import socket
import json
import argparse
import random

from Utils.configuration import ConnectionConfig
from Network_Packets.packet import HandshakePacket, DataPacket, AckPacket, FinPacket, PacketType


class DataCollector:
    def __init__(self, bind_ip: str, bind_port: int, config_loc: str = "config.txt"):
        self.srv_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.srv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.srv_sock.bind((bind_ip, bind_port))
        self.packet_store = {}
        self.next_needed = 0
        self.incoming_buff = ""
        self.config_loc = config_loc
        self.negotiated = None
        self.server_cfg = ConnectionConfig(config_loc)

    @staticmethod
    def _transmit(conn_handle, pkt_obj):
        conn_handle.sendall(pkt_obj.to_bytes())

    def start_service(self):
        self.srv_sock.listen(1)
        print(f"[Collector] Listening on port {self.srv_sock.getsockname()[1]}...")
        while True:
            client_conn, origin = self.srv_sock.accept()
            print(f"[Collector] Accepted link from {origin}")
            self._manage_session(client_conn)

    def _manage_session(self, active_conn):
        session_active = True
        self.packet_store.clear()
        self.next_needed = 0
        self.incoming_buff = ""
        while session_active:
            try:
                raw_input = active_conn.recv(1024).decode('utf-8')
                if not raw_input: break
                self.incoming_buff += raw_input
                while "\n" in self.incoming_buff:
                    json_str, self.incoming_buff = self.incoming_buff.split("\n", 1)
                    if not json_str.strip(): continue
                    try:
                        p_data = json.loads(json_str)
                        session_active = self._route_logic(p_data, active_conn)
                    except json.JSONDecodeError:
                        pass
            except socket.error:
                break
        active_conn.close()
        print("[Collector] Session Closed.")
        full_text = "".join([self.packet_store[k] for k in sorted(self.packet_store)])
        print(f"\n[OUTPUT] Reconstructed Data: {full_text}\n")

    def _route_logic(self, p_map: dict, conn) -> bool:
        p_type = p_map.get("flag")

        if p_type == PacketType.SYN.value:
            print("[Collector] SYN received.")
            client_syn = HandshakePacket.json_to_packet(p_map)

            if self.server_cfg:
                s_win = int(self.server_cfg.get_window_size())
                s_msg = int(self.server_cfg.get_message_size())
                s_timeout = int(self.server_cfg.get_timeout())
                s_dyn = bool(self.server_cfg.get_is_dynamic())
            else:
                s_win, s_msg, s_timeout, s_dyn = client_syn.window, client_syn.maximum_message_size, client_syn.timeout, client_syn.dynamic

            self.negotiated = {
                "window_size": min(client_syn.window, s_win),
                "maximum_msg_size": min(client_syn.maximum_message_size, s_msg),
                "timeout": min(client_syn.timeout, s_timeout),
                "dynamic_size": client_syn.dynamic and s_dyn,
            }
            print(f"[Collector] Negotiated Config: {self.negotiated}")
            reply = HandshakePacket(PacketType.SYNACK, s_win, s_msg, s_timeout, s_dyn)
            self._transmit(conn, reply)
            return True

        elif p_type == PacketType.ACK.value and not self.packet_store:
            print("[Collector] Handshake ACK received.")
            return True

        elif p_type == PacketType.PUSH.value:
            data_pkt = DataPacket.json_to_packet(p_map)
            seq = data_pkt.sequence
            print(f"[Collector] Got PUSH {seq}")

            if seq == self.next_needed:
                self.packet_store[seq] = data_pkt.payload
                self.next_needed += 1
                while self.next_needed in self.packet_store:
                    self.next_needed += 1
            elif seq > self.next_needed:
                self.packet_store[seq] = data_pkt.payload

            ack_val = max(0, self.next_needed - 1)

            # --- DYNAMIC MESSAGE SIZE LOGIC ---
            update_msg_size = None
            if self.negotiated and self.negotiated["dynamic_size"]:
                # Trigger change periodically (e.g. every 3rd packet)
                if seq % 3 == 0:
                    # Random message size between 5 and 20
                    update_msg_size = random.randint(5, 20)
                    print(f"[Collector] Dynamic Config: Requesting new Msg Size -> {update_msg_size}")

            ack_reply = AckPacket(PacketType.ACK, ack_val, new_block_size=update_msg_size)
            self._transmit(conn, ack_reply)
            return True

        elif p_type == PacketType.FIN.value:
            print("[Collector] FIN received.")
            self._transmit(conn, FinPacket(PacketType.FINACK))
            buff = ""
            while True:
                try:
                    d = conn.recv(1024).decode('utf-8')
                    if not d: break
                    buff += d
                    if "ACK" in buff or str(PacketType.ACK.value) in buff: break
                except:
                    break
            print("[Collector] Final ACK received.")
            return False

        return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-host", type=str, default="127.0.0.1")
    parser.add_argument("-port", type=int, default=5555)
    args = parser.parse_args()
    srv = DataCollector(args.host, args.port)
    srv.start_service()