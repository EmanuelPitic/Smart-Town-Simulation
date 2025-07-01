import struct

def encode_remaining_length(length):
    encoded = bytearray()
    while True:
        byte = length % 128
        length //= 128
        if length > 0:
            byte |= 0x80
        encoded.append(byte)
        if length == 0:
            break
    return encoded


def create_connack_packet(
        connect_ack_flags=0,
        reason_code=0,
        session_expiry_interval=None,
        receive_maximum=None,
        maximum_qos=None,
        retain_available=None,
        maximum_packet_size=None,
        assigned_client_identifier=None,
        server_keep_alive=None,
        response_information=None,
        server_reference=None
):
    # Packet Type
    packet_type = 0x20  # CONNACK packet type

    # Variable Header
    variable_header = bytes([connect_ack_flags, reason_code])

    # Properties
    properties = bytearray()

    # Encode each property if provided
    if session_expiry_interval is not None:
        properties.extend([0x11])  # Property identifier for session expiry interval
        properties.extend(session_expiry_interval.to_bytes(4, 'big'))

    if receive_maximum is not None:
        properties.extend([0x21])  # Property identifier for receive maximum
        properties.extend(receive_maximum.to_bytes(2, 'big'))

    if maximum_qos is not None:
        properties.extend([0x24])  # Property identifier for maximum QoS
        properties.append(maximum_qos)

    if retain_available is not None:
        properties.extend([0x25])  # Property identifier for retain available
        properties.append(1 if retain_available else 0)

    if maximum_packet_size is not None:
        properties.extend([0x27])  # Property identifier for maximum packet size
        properties.extend(maximum_packet_size.to_bytes(4, 'big'))

    if assigned_client_identifier is not None:
        properties.extend([0x12])  # Property identifier for assigned client identifier
        identifier_bytes = assigned_client_identifier.encode('utf-8')
        properties.extend(len(identifier_bytes).to_bytes(2, 'big'))
        properties.extend(identifier_bytes)

    if server_keep_alive is not None:
        properties.extend([0x13])  # Property identifier for server keep alive
        properties.extend(server_keep_alive.to_bytes(2, 'big'))

    if response_information is not None:
        properties.extend([0x1A])  # Property identifier for response information
        response_bytes = response_information.encode('utf-8')
        properties.extend(len(response_bytes).to_bytes(2, 'big'))
        properties.extend(response_bytes)

    if server_reference is not None:
        properties.extend([0x1C])  # Property identifier for server reference
        reference_bytes = server_reference.encode('utf-8')
        properties.extend(len(reference_bytes).to_bytes(2, 'big'))
        properties.extend(reference_bytes)

    # Add property length to the start of the properties section
    properties_length = encode_remaining_length(len(properties))
    properties = properties_length + properties

    # Calculate Remaining Length
    remaining_length = len(variable_header) + len(properties)
    fixed_header = bytearray([packet_type]) + encode_remaining_length(remaining_length)

    # Combine Fixed Header, Variable Header, and Properties to form the complete packet
    return fixed_header + variable_header + properties



def create_suback_packet(packet_id, return_codes):
    """
    Creates a SUBACK packet for MQTT v5.

    :param packet_id: The packet identifier from the SUBSCRIBE request.
    :param return_codes: A list of return codes for each topic (QoS levels or failure codes).
    :return: The SUBACK packet as bytes.
    """
    # Fixed header for SUBACK (Packet Type: 9, Flags: 0)
    packet_type = 0x90  # 1001 0000 in binary

    # Variable header: Packet Identifier (2 bytes) + Properties Length (1 byte)
    variable_header = struct.pack("!H", packet_id) + b'\x00'  # Properties Length is 0

    # Payload: Return codes for each topic
    payload = bytes(return_codes)

    # Remaining Length: Length of Variable Header + Payload
    remaining_length = len(variable_header) + len(payload)

    # Construct the Fixed Header with the correct Remaining Length
    fixed_header = struct.pack("!BB", packet_type, remaining_length)

    # Combine all parts to form the SUBACK packet
    suback_packet = fixed_header + variable_header + payload
    return suback_packet


def create_unsuback_packet(packet_id):
    # Packet Type
    packet_type = 0xB0  # UNSUBACK packet type
    variable_header = packet_id.to_bytes(2, 'big')  # Packet Identifier

    # Calculate Remaining Length
    remaining_length = len(variable_header)
    fixed_header = bytearray([packet_type]) + encode_remaining_length(remaining_length)

    return fixed_header + variable_header

def create_pingresp_packet():
    return bytearray([0xD0, 0x00])  # PINGRESP packet type with zero remaining length


def create_disconnect_packet(reason_code=0x00):
    # Packet Type
    packet_type = 0xE0  # DISCONNECT packet type
    variable_header = bytes([reason_code])  # Reason code

    # Calculate Remaining Length
    remaining_length = len(variable_header)
    fixed_header = bytearray([packet_type]) + encode_remaining_length(remaining_length)

    return fixed_header + variable_header

def create_puback_packet(
        packet_id,
        reason_code=0x00,  # Default is Success (0x00)
        reason_string=None,
        user_properties=None
):
    # Packet Type
    packet_type = 0x40  # PUBACK packet type

    # Variable Header (Packet Identifier and Reason Code)
    variable_header = packet_id.to_bytes(2, 'big') + bytes([reason_code])

    # Properties
    properties = bytearray()

    if reason_string is not None:
        properties.extend([0x1F])  # Property identifier for Reason String
        reason_bytes = reason_string.encode('utf-8')
        properties.extend(len(reason_bytes).to_bytes(2, 'big'))
        properties.extend(reason_bytes)

    if user_properties:
        for key, value in user_properties.items():
            properties.extend([0x26])  # Property identifier for User Property
            key_bytes = key.encode('utf-8')
            value_bytes = value.encode('utf-8')
            properties.extend(len(key_bytes).to_bytes(2, 'big'))
            properties.extend(key_bytes)
            properties.extend(len(value_bytes).to_bytes(2, 'big'))
            properties.extend(value_bytes)

    # Add property length to the start of the properties section
    properties_length = encode_remaining_length(len(properties))
    properties = properties_length + properties

    # Calculate Remaining Length
    remaining_length = len(variable_header) + len(properties)
    fixed_header = bytearray([packet_type]) + encode_remaining_length(remaining_length)

    # Combine Fixed Header, Variable Header, and Properties to form the complete packet
    return fixed_header + variable_header + properties

def create_pubrec_packet(packet_id, reason_code=0x00, properties=None):
    # PUBREC packet type (0x50)
    packet_type = 0x50
    variable_header = packet_id.to_bytes(2, 'big') + bytes([reason_code])

    # Properties (optional, MQTT 5.0 feature)
    properties_section = bytearray()
    if properties:
        for key, value in properties.items():
            properties_section.extend(key.encode('utf-8'))
            properties_section.extend(value.encode('utf-8'))

    # Add property length to the properties section if any
    properties_length = encode_remaining_length(len(properties_section))
    properties_section = properties_length + properties_section

    # Calculate Remaining Length
    remaining_length = len(variable_header) + len(properties_section)
    fixed_header = bytearray([packet_type]) + encode_remaining_length(remaining_length)

    # Combine Fixed Header, Variable Header, and Properties to form the complete packet
    return fixed_header + variable_header + properties_section

def create_pubcomp_packet(packet_id, reason_code=0x00, properties=None):
    # PUBCOMP packet type (0x70)
    packet_type = 0x70
    variable_header = packet_id.to_bytes(2, 'big') + bytes([reason_code])

    # Properties (optional, MQTT 5.0 feature)
    properties_section = bytearray()
    if properties:
        for key, value in properties.items():
            properties_section.extend(key.encode('utf-8'))
            properties_section.extend(value.encode('utf-8'))

    # Add property length to the properties section if any
    properties_length = encode_remaining_length(len(properties_section))
    properties_section = properties_length + properties_section

    # Calculate Remaining Length
    remaining_length = len(variable_header) + len(properties_section)
    fixed_header = bytearray([packet_type]) + encode_remaining_length(remaining_length)

    # Combine Fixed Header, Variable Header, and Properties to form the complete packet
    return fixed_header + variable_header + properties_section


def create_publish_packet(topic, payload, qos=0, retain=False, packet_id=None, properties=None, mqtt_version=5):
    """
    Creates a PUBLISH packet according to the MQTT protocol version.

    :param topic: The topic name as a string.
    :param payload: The payload as a string.
    :param qos: The Quality of Service level (0, 1, or 2).
    :param retain: Boolean indicating if the retain flag should be set.
    :param packet_id: Packet identifier for QoS > 0 (default is None for QoS 0).
    :param properties: Optional dictionary of properties for MQTT 5.0.
    :param mqtt_version: The MQTT protocol version (default is 5).
    :return: The PUBLISH packet as a bytearray.
    """
    # Fixed header
    packet_type = 0x30  # PUBLISH packet type
    flags = (qos << 1) | (1 if retain else 0)
    fixed_header = bytearray([packet_type | flags])

    # Variable header: topic name
    topic_encoded = topic.encode('utf-8')
    variable_header = len(topic_encoded).to_bytes(2, 'big') + topic_encoded

    # Packet identifier if QoS > 0
    if qos > 0:
        if packet_id is None:
            raise ValueError("Packet identifier is required for QoS > 0")
        variable_header += packet_id.to_bytes(2, 'big')

    # MQTT 5.0 Properties
    if mqtt_version == 5:
        # Properties
        properties_bytes = bytearray()
        if properties:
            # Add properties handling if needed
            pass

        # Add property length to the variable header
        properties_length = encode_remaining_length(len(properties_bytes))
        variable_header += properties_length + properties_bytes

    # Payload
    payload_encoded = payload.encode('utf-8')

    # Calculate Remaining Length
    remaining_length = len(variable_header) + len(payload_encoded)
    fixed_header += encode_remaining_length(remaining_length)

    # Combine Fixed Header, Variable Header, and Payload
    return fixed_header + variable_header + payload_encoded


def create_pubrel_packet(packet_id):
    """
    Creates a PUBREL packet for MQTT QoS 2 flow.

    :param packet_id: The packet identifier for the PUBREL packet.
    :return: The PUBREL packet as bytes.
    """
    # Fixed header for PUBREL (Type = 6, DUP flag = 0, QoS = 1, RETAIN = 0)
    packet_type = 0b01100010  # Binary: 0110 (PUBREL) + 0010 (QoS 1, flags)
    remaining_length = 2  # Remaining length is always 2 for PUBREL (only includes packet identifier)

    # Variable header: packet identifier (2 bytes)
    variable_header = (
        struct.pack("!H", packet_id))

    # Construct the full PUBREL packet
    pubrel_packet = struct.pack("!BB", packet_type, remaining_length) + variable_header
    return pubrel_packet

