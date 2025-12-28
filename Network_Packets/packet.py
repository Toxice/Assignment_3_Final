from abc import ABC, abstractmethod
import json
from Network_Packets.packet_type import PacketType

class Packet(ABC):
    def __init__(self, flag: PacketType):
        self.flag = flag

    @abstractmethod
    def return_dict(self) -> dict:
        pass

    @abstractmethod
    def to_bytes(self) -> bytes:
        pass

class HandshakePacket(Packet):
    def __init__(self, flag: PacketType, window: int, maximum_message_size: int, timeout: int, dynamic_size: bool):
        super().__init__(flag)
        self.window = int(window)
        self.maximum_message_size = int(maximum_message_size)
        self.timeout = int(timeout)
        self.dynamic = bool(dynamic_size)

    def return_dict(self) -> dict:
        return {
            "flag": self.flag.value if isinstance(self.flag, PacketType) else self.flag,
            "window_size": self.window,
            "maximum_msg_size": self.maximum_message_size,
            "timeout": self.timeout,
            "dynamic_size": self.dynamic
        }

    def to_bytes(self) -> bytes:
        return (json.dumps(self.return_dict()) + "\n").encode('utf-8')

    @staticmethod
    def json_to_packet(json_dict: dict):
        return HandshakePacket(
            json_dict.get('flag'),
            json_dict.get('window_size'),
            json_dict.get('maximum_msg_size'),
            json_dict.get('timeout'),
            json_dict.get('dynamic_size')
        )

class HandshakeAckPacket(Packet):
    def __init__(self, flag: PacketType):
        super().__init__(flag)

    def return_dict(self) -> dict:
        data = {
            "flag": self.flag.value
        }
        return data

    def to_bytes(self) -> bytes:
        return (json.dumps(self.return_dict()) + "\n").encode('utf-8')

    @staticmethod
    def json_to_packet(json_dict: dict):
        return HandshakeAckPacket(
            json_dict.get('flag')
        )

class DataPacket(Packet):
    def __init__(self, flag: PacketType, sequence: int, payload: str):
        super().__init__(flag)
        self.sequence = sequence
        self.payload = payload

    def __lt__(self, other):
        return self.sequence < other.sequence

    def __gt__(self, other):
        return self.sequence > other.sequence

    def __eq__(self, other):
        return self.sequence == other.sequence

    def return_dict(self) -> dict:
        return {
            "flag": self.flag.value if isinstance(self.flag, PacketType) else self.flag,
            "sequence": self.sequence,
            "payload": self.payload
        }

    def to_bytes(self) -> bytes:
        return (json.dumps(self.return_dict()) + "\n").encode('utf-8')

    @staticmethod
    def json_to_packet(json_dict: dict):
        return DataPacket(json_dict.get('flag'), json_dict.get('sequence'), json_dict.get('payload'))

class AckPacket(Packet):
    def __init__(self, flag: PacketType, ack: int, new_block_size: int = None):
        super().__init__(flag)
        self.ack = ack
        self.new_block_size = new_block_size

    def return_dict(self) -> dict:
        data = {
            "flag": self.flag.value if isinstance(self.flag, PacketType) else self.flag,
            "ack": self.ack
        }
        if self.new_block_size is not None:
            data["new_block_size"] = self.new_block_size
        return data

    def to_bytes(self) -> bytes:
        return (json.dumps(self.return_dict()) + "\n").encode('utf-8')

    @staticmethod
    def json_to_packet(json_dict: dict):
        return AckPacket(
            json_dict.get('flag'),
            json_dict.get('ack'),
            json_dict.get('new_block_size') # Changed key
        )

class FinPacket(Packet):
    def __init__(self, flag: PacketType):
        super().__init__(flag)

    def return_dict(self) -> dict:
        return {"flag": self.flag.value if isinstance(self.flag, PacketType) else self.flag}

    def to_bytes(self) -> bytes:
        return (json.dumps(self.return_dict()) + "\n").encode('utf-8')