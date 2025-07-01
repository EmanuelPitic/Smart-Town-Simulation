import struct

class MQTTDecoder:
    def decode_mqtt_packet(self, data):
        packet_type = data[0] >> 4
        if packet_type == 1:  # CONNECT
            return self._decode_connect(data)
        elif packet_type == 3:  # PUBLISH
            return self._decode_publish(data)
        elif packet_type == 4:  # PUBACK
            return self._decode_puback(data)
        elif packet_type == 5:  # PUBREC
            return self._decode_pubrec(data)
        elif packet_type == 6:  # PUBREL
            return self._decode_pubrel(data)
        elif packet_type == 7:  # PUBCOMP
            return self._decode_pubcomp(data)
        elif packet_type == 8:  # SUBSCRIBE
            return self._decode_subscribe(data)
        elif packet_type == 10:  # UNSUBSCRIBE
            return self._decode_unsubscribe(data)
        elif packet_type == 12:  # PINGREQ
            return {"packet_type": "PINGREQ"}
        elif packet_type == 14:  # DISCONNECT
            return self._decode_disconnect(data)
        else:
            raise ValueError("Unsupported packet type")

    def _decode_remaining_length(self, data, index):
        multiplier = 1
        value = 0
        while True:
            encoded_byte = data[index]
            index += 1
            value += (encoded_byte & 127) * multiplier
            if (encoded_byte & 128) == 0:
                break
            multiplier *= 128
        return value, index

    def _decode_string(self, data, index):
        if index + 2 > len(data):
            raise ValueError(f"Not enough data to decode string length at index {index}")
        str_len = struct.unpack("!H", data[index:index + 2])[0]
        index += 2
        if index + str_len > len(data):
            raise ValueError(f"Not enough data to decode string of length {str_len} at index {index}")
        return data[index:index + str_len].decode("utf-8"), index + str_len

    def _decode_properties(self, data, index):
        properties = {}
        prop_length, index = self._decode_remaining_length(data, index)
        end_index = index + prop_length

        while index < end_index:
            prop_id = data[index]
            index += 1

            # Handle known property IDs
            if prop_id == 0x11:  # Session Expiry Interval (4-byte integer)
                properties["session_expiry_interval"] = struct.unpack("!I", data[index:index + 4])[0]
                index += 4
            elif prop_id == 0x01:  # Payload Format Indicator (1-byte integer)
                properties["payload_format_indicator"] = data[index]
                index += 1
            elif prop_id == 0x02:  # Message Expiry Interval (4-byte integer)
                properties["message_expiry_interval"] = struct.unpack("!I", data[index:index + 4])[0]
                index += 4
            elif prop_id == 0x03:  # Content Type (UTF-8 string)
                properties["content_type"], index = self._decode_string(data, index)
            elif prop_id == 0x08:  # Response Topic (UTF-8 string)
                properties["response_topic"], index = self._decode_string(data, index)
            elif prop_id == 0x09:  # Correlation Data (Binary Data)
                properties["correlation_data"], index = self._decode_binary_data(data, index)
            elif prop_id == 0x26:  # User Properties (UTF-8 key-value pairs)
                if "user_properties" not in properties:
                    properties["user_properties"] = []
                key, index = self._decode_string(data, index)
                value, index = self._decode_string(data, index)
                properties["user_properties"].append({"key": key, "value": value})
            else:
                # Log and skip unknown properties
                print(f"Skipping unknown property ID: {prop_id} at index {index - 1}")
                if index < end_index:
                    # Safely skip 1-byte properties or advance to the next byte
                    index += 1
                else:
                    raise ValueError(f"Malformed property at index {index - 1}")

        return properties, index

    def _decode_binary_data(self, data, index):
        if index + 2 > len(data):
            raise ValueError(f"Not enough data to decode binary data length at index {index}")
        data_len = struct.unpack("!H", data[index:index + 2])[0]
        index += 2
        if index + data_len > len(data):
            raise ValueError(f"Not enough data to decode binary data of length {data_len} at index {index}")
        return data[index:index + data_len], index + data_len

    def _decode_connect(self, data):
        remaining_length, index = self._decode_remaining_length(data, 1)
        print(f"Remaining length: {remaining_length}, starting index: {index}")

        # Protocol name
        protocol_name, index = self._decode_string(data, index)
        print(f"Protocol name: {protocol_name}, next index: {index}")

        protocol_level = data[index]
        index += 1
        connect_flags = data[index]
        index += 1
        keep_alive = struct.unpack("!H", data[index:index + 2])[0]
        index += 2
        print(f"Protocol level: {protocol_level}, Connect flags: {connect_flags}, Keep alive: {keep_alive}")

        # Properties
        properties, index = self._decode_properties(data, index)
        print(f"Properties: {properties}, next index: {index}")

        # Client ID
        client_id, index = self._decode_string(data, index)
        print(f"Client ID: {client_id}, next index: {index}")

        # Will fields
        will_flag = bool(connect_flags & 0x04)
        print(f"Will Flag: {will_flag}")
        will_properties = {}
        will_topic = None
        will_message = None

        if will_flag:
            # Will Properties
            will_properties, index = self._decode_properties(data, index)
            print(f"Will Properties: {will_properties}, next index: {index}")

            # Will Topic
            will_topic, index = self._decode_string(data, index)
            print(f"Will Topic: {will_topic}, next index: {index}")

            # Will Message
            will_message, index = self._decode_string(data, index)
            print(f"Will Message: {will_message}, next index: {index}")

        # Username and Password
        username = None
        password = None
        if connect_flags & 0x80:
            username, index = self._decode_string(data, index)
            print(f"Username: {username}, next index: {index}")
        if connect_flags & 0x40:
            password, index = self._decode_string(data, index)
            print(f"Password: {password}, next index: {index}")

        # Extract clean_session
        clean_session = bool(connect_flags & 0x02)
        print(f"Clean Session: {clean_session}")

        return {
            "packet_type": "CONNECT",
            "protocol_name": protocol_name,
            "protocol_level": protocol_level,
            "connect_flags": connect_flags,
            "clean_session": clean_session,
            "keep_alive": keep_alive,
            "properties": properties,
            "client_id": client_id,
            "will_flag": will_flag,
            "will_properties": will_properties,
            "will_topic": will_topic,
            "will_message": will_message,
            "username": username,
            "password": password,
            "length": len(data)
        }

    def _decode_publish(self, data):
        # Decode the remaining length
        remaining_length, index = self._decode_remaining_length(data, 1)

        # Extract the retain flag from the first byte of the fixed header (bit 0)
        retain = bool(data[0] & 0b00000001)

        # Decode the topic name
        topic_name, index = self._decode_string(data, index)

        # Extract QoS level from the first byte of the fixed header (bits 1 and 2)
        qos = (data[0] & 0b00000110) >> 1  # Extract QoS bits

        # Decode packet identifier if QoS > 0
        packet_identifier = None
        if qos > 0:
            packet_identifier = struct.unpack("!H", data[index:index + 2])[0]
            index += 2

        # Decode properties (for MQTT 5.0)
        properties, index = self._decode_properties(data, index)
        # Decode payload
        payload = data[index:]
        try:
            decoded_payload = payload.decode("utf-8")
        except UnicodeDecodeError:
            # Handle non-UTF-8 payload gracefully
            decoded_payload = payload  # Keep it as bytes if decoding fails

        return {
            "packet_type": "PUBLISH",
            "retain": retain,
            "topic_name": topic_name,
            "packet_identifier": packet_identifier,
            "qos": qos,
            "properties": properties,
            "payload": decoded_payload
        }

    def _decode_puback(self, data):
        # Decode PUBACK packet
        packet_id = struct.unpack("!H", data[2:4])[0]
        return {
            "packet_type": "PUBACK",
            "packet_identifier": packet_id
        }

    def _decode_pubrec(self, data):
        # Decode PUBREC packet
        packet_id = struct.unpack("!H", data[2:4])[0]
        return {
            "packet_type": "PUBREC",
            "packet_identifier": packet_id
        }

    def _decode_pubrel(self, data):
        # Decode PUBREL packet
        packet_id = struct.unpack("!H", data[2:4])[0]
        return {
            "packet_type": "PUBREL",
            "packet_identifier": packet_id
        }

    def _decode_pubcomp(self, data):
        # Decode PUBCOMP packet
        packet_id = struct.unpack("!H", data[2:4])[0]
        return {
            "packet_type": "PUBCOMP",
            "packet_identifier": packet_id
        }

    def _decode_subscribe(self, data):
        remaining_length, index = self._decode_remaining_length(data, 1)
        end_index = index + remaining_length

        if index + 2 > len(data):
            raise ValueError("Malformed SUBSCRIBE packet identifier")
        packet_identifier = struct.unpack("!H", data[index:index + 2])[0]
        index += 2

        # Attempt to decode properties only if there is remaining length
        properties = {}
        if index < end_index:
            try:
                properties, index = self._decode_properties(data, index)
            except ValueError:
                print("Error: Unable to parse properties. Skipping properties for this packet.")
                properties = {}

        # Ensure properties are parsed as an empty dictionary if not present
        if not properties:
            properties = {}

        # Topic filters and subscription options
        topics = []
        while index < end_index:
            topic_filter, index = self._decode_string(data, index)
            if index >= len(data):
                raise ValueError("Malformed Subscription Options")
            subscription_options = data[index]
            index += 1
            topics.append({
                "topic_filter": topic_filter,
                "subscription_options": subscription_options
            })

        return {
            "packet_type": "SUBSCRIBE",
            "packet_identifier": packet_identifier,
            "properties": properties,
            "topics": topics
        }

    def _decode_unsubscribe(self, data):
        remaining_length, index = self._decode_remaining_length(data, 1)
        end_index = index + remaining_length

        if index + 2 > len(data):
            raise ValueError("Malformed UNSUBSCRIBE packet identifier")
        packet_identifier = struct.unpack("!H", data[index:index + 2])[0]
        index += 2

        # Properties
        properties, index = self._decode_properties(data, index)

        # Topic filters
        topics = []
        while index < end_index:
            topic_filter, index = self._decode_string(data, index)
            topics.append(topic_filter)

        return {
            "packet_type": "UNSUBSCRIBE",
            "packet_identifier": packet_identifier,
            "properties": properties,
            "topics": topics
        }

    def _decode_disconnect(self, data):
        remaining_length, index = self._decode_remaining_length(data, 1)

        # Properties
        properties = {}
        if remaining_length > 0:
            properties, _ = self._decode_properties(data, index)

        return {
            "packet_type": "DISCONNECT",
            "properties": properties
        }
