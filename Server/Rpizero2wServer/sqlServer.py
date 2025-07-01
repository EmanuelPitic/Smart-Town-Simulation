import sqlite3
from typing import Optional, List, Tuple
from client import Client
from message import Message
import hashlib
import threading
from datetime import datetime

class SQLServer:
    """Initializes and configures the MQTT SQL server with essential parameters and database setup."""

    def __init__(self, db_name="mqtt_server.db", SUPPORTED_MQTT_VERSION=5.0, MAX_CONNECTIONS=50, MIN_CONNECTION_INTERVAL=1, MAX_CLIENT_ID_LENGTH=23):
        # Initialize server parameters and set up database tables
        self.db_name = db_name
        self.SUPPORTED_MQTT_VERSION = SUPPORTED_MQTT_VERSION
        self.MAX_CONNECTIONS = MAX_CONNECTIONS
        self.MIN_CONNECTION_INTERVAL = MIN_CONNECTION_INTERVAL
        self.MAX_CLIENT_ID_LENGTH = MAX_CLIENT_ID_LENGTH
        self.lock = threading.Lock()  # Ensures thread-safe operations
        self.setup_tables()  # Create database tables if they don’t exist

    def _get_connection(self):
        """Creates and returns a new SQLite connection for the current thread."""
        return sqlite3.connect(self.db_name, check_same_thread=False)

    def setup_tables(self):
        """
        Creates all necessary database tables for managing MQTT server clients, topics, subscriptions, messages, and related data.
        """

        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Create tables if they don't exist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS clients (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    client_id TEXT NOT NULL UNIQUE,
                    banned BOOLEAN DEFAULT 0,  -- Indicates if the client is banned
                    clean_session BOOLEAN DEFAULT 1,
                    connected BOOLEAN DEFAULT 0,
                    keep_alive INTEGER DEFAULT 60,
                    session_expiry INTEGER DEFAULT 0,  -- Expiry in seconds
                    last_seen DATETIME DEFAULT CURRENT_TIMESTAMP
                );
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    password TEXT -- Hashed password for security
                );
            """)


            cursor.execute("""
                CREATE TABLE IF NOT EXISTS topics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    parent_id INTEGER,  -- Reference to parent topic (NULL for root topics)
                    topic_name TEXT NOT NULL,
                    full_path TEXT UNIQUE NOT NULL,  -- Full topic path (e.g., "home/livingroom")
                    retained_message TEXT,  -- Latest retained message (optional)
                    retained_qos INTEGER DEFAULT 0,  -- QoS of the retained message
                    retained_timestamp DATETIME,  -- Timestamp of the retained message
                    FOREIGN KEY (parent_id) REFERENCES topics (id) ON DELETE CASCADE
                );
            """)
            cursor.execute("""
           CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id TEXT NOT NULL,
                topic_id INTEGER,  -- Allow NULL for wildcard topics
                topic_filter TEXT,  -- Stores the topic filter for wildcard subscriptions
                qos INTEGER DEFAULT 0,
                FOREIGN KEY (client_id) REFERENCES clients (client_id) ON DELETE CASCADE,
                FOREIGN KEY (topic_id) REFERENCES topics (id) ON DELETE CASCADE
            );
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    topic_id INTEGER NOT NULL,  -- Links to the `topics` table
                    payload TEXT NOT NULL,  -- The message content
                    qos INTEGER DEFAULT 0,
                    retain BOOLEAN DEFAULT 0,
                    packet_id INTEGER,  -- Stores the packet identifier for QoS 1 and 2 messages
                    published_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (topic_id) REFERENCES topics (id) ON DELETE CASCADE
                );
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS topic_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    topic_id INTEGER NOT NULL,  -- Links to the `topics` table
                    message_id INTEGER NOT NULL,  -- Links to the `messages` table
                    FOREIGN KEY (topic_id) REFERENCES topics (id) ON DELETE CASCADE,
                    FOREIGN KEY (message_id) REFERENCES messages (id) ON DELETE CASCADE
                );
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS will_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    client_id TEXT NOT NULL,
                    topic_id INTEGER NOT NULL,  -- Links to the `topics` table
                    message TEXT NOT NULL,
                    qos INTEGER DEFAULT 0,
                    retain BOOLEAN DEFAULT 0,
                    registered_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (client_id) REFERENCES clients (client_id) ON DELETE CASCADE,
                    FOREIGN KEY (topic_id) REFERENCES topics (id) ON DELETE CASCADE
                );
            """)
            conn.commit()

    def store_client(self, decoded_packet: dict) -> Tuple[int, int]:
        """
        Tries to store and authenticate the client. Returns a tuple of (connect_ack_flags, reason_code).
        """
        client_id = decoded_packet.get("client_id")
        username = decoded_packet.get("username")
        password = decoded_packet.get("password")
        protocol_level = decoded_packet.get("protocol_level")
        packet_size = decoded_packet.get("length")

        # Reject if packet size exceeds maximum allowed limit
        if packet_size > 268435456:
            return (0x00, 0x95)  # Packet too large

        # Reject if MQTT protocol version is unsupported
        if protocol_level != self.SUPPORTED_MQTT_VERSION:
            return (0x00, 0x84)  # Unsupported Protocol Version

        # Check server availability and reject if unavailable
        if not self.is_server_available():
            return (0x00, 0x88)  # Server Unavailable

        # Reject if server is too busy to handle more connections
        if self.is_server_busy():
            return (0x00, 0x89)  # Server Busy

        # Reject if client is banned
        if self.is_client_banned(client_id):
            return (0x00, 0x8A)  # Client Banned

        # Reject if client is connecting too frequently
        if self.is_connection_rate_exceeded(client_id):
            return (0x00, 0x9F)  # Connection Rate Exceeded

        # Reject if client ID is invalid or too long
        if not client_id or len(client_id) > self.MAX_CLIENT_ID_LENGTH:
            return (0x00, 0x85)  # Client Identifier Not Valid

        # Store or authenticate client in the database
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT password, username FROM users WHERE username = ?", (username,))
                existing_record = cursor.fetchone()

                # Validate username and password if client already exists
                if existing_record:
                    stored_password_hash = existing_record[0]
                    stored_username = existing_record[1]
                    provided_password_hash = hashlib.sha256(password.encode()).hexdigest() if password else None
                    if provided_password_hash != stored_password_hash or stored_username != username:
                        return (0x00, 0x86)  # Bad Username or Password

                # Hash password if provided
                password_hash = hashlib.sha256(password.encode()).hexdigest() if password else None

                # Insert or update client record in the database
                query = """
                INSERT INTO clients (client_id, session_expiry, keep_alive, connected)
                VALUES (?, ?, ?, 1)
                ON CONFLICT(client_id) DO UPDATE SET
                    connected=1,
                    session_expiry=excluded.session_expiry,
                    keep_alive=excluded.keep_alive,
                    last_seen=CURRENT_TIMESTAMP
                """
                cursor.execute(query, (client_id, decoded_packet.get("session_expiry", 0),
                                       decoded_packet.get("keep_alive", 60)))
                conn.commit()  # Save changes to the database

                query = """
                INSERT INTO users (username, password)
                VALUES (?, ?)
                ON CONFLICT(username) DO UPDATE SET
                    username=excluded.username,
                    password=excluded.password
                """
                cursor.execute(query, (username, password_hash))
                conn.commit()  # Save changes to the database

            # Handle Last Will if provided
            if decoded_packet.get("will_flag"):
                self.save_will_message(
                    client_id=client_id,
                    topic=decoded_packet.get("will_topic"),
                    message=decoded_packet.get("will_message"),
                    qos=decoded_packet.get("will_properties", {}).get("will_qos", 0),
                    retain=decoded_packet.get("will_properties", {}).get("will_retain", False),
                )

            return (0x00, 0x00)  # Connection Success

        except sqlite3.IntegrityError as e:
            print(f"Error storing client '{client_id}': {e}")
            return (0x00, 0x87)  # Connection Refused, Not Authorized

    def is_server_available(self) -> bool:
        """Checks if server is available for new connections."""
        return True  # Placeholder for actual server status check

    def is_server_busy(self) -> bool:
        """Checks if server is busy, e.g., using a limit on active connections."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                # Query count of currently connected clients
                cursor.execute("SELECT COUNT(*) FROM clients WHERE connected = 1")
                active_connections = cursor.fetchone()[0]
                # Return True if active connections exceed max allowed connections
                return active_connections >= self.MAX_CONNECTIONS
        except sqlite3.Error as e:
            print(f"Error checking server busy status: {e}")
            return True

    def is_client_banned(self, client_id: str) -> bool:
        """Checks if a client is banned by querying the banned status from the clients table."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                # Query the banned status for the given client_id
                cursor.execute("SELECT banned FROM clients WHERE client_id = ?", (client_id,))
                result = cursor.fetchone()

                # Return True if the client is found and banned, otherwise False
                return result is not None and result[0] == 1

        except sqlite3.Error as e:
            print(f"Error checking banned status for client '{client_id}': {e}")
            # In case of an error, assume the client is not banned to avoid disruptions
            return False

    def is_connection_rate_exceeded(self, client_id: str) -> bool:
        """Checks if a client is connecting too frequently."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT last_seen FROM clients WHERE client_id = ?", (client_id,))
                last_seen_row = cursor.fetchone()

                # Allow connection if no last seen record exists
                if not last_seen_row or not last_seen_row[0]:
                    return False

                # Calculate time since last connection attempt
                last_seen_time = datetime.strptime(last_seen_row[0], "%Y-%m-%d %H:%M:%S")
                time_since_last_seen = (datetime.now() - last_seen_time).total_seconds()

                # Reject if connection interval is too short
                if time_since_last_seen < self.MIN_CONNECTION_INTERVAL:
                    print(f"Client '{client_id}' exceeded connection rate limit.")
                    return True

                # Update last seen time in the database
                cursor.execute("UPDATE clients SET last_seen = ? WHERE client_id = ?",
                               (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), client_id))
                conn.commit()  # Save changes to the database

                return False

        except sqlite3.Error as e:
            print(f"Error checking connection rate for client '{client_id}': {e}")
            return True

            return False

    def save_subscription(self, client_id: str, topic: str, qos: int) -> bool:
        """
        Saves a subscription for a client to a specific topic with the specified QoS level.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Check if the topic contains wildcards
                if '+' in topic or '#' in topic:
                    topic_id = None  # No topic ID since wildcards are not actual topics
                    topic_filter = topic  # Store the topic filter directly
                else:
                    # Check if the topic exists in the topics table
                    cursor.execute("SELECT id FROM topics WHERE full_path = ?", (topic,))
                    topic_result = cursor.fetchone()

                    # Insert topic into the topics table if it doesn't exist
                    if not topic_result:
                        cursor.execute(
                            "INSERT INTO topics (topic_name, full_path) VALUES (?, ?)",
                            (topic.split('/')[-1], topic)
                        )
                        conn.commit()
                        topic_id = cursor.lastrowid
                    else:
                        topic_id = topic_result[0]
                    topic_filter = None  # No need to store topic filter for exact topics

                # Insert subscription into the subscriptions table
                cursor.execute("""
                    INSERT INTO subscriptions (client_id, topic_id, topic_filter, qos)
                    VALUES ((SELECT client_id FROM clients WHERE client_id = ?), ?, ?, ?)
                """, (client_id, topic_id, topic_filter, qos))

                conn.commit()
                return True
        except sqlite3.Error as e:
            print(f"Error saving subscription for client '{client_id}' on topic '{topic}': {e}")
            return False

    def save_message(self, message: Message) -> bool:
        """
        Saves a message to the database, associating it with a topic.
        If the topic does not exist, it will be created.
        Handles retained messages by updating the topic's retained message details.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM topics WHERE full_path = ?", (message.topic,))
                topic_result = cursor.fetchone()
                if not topic_result:
                    # Create topic if it doesn't exist
                    cursor.execute("INSERT INTO topics (topic_name, full_path) VALUES (?, ?)",
                                   (message.topic.split('/')[-1], message.topic))
                    conn.commit()
                    topic_id = cursor.lastrowid
                else:
                    topic_id = topic_result[0]

                # Save the message
                query = """
                INSERT INTO messages (topic_id, payload, qos, retain, packet_id, published_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """
                cursor.execute(query, (topic_id, message.payload, message.qos, message.retain, message.packet_id))
                conn.commit()

                # If the message is retained, update the topics table
                if message.retain:
                    update_query = """
                    UPDATE topics
                    SET retained_message = ?, retained_qos = ?, retained_timestamp = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """
                    cursor.execute(update_query, (message.payload, message.qos, topic_id))
                    conn.commit()

                return True
        except sqlite3.Error as e:
            print(f"Error saving message: {e}")
            return False

    def save_will_message(self, client_id: str, topic: str, message: str, qos: int = 0, retain: bool = False) -> bool:
        """
        Saves a Last Will and Testament (LWT) message for a client.
        Associates the will message with a topic, creating the topic if it does not exist.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM topics WHERE full_path = ?", (topic,))
                topic_result = cursor.fetchone()
                if not topic_result:
                    cursor.execute("INSERT INTO topics (topic_name, full_path) VALUES (?, ?)", (topic.split('/')[-1], topic))
                    conn.commit()
                    topic_id = cursor.lastrowid
                else:
                    topic_id = topic_result[0]

                query = """
                INSERT INTO will_messages (client_id, topic_id, message, qos, retain, registered_at)
                VALUES ((SELECT client_id FROM clients WHERE client_id = ?), ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """
                cursor.execute(query, (client_id, topic_id, message, qos, retain))
                conn.commit()
                return True
        except sqlite3.Error as e:
            print(f"Error saving will message for client '{client_id}' on topic '{topic}': {e}")
            return False


    def update_disconnect_time(self, client_id: str) -> None:
        """
        Updates the last seen timestamp and marks the client as disconnected in the database.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE clients SET last_seen = CURRENT_TIMESTAMP, connected = 0 WHERE client_id = ?",
                    (client_id,)
                )
                conn.commit()
        except sqlite3.Error as e:
            print(f"Error updating disconnect time for client '{client_id}': {e}")

    def get_subscribers(self, topic_name: str) -> List[Tuple[str, int]]:
        """
        Retrieves a list of subscribers to a given topic, including both exact and wildcard matches.
        Returns a list of tuples containing client IDs and QoS levels.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Fetch all subscriptions
                cursor.execute("""
                    SELECT DISTINCT subscriptions.client_id, subscriptions.qos, subscriptions.topic_id, topics.full_path
                    FROM subscriptions
                    LEFT JOIN topics ON subscriptions.topic_id = topics.id
                    JOIN clients ON subscriptions.client_id = clients.client_id
                    WHERE clients.connected = 1
                """)
                all_subscriptions = cursor.fetchall()

                # Filter matches based on wildcards and exact matches
                matched_subscribers = []
                for client_id, qos, topic_id, subscription_topic in all_subscriptions:
                    if subscription_topic:
                        # Exact topic subscription
                        if self.matches_wildcard(subscription_topic, topic_name):
                            matched_subscribers.append((client_id, qos))
                    else:
                        # Wildcard subscription (topic_id is None)
                        # The topic filter is stored elsewhere; you need to adjust your subscriptions table
                        # to store the topic filter as a string for wildcard subscriptions
                        cursor.execute("""
                            SELECT topic_filter FROM subscriptions
                            WHERE client_id = ? AND topic_id IS NULL
                        """, (client_id,))
                        wildcard_subscription = cursor.fetchone()
                        if wildcard_subscription and self.matches_wildcard(wildcard_subscription[0], topic_name):
                            matched_subscribers.append((client_id, qos))

                return matched_subscribers

        except sqlite3.Error as e:
            print(f"Error getting subscribers for topic '{topic_name}': {e}")
            return []

    def remove_subscription(self, client_id: str, topic: str) -> bool:
        """
        Removes a subscription for the given client and topic.
        Handles both direct topic subscriptions and wildcard topic filters.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Check for wildcard topic filter
                cursor.execute("""
                    DELETE FROM subscriptions
                    WHERE client_id = ? AND topic_filter = ?
                """, (client_id, topic))
                wildcard_deleted = cursor.rowcount > 0

                # Check for direct topic subscription
                cursor.execute("SELECT id FROM topics WHERE full_path = ?", (topic,))
                topic_result = cursor.fetchone()
                if topic_result:
                    topic_id = topic_result[0]
                    cursor.execute("""
                        DELETE FROM subscriptions
                        WHERE client_id = ? AND topic_id = ?
                    """, (client_id, topic_id))
                    direct_deleted = cursor.rowcount > 0
                else:
                    direct_deleted = False

                if wildcard_deleted or direct_deleted:
                    conn.commit()
                    print(f"Subscription for client '{client_id}' to topic '{topic}' removed successfully.")
                    return True
                else:
                    print(f"No subscription found for client '{client_id}' on topic '{topic}'.")
                    return False

        except sqlite3.Error as e:
            print(f"Error removing subscription for client '{client_id}' on topic '{topic}': {e}")
            return False

    def retrieve_message_by_packet_id(self, packet_id):
        """
        Retrieves a message from the database using the given packet ID.
        Returns a Message object if found, otherwise returns None.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                query = """
                SELECT topics.full_path, messages.payload, messages.qos, messages.retain, messages.packet_id
                FROM messages
                JOIN topics ON messages.topic_id = topics.id
                WHERE messages.packet_id = ?
                """
                cursor.execute(query, (packet_id,))
                result = cursor.fetchone()

                if result:
                    topic, payload, qos, retain, packet_id = result
                    return Message(topic=topic, payload=payload, qos=qos, retain=retain, packet_id=packet_id)
                else:
                    return None
        except sqlite3.Error as e:
            print(f"Error retrieving message by packet ID '{packet_id}': {e}")
            return None

    def matches_wildcard(self, subscription: str, topic: str) -> bool:
        """
        Checks if a topic matches a wildcard subscription.
        Supports:
        - Single-level wildcard `+`
        - Multi-level wildcard `#`
        """
        subscription_levels = subscription.split('/')
        topic_levels = topic.split('/')

        for sub_level, topic_level in zip(subscription_levels, topic_levels):
            if sub_level == '+':
                continue  # Single-level wildcard matches anything at this level
            if sub_level == '#':
                return True  # Multi-level wildcard matches everything after
            if sub_level != topic_level:
                return False

        # If all levels match, check for trailing wildcards
        if len(subscription_levels) > len(topic_levels):
            return subscription_levels[len(topic_levels)] == '#'

        return len(subscription_levels) == len(topic_levels)

    def retrieve_last_will(self, client_id: str) -> Optional[dict]:
        """
        Retrieve the Last Will message for the specified client.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                query = """
                SELECT topics.full_path, will_messages.message, will_messages.qos, will_messages.retain
                FROM will_messages
                JOIN topics ON will_messages.topic_id = topics.id
                WHERE will_messages.client_id = ?
                """
                cursor.execute(query, (client_id,))
                result = cursor.fetchone()
                if result:
                    topic, message, qos, retain = result
                    return {
                        "topic": topic,
                        "message": message,
                        "qos": qos,
                        "retain": retain
                    }
                return None
        except sqlite3.Error as e:
            print(f"Error retrieving Last Will for client '{client_id}': {e}")
            return None

    def remove_last_will(self, client_id: str) -> bool:
        """
        Removes the Last Will message for the specified client.
        Returns True if the operation was successful, False otherwise.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                query = "DELETE FROM will_messages WHERE client_id = ?"
                cursor.execute(query, (client_id,))
                if cursor.rowcount > 0:
                    conn.commit()
                    print(f"Last Will message for client '{client_id}' successfully removed.")
                    return True
                else:
                    print(f"No Last Will message found for client '{client_id}'.")
                    return False
        except sqlite3.Error as e:
            print(f"Error removing Last Will for client '{client_id}': {e}")
            return False

    def remove_all_subscriptions_for_client(self, client_id: str) -> bool:
        """
        Removes all subscriptions for a given client ID from the database.
        This is typically used when a client disconnects with `clean_flag = 1`.
        Returns True if at least one subscription is removed, False otherwise.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Delete all subscriptions for the given client ID
                query = """
                DELETE FROM subscriptions WHERE client_id = ?
                """
                cursor.execute(query, (client_id,))

                # Check if any rows were affected
                if cursor.rowcount > 0:
                    conn.commit()
                    return True
                else:
                    print(f"No subscriptions found for client '{client_id}'.")
                    return False

        except sqlite3.Error as e:
            print(f"Error removing subscriptions for client '{client_id}': {e}")
            return False

    from typing import List

    def return_last_retained_messages(self, topic_filter: str) -> List[Message]:
        """
        Retrieves the last retained messages matching a specific topic filter.
        Supports wildcards ('+' for single level, '#' for multi-level).
        Returns a list of Message objects if retained messages exist, otherwise an empty list.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                if "+" in topic_filter or "#" in topic_filter:
                    # Convert MQTT wildcards to SQL LIKE pattern
                    like_pattern = topic_filter.replace("+", "_").replace("#", "%")
                    query = """
                    SELECT full_path, retained_message, retained_qos, retained_timestamp
                    FROM topics
                    WHERE full_path LIKE ?
                    """
                    cursor.execute(query, (like_pattern,))
                else:
                    # Exact match for non-wildcard topics
                    query = """
                    SELECT full_path, retained_message, retained_qos, retained_timestamp
                    FROM topics
                    WHERE full_path = ?
                    """
                    cursor.execute(query, (topic_filter,))

                # Fetch all matching rows
                results = cursor.fetchall()

                # Construct a list of Message objects for topics with retained messages
                retained_messages = []
                for full_path, retained_message, retained_qos, retained_timestamp in results:
                    if retained_message is not None:
                        retained_messages.append(
                            Message(
                                topic=full_path,
                                payload=retained_message,
                                qos=retained_qos,
                                retain=True,
                                packet_id=None,  # Retained messages do not have a packet ID
                                published_at=retained_timestamp
                            )
                        )

                if not retained_messages:
                    print(f"No retained messages found for topic filter '{topic_filter}'.")
                return retained_messages

        except sqlite3.Error as e:
            print(f"Error retrieving retained messages for topic filter '{topic_filter}': {e}")
            return []

    def close(self):
        # Connections are managed per-thread, so no need to close here
        pass