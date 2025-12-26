class FileConfiger:
    def __init__(self, message, maximum_msg_size, window_size, timeout, dynamic_message_size):
        with open("manual_config.txt", "w") as f:
            f.write(f"message: {message}\n")
            f.write(f"maximum_msg_size: {maximum_msg_size}\n")
            f.write(f"window_size: {window_size}\n")
            f.write(f"timeout: {timeout}\n")
            f.write(f"dynamic_message_size: {dynamic_message_size}\n")
    @staticmethod
    def get_new_config() -> str:
        return "manual_config.txt"