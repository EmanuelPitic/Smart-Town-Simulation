class Client:
    def __init__(self, client_id, username=None, password=None, clean_session=True, keep_alive=60, session_expiry=0, isLastWill=0):
        self.client_id = client_id
        self.username = username
        self.password = password
        self.clean_session = clean_session
        self.keep_alive = keep_alive
        self.session_expiry = session_expiry
        self.connected = False
        self.last_seen = None
        self.isLastWill = isLastWill

        #self.subscriptions = {}  # {topic: qos}

    def __repr__(self):
        return f"<Client client_id={self.client_id} connected={self.connected}>"
