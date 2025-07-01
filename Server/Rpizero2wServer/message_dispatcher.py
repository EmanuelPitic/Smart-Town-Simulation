from concurrent.futures import ThreadPoolExecutor
from queue import Queue, Empty
import threading
import socket
from decoder import MQTTDecoder
from packet_creator import create_publish_packet, create_pubrel_packet, create_disconnect_packet

class MessageDispatcher:
    def __init__(self, db, max_workers=5):
        self.db = db
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.message_queue = Queue()
        self.packet_id_counter = 0
        self.pending_acks = {}
        self.pending_acks_lock = threading.Lock()
        self.shutdown_event = threading.Event()
        self.isKillSwitch = False

        # Start worker threads to process messages
        for _ in range(max_workers):
            threading.Thread(target=self._process_queue, daemon=True).start()

    def dispatch_message(self, message, active_connections, isKillSwitch = False):
        """Enqueue a message for dispatching."""
        print('Enqueuing message for dispatch')
        self.isKillSwitch = isKillSwitch
        self.message_queue.put((message, active_connections))

    def _process_queue(self):
        """Continuously process the message queue and dispatch messages."""
        while not self.shutdown_event.is_set():
            try:
                if self.isKillSwitch == False:
                    message, active_connections = self.message_queue.get(timeout=1)
                    print('Dispatching message from queue')

                    # Retrieve the subscribers for the topic
                    subscribers = self.db.get_subscribers(message.topic)
                    if not subscribers:
                        print(f"No subscribers found for topic '{message.topic}'")
                    else:
                        for subscriber_id, qos_for_subscriber in subscribers:
                            subscriber_conn = active_connections.get(subscriber_id)

                            # Submit the message-sending task
                            if subscriber_conn:
                                self.executor.submit(
                                    self._send_message,
                                    subscriber_id,
                                    subscriber_conn,
                                    message,
                                    qos_for_subscriber
                                )

                    self.message_queue.task_done()
                else:
                    message, active_connections = self.message_queue.get(timeout=1)
                    for conn_id, connection in active_connections:
                        self.executor.submit(
                            self._send_message,
                            conn_id,
                            connection,
                            message,
                            1
                        )

            except Empty:
                continue  # Continue if the queue is empty
            except Exception as e:
                print(f"Error processing message from queue: {e}")

    def _send_message(self, subscriber_id, subscriber_conn, message, qos_for_subscriber):
        """Send a message to a subscriber."""
        try:
            if self.isKillSwitch == False:
                print(f'Sending message to subscriber {subscriber_id}')
                packet_id = self._generate_packet_id()
                effective_qos = min(qos_for_subscriber, message.qos)

                # Initialize waiting event before sending the message
                if effective_qos in (1, 2):
                    event = threading.Event()
                    with self.pending_acks_lock:
                        self.pending_acks[packet_id] = event
                        print(f"Initialized event for packet ID {packet_id}")

                publish_packet = create_publish_packet(
                    message.topic, message.payload, effective_qos, message.retain, packet_id
                )

                # Ensure the pending_acks entry is in place before sending the packet
                subscriber_conn.sendall(publish_packet)
                print(f"Sent PUBLISH packet with ID {packet_id} to '{subscriber_id}'")

                if effective_qos == 1:
                    # Wait for PUBACK
                    if not event.wait(timeout=5):
                        print(f"No PUBACK received for packet ID {packet_id} from '{subscriber_id}'")
                elif effective_qos == 2:
                    self._handle_qos2(subscriber_id, subscriber_conn, packet_id)
            else:
                subscriber_conn.sendall(create_disconnect_packet())

        except (socket.error, Exception) as e:
            print(f"Error sending PUBLISH to subscriber '{subscriber_id}': {e}")
        finally:
            # Clean up the event after handling
            if effective_qos in (1, 2):
                with self.pending_acks_lock:
                    self.pending_acks.pop(packet_id, None)
                    print(f"Removed packet ID {packet_id} from pending_acks")

    def _handle_qos1(self, subscriber_id, subscriber_conn, packet_id, publish_packet):
        """Handle QoS level 1 packet acknowledgment (PUBACK)."""
        puback_event = threading.Event()
        with self.pending_acks_lock:
            self.pending_acks[packet_id] = puback_event
            subscriber_conn.sendall(publish_packet)
            print(f"Sent PUBLISH packet with ID {packet_id} to '{subscriber_id}'")
            print(f"Added PUBACK event for packet ID {packet_id} to pending_acks")

        if puback_event.wait(timeout=5):
            print(f"Received PUBACK for packet ID {packet_id} from '{subscriber_id}'")
        else:
            print(f"No PUBACK received for packet ID {packet_id} from '{subscriber_id}'")

        with self.pending_acks_lock:
            self.pending_acks.pop(packet_id, None)
            print(f"Removed packet ID {packet_id} from pending_acks")

    def _handle_qos2(self, subscriber_id, subscriber_conn, packet_id):
        """Handle QoS level 2 packet acknowledgment flow."""
        pubrec_event = threading.Event()
        with self.pending_acks_lock:
            self.pending_acks[packet_id] = pubrec_event
            print(f"Added PUBREC event for packet ID {packet_id} to pending_acks")

        if pubrec_event.wait(timeout=5):
            print(f"Received PUBREC for packet ID {packet_id} from '{subscriber_id}'")
            pubrel_packet = create_pubrel_packet(packet_id)
            subscriber_conn.sendall(pubrel_packet)
            print(f"Sent PUBREL for packet ID {packet_id} to '{subscriber_id}'")

            pubcomp_event = threading.Event()
            with self.pending_acks_lock:
                self.pending_acks[packet_id] = pubcomp_event
                print(f"Replaced with PUBCOMP event for packet ID {packet_id} in pending_acks")

            if pubcomp_event.wait(timeout=5):
                print(f"Received PUBCOMP for packet ID {packet_id} from '{subscriber_id}'")
            else:
                print(f"No PUBCOMP received for packet ID {packet_id} from '{subscriber_id}'")
        else:
            print(f"No PUBREC received for packet ID {packet_id} from '{subscriber_id}'")

        with self.pending_acks_lock:
            self.pending_acks.pop(packet_id, None)
            print(f"Removed packet ID {packet_id} from pending_acks")

    def _generate_packet_id(self):
        """Generate a new packet ID, ensuring it stays within the valid range."""
        self.packet_id_counter = (self.packet_id_counter + 1) % 65536
        if self.packet_id_counter == 0:
            self.packet_id_counter = 1
        return self.packet_id_counter




    def shutdown(self):
        """Shut down the dispatcher gracefully."""
        self.shutdown_event.set()
        self.executor.shutdown(wait=True)
        print("MessageDispatcher shutdown complete.")
