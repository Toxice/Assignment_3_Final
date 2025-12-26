from enum import Enum

class PacketType(Enum):
    PUSH = "PUSH"
    ACK = "ACK"
    FIN = "FIN"
    SYN = "SYN"
    SYNACK = "SYN/ACK"
    FINACK = "FIN/ACK"