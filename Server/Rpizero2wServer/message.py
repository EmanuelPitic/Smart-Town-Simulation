class Message:
    def __init__(self, topic, payload, qos, packet_id: int = None, retain=False,  published_at=None):
        self.topic = topic
        self.payload = payload
        self.qos = qos
        self.retain = retain
        self.packet_id = packet_id
        self.published_at = published_at  # Optional: Timestamp when the message was published
        self.message_id = None  # Optional: Unique identifier for the message
        self.delivered = False  # Optional: Delivery status for the message

    def __repr__(self):
        return f"<Message topic={self.topic} qos={self.qos} retain={self.retain}>"
