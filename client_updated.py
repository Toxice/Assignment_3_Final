import socket
import json
import sys
from typing import List

from Utils.configuration import ConnectionConfig
from Utils.config_writer import FileConfiger
from Utils.file_handler import FileHandler
from Network_Packets.packet import HandshakePacket, AckPacket, FinPacket, PacketType
from Network_Packets.window_framer import Framer


class DataEmitter:
    def __init__(self, config_loc: str, target_ip: str = "127.0.0.1", target_socket: int = 5555):
        raw_handler = FileHandler(config_loc)
        # Store raw filename and text for later
        self.msg_source = raw_handler.get_message()
        self.raw_text_content = ""

        self.net_params = ConnectionConfig(config_loc)
        self.dest_addr = target_ip
        self.dest_port = target_socket
        self.link_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        self.proposed_window = self.net_params.get_window_size()
        self.proposed_msg_size = self.net_params.get_message_size()
        self.proposed_timeout = self.net_params.get_timeout()
        self.proposed_dynamic = self.net_params.get_is_dynamic()

        self.effective_window = 0
        self.effective_msg_size = 0
        self.effective_timeout = 0
        self.effective_dynamic = False
        self.payload_segments = []

    def _harvest_and_slice(self, chunk_cap: int) -> List[str]:
        try:
            with open(self.msg_source, 'r') as f_obj:
                self.raw_text_content = f_obj.read()
            return [self.raw_text_content[i:i + chunk_cap] for i in range(0, len(self.raw_text_content), chunk_cap)]
        except FileNotFoundError:
            print(f"Critical: Source file {self.msg_source} missing.")
            sys.exit(1)

    def _dispatch_unit(self, packet_obj) -> None:
        self.link_socket.sendall(packet_obj.to_bytes())

    def _await_specific_packet(self, expected_flag: PacketType):
        self.link_socket.settimeout(None)
        accumulator = ""
        while True:
            raw_bytes = self.link_socket.recv(4096).decode('utf-8')
            if not raw_bytes: continue
            accumulator += raw_bytes
            while "\n" in accumulator:
                line_data, accumulator = accumulator.split("\n", 1)
                try:
                    p_map = json.loads(line_data)
                    if p_map.get("flag") == expected_flag.value:
                        return p_map
                except json.JSONDecodeError:
                    continue

    def initiate_link(self):
        print("[Emitter] Dialing target...")
        self.link_socket.connect((self.dest_addr, self.dest_port))

        syn = HandshakePacket(PacketType.SYN, self.proposed_window, self.proposed_msg_size, self.proposed_timeout,
                              self.proposed_dynamic)
        self._dispatch_unit(syn)
        print("[Emitter] Sent SYN.")

        synack = self._await_specific_packet(PacketType.SYNACK)
        print("[Emitter] Received SYN/ACK.")

        server_win = int(synack.get("window_size", self.proposed_window))
        server_msg = int(synack.get("maximum_msg_size", self.proposed_msg_size))
        server_to = int(synack.get("timeout", self.proposed_timeout))
        server_dyn = bool(synack.get("dynamic_size", self.proposed_dynamic))

        self.effective_window = min(self.proposed_window, server_win)
        self.effective_msg_size = min(self.proposed_msg_size, server_msg)
        self.effective_timeout = min(self.proposed_timeout, server_to)
        self.effective_dynamic = self.proposed_dynamic and server_dyn

        print(
            f"[Emitter] Negotiated: Win={self.effective_window}, Msg={self.effective_msg_size}, Timeout={self.effective_timeout}, Dyn={self.effective_dynamic}")

        self.payload_segments = self._harvest_and_slice(self.effective_msg_size)

        self._dispatch_unit(AckPacket(PacketType.ACK, 0))
        print("[Emitter] Connection Established.")

    def execute_transfer(self):
        print("[Emitter] Handing over control to Framer...")
        # PASS RAW TEXT CONTENT HERE
        transfer_agent = Framer(
            self.link_socket,
            self.raw_text_content,  # New Argument
            self.payload_segments,
            self.effective_window,
            self.effective_msg_size,
            self.effective_timeout,
           self.effective_dynamic
        )
        transfer_agent.run_transfer_loop()
        print("[Emitter] Transfer complete.")

    def terminate_link(self):
        print("[Emitter] Initiating Teardown.")
        self._dispatch_unit(FinPacket(PacketType.FIN))
        self._await_specific_packet(PacketType.FINACK)
        self._dispatch_unit(AckPacket(PacketType.ACK, 0))
        print("[Emitter] Closed.")
        self.link_socket.close()


if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("Choose mode:")
    print(" 1. config from file (default)")
    print(" 2. config manually")
    print("=" * 50)
    choice = input("Enter choice (file/manual): ").strip()

    if choice == "manual":
        try:
            m_size = int(input("Msg Size: "))
            w_size = int(input("Window Size: "))
            tout = int(input("Timeout: "))
            is_dyn = input("Dynamic (True/False): ")
            manual_config = FileConfiger("message.txt", m_size, w_size, tout, is_dyn)
            path = manual_config.get_new_config()
        except ValueError:
            print("Invalid input, using default.")
            path = "config.txt"
    else:
        path = "config.txt"

    node = DataEmitter(path)
    node.initiate_link()
    node.execute_transfer()
    node.terminate_link()