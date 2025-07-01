class WillMessage:
    def __init__(self, client_id, topic, message, qos=0, retain=False, registered_at=None):
        self.client_id = client_id
        self.topic = topic
        self.message = message
        self.qos = qos
        self.retain = retain
        self.registered_at = registered_at  # Optional: Timestamp when the will was registered
        self.sent = False  # Optional: Flag to indicate if the will message has been sent

    def __repr__(self):
        return f"<WillMessage client_id={self.client_id} topic={self.topic}>"
