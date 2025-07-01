class Subscription:
    def __init__(self, client_id, topic, qos):
        self.client_id = client_id
        self.topic = topic
        self.qos = qos

    def __repr__(self):
        return f"<Subscription client_id={self.client_id} topic={self.topic} qos={self.qos}>"
