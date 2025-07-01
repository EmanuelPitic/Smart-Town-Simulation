import usocket as socket
import ustruct as struct
from ubinascii import hexlify

class MQTTException(Exception):
    pass

class MQTTClient:

    def __init__(self, client_id, server, port=0, user=None, password=None, keepalive=0,
                 ssl=False, ssl_params={}):
        if port == 0:
            port = 8883 if ssl else 1883
        self.client_id = client_id
        self.sock = None
        self.server = server
        self.port = port
        self.ssl = ssl
        self.ssl_params = ssl_params
        self.pid = 0
        self.cb = None
        self.user = user
        self.pswd = password
        self.keepalive = keepalive
        self.lw_topic = None
        self.lw_msg = None
        self.lw_qos = 0
        self.lw_retain = False

    def _send_str(self, s):
        self.sock.write(struct.pack("!H", len(s)))
        self.sock.write(s)

    def _recv_len(self):
        n = 0
        sh = 0
        while 1:
            b = self.sock.read(1)[0]
            n |= (b & 0x7f) << sh
            if not b & 0x80:
                return n
            sh += 7

    def set_callback(self, f):
        self.cb = f

    def set_last_will(self, topic, msg, retain=False, qos=0):
        assert 0 <= qos <= 2
        assert topic
        self.lw_topic = topic
        self.lw_msg = msg
        self.lw_qos = qos
        self.lw_retain = retain

    def connect(self, clean_start=True):
        self.sock = socket.socket()
        addr = socket.getaddrinfo(self.server, self.port)[0][-1]
        self.sock.connect(addr)

        if self.ssl:
            import ussl
            self.sock = ussl.wrap_socket(self.sock, **self.ssl_params)

        # === MQTT v5: Variable Header ===
        msg = bytearray(b"\x00\x04MQTT\x05")  # Protocol Name + Protocol Level 5

        connect_flags = 0
        if clean_start:
            connect_flags |= 0x02  # Clean Start
        connect_flags |= 0x80  # Username Flag (bit 7) set

        msg.append(connect_flags)
        msg.append(self.keepalive >> 8 if self.keepalive else 0x00)  # Keep Alive MSB
        msg.append(self.keepalive & 0xFF if self.keepalive else 0x00)  # Keep Alive LSB

        msg.append(0x00)  # Property Length = 0 (no properties)

        # === Payload ===
        # Client ID
        client_id_bytes = self.client_id.encode('utf-8')
        msg.append(0x00)
        msg.append(len(client_id_bytes))  # length MSB+LSB
        msg.extend(client_id_bytes)

        # Username (same as client_id)
        msg.append(0x00)
        msg.append(len(client_id_bytes))
        msg.extend(client_id_bytes)

        # === Fixed Header ===
        packet = bytearray()
        packet.append(0x10)  # CONNECT packet type

        remaining_length = len(msg)
        while True:
            encoded_byte = remaining_length % 128
            remaining_length //= 128
            if remaining_length > 0:
                encoded_byte |= 0x80
            packet.append(encoded_byte)
            if remaining_length == 0:
                break

        # === Send full CONNECT packet ===
        self.sock.write(packet + msg)

        # === Receive CONNACK ===
        resp = self.sock.read(4)
        assert resp[0] == 0x20 and resp[1] == 0x03
        if resp[3] != 0:
            raise MQTTException(resp[3])
        return resp[2] & 0x01  # Session Present



    def disconnect(self):
        self.sock.write(b"\xe0\0")
        self.sock.close()

    def ping(self):
        self.sock.write(b"\xc0\0")

    import struct

    def publish(self, topic, msg, retain=False, qos=0):
        """
        Publică un pachet MQTT PUBLISH într-o singură scriere de socket,
        fără apeluri multiple la sock.write().
        """
        # --- 1. Construcția byte de control (Fixed Header byte 1) ---
        first_byte = 0x30  # PUBLISH, QoS=0, DUP=0, RETAIN=0 inițial
        first_byte |= (qos << 1) | (1 if retain else 0)

        # --- 2. Topic și payload sub formă de bytes ---
        if isinstance(topic, str):
            topic_bytes = topic.encode("utf-8")
        else:
            # presupunem deja bytes
            topic_bytes = topic

        if isinstance(msg, str):
            msg_bytes = msg.encode("utf-8")
        else:
            # presupunem deja bytes
            msg_bytes = msg

        # --- 3. Calcul Remaining Length ---
        #   2 octeți pentru lungimea topic-ului + len(topic_bytes)
        #   + (2 octeți pentru Packet Identifier dacă QoS > 0)
        #   + 1 octet pentru Property Length (aici 0)
        #   + len(payload)
        rem_len = 2 + len(topic_bytes)
        if qos > 0:
            rem_len += 2
        rem_len += 1
        rem_len += len(msg_bytes)

        assert rem_len < 2097152  # MQTT varint max

        # --- 4. Encodarea Remaining Length (varint) ---
        rl_bytes = bytearray()
        x = rem_len
        while x > 0x7F:
            rl_bytes.append((x & 0x7F) | 0x80)
            x >>= 7
        rl_bytes.append(x)

        # --- 5. Construirea completă a pachetului în memorie ---
        packet = bytearray()
        packet.append(first_byte)        # Fixed header byte 1
        packet.extend(rl_bytes)          # Remaining Length (varint)

        # 5.a. Topic Name: 2 octeți de lungime + octeții topic-ului
        packet.extend(struct.pack("!H", len(topic_bytes)))
        packet.extend(topic_bytes)

        # 5.b. Packet Identifier (dacă QoS > 0)
        if qos > 0:
            self.pid = (self.pid + 1) & 0xFFFF or 1
            packet.extend(struct.pack("!H", self.pid))

        # 5.c. Property Length (aici zero, deci un singur octet 0x00)
        packet.append(0x00)

        # 5.d. Payload
        packet.extend(msg_bytes)

        # --- 6. Write în socket o singură dată ---
        self.sock.write(packet)

        # --- 7. Pentru QoS=1: așteptăm PUBACK ---
        if qos == 1:
            while True:
                op = self.wait_msg()
                if op == 0x40:  # PUBACK
                    sz = self.sock.read(1)
                    assert sz == b"\x02"
                    rcv_pid = self.sock.read(2)
                    rcv_pid = (rcv_pid[0] << 8) | rcv_pid[1]
                    if rcv_pid == self.pid:
                        return
        elif qos == 2:
            raise NotImplementedError("QoS 2 not supported yet")



    def subscribe(self):
        self.sock.write(b'\x82\x14\x00\x01\x00\x00\x0eTrafficLight_1\x01')
        # assert self.cb is not None, "Subscribe callback is not set"
        # assert qos in (0, 1, 2), "Invalid QoS"

        # # 1) UTF-8–encode the topic filter using the class’s utf8_encode
        # topic_bytes = self.utf8_encode(topic)
        # topic_len = len(topic_bytes)

        # # 2) Increment Packet Identifier
        # self.pid += 1
        # pid_bytes = self.pid.to_bytes(2, "big")  # 2 bytes, big-endian

        # # 3) Compute “payload length” (variable header + payload):
        # #    - 2 bytes for Packet Identifier
        # #    - 2 bytes for Topic Length + N bytes of topic
        # #    - 1 byte  for Subscription Options (just QoS here)
        # payload_len = 2 + (2 + topic_len) + 1  # = 5 + len(topic)

        # # 4) Encode Remaining Length (base-128, up to 4 bytes)
        # def _encode_remaining_length(x):
        #     encoded = bytearray()
        #     while True:
        #         digit = x & 0x7F
        #         x >>= 7
        #         if x > 0:
        #             digit |= 0x80
        #         encoded.append(digit)
        #         if x == 0:
        #             break
        #     return encoded

        # remaining_length_bytes = _encode_remaining_length(payload_len)

        # # 5) Build the full SUBSCRIBE packet in one bytearray:
        # packet = bytearray()
        # packet.append(0x82)                       # SUBSCRIBE fixed header (type=8, flags=0010)
        # packet.extend(remaining_length_bytes)     # Remaining Length
        # packet.extend(pid_bytes)                  # Packet Identifier
        # packet.extend(topic_len.to_bytes(2, "big"))  # Topic length MSB+LSB
        # packet.extend(topic_bytes)                # Topic UTF-8 bytes
        # packet.append(qos & 0x03)                 # Subscription Options (QoS in low 2 bits)

        # # 6) Send the entire packet in one write()
        # self.sock.write(packet)

        # # 7) Wait for SUBACK (0x90), then read its 4-byte header (Remaining Length + Packet ID + return code)
        # while True:
        #     op = self.wait_msg()
        #     if op == 0x90:
        #         # Read the next 4 bytes: [Remaining Length=0x03][PID MSB][PID LSB][Return Code]
        #         resp = self.sock.read(4)
        #         # resp[1:3] is the Packet Identifier from the broker
        #         assert resp[1] == pid_bytes[0] and resp[2] == pid_bytes[1], \
        #             "PID mismatch: sent %s, got %s" % (pid_bytes.hex(), resp[1:3].hex())
        #         if resp[3] == 0x80:
        #             raise MQTTException("Subscription failed (return code 0x80)")
        #         return


    # Wait for a single incoming MQTT message and process it.
    # Subscribed messages are delivered to a callback previously
    # set by .set_callback() method. Other (internal) MQTT
    # messages processed internally.
    def wait_msg(self):
        res = self.sock.read(1)
        self.sock.setblocking(True)
        if res is None:
            return None
        if res == b"":
            raise OSError(-1)
        if res == b"\xd0":  # PINGRESP
            sz = self.sock.read(1)[0]
            assert sz == 0
            return None
        op = res[0]
        if op & 0xf0 != 0x30:
            return op
        sz = self._recv_len()
        topic_len = self.sock.read(2)
        topic_len = (topic_len[0] << 8) | topic_len[1]
        topic = self.sock.read(topic_len)
        sz -= topic_len + 2
        if op & 6:
            pid = self.sock.read(2)
            pid = pid[0] << 8 | pid[1]
            sz -= 2
        msg = self.sock.read(sz)
        self.cb(topic, msg)
        if op & 6 == 2:
            pkt = bytearray(b"\x40\x02\0\0")
            struct.pack_into("!H", pkt, 2, pid)
            self.sock.write(pkt)
        elif op & 6 == 4:
            assert 0

    # Checks whether a pending message from server is available.
    # If not, returns immediately with None. Otherwise, does
    # the same processing as wait_msg.
    def check_msg(self):
        self.sock.setblocking(False)
        return self.wait_msg()
    
    def wait_msg_nonblocking(self):
        self.sock.setblocking(False)
        try:
            res = self.sock.read(1)
        except OSError:
            # Nu sunt date disponibile acum, deci returnăm None fără să blocăm
            return None

        if res is None or res == b"":
            return None

        if res == b"\xd0":  # PINGRESP
            sz = self.sock.read(1)[0]
            assert sz == 0
            return None

        op = res[0]
        if op & 0xf0 != 0x30:
            return op

        sz = self._recv_len()
        topic_len = self.sock.read(2)
        topic_len = (topic_len[0] << 8) | topic_len[1]
        topic = self.sock.read(topic_len)
        sz -= topic_len + 2

        if op & 6:
            pid = self.sock.read(2)
            pid = pid[0] << 8 | pid[1]
            sz -= 2

        msg = self.sock.read(sz)
        self.cb(topic, msg)

        if op & 6 == 2:
            pkt = bytearray(b"\x40\x02\0\0")
            struct.pack_into("!H", pkt, 2, pid)
            self.sock.write(pkt)
        elif op & 6 == 4:
            assert 0

        return True  # Sau orice altceva pentru a semnala că a venit mesaj

