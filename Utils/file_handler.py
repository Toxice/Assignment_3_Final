class FileHandler:
    def __init__(self, path: str):
        self.path = path
        self.data = dict()

        with open(self.path, 'r') as f:
            for line in f:
                key, value = line.strip().split(": ")
                self.data[key] = value  # or int(value) if needed

    def get_window_size(self):
        return int(self.data.get("window_size"))

    def get_timeout(self):
        return int(self.data.get("timeout"))

    def get_message_size(self):
        return int(self.data.get("maximum_msg_size"))

    def get_dynamic_state(self):
        return bool(self.data.get("dynamic_message_size"))

    def get_message(self) -> str:
        return str(self.data.get("message"))
