class Topic:
    def __init__(self, topic_id, full_path, retained_message=None, retained_qos=0, retained_timestamp=None):
        self.topic_id = topic_id
        self.full_path = full_path
        self.retained_message = retained_message
        self.retained_qos = retained_qos
        self.retained_timestamp = retained_timestamp
        self.subtopics = {}  # In-memory representation for child topics

    def add_subtopic(self, topic):
        self.subtopics[topic.full_path] = topic

    def __repr__(self):
        return f"<Topic full_path={self.full_path} retained={bool(self.retained_message)}>"
