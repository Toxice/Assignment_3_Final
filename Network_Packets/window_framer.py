import time
import select
import json
from typing import List
from Network_Packets.packet import DataPacket, AckPacket, PacketType


class Framer:
    def __init__(self, socket_obj, raw_message: str, initial_payload: List[str], window_size: int, msg_size: int,
                 timeout: int, is_dynamic: bool):
        self.socket = socket_obj
        self.raw_message = raw_message  # Keep full text to allow re-slicing
        self.payload = initial_payload

        self.window_size = window_size
        self.msg_size = msg_size
        self.timeout = timeout
        self.is_dynamic = is_dynamic

        self.frame_cursor = 0
        self.sequence_tracker = 0
        self.last_ack_time = time.time()
        self.last_ack_seq = None
        self.dup_ack_count = 0

        self.drop_seq = 1
        self._dropped_once = False

    def run_transfer_loop(self):
        print(f"[Framer] Starting transfer of {len(self.payload)} segments...")

        while self.frame_cursor < len(self.payload):
            # 1. SEND
            self._send_available_frames()

            # 2. LISTEN
            readable, _, _ = select.select([self.socket], [], [], 0.1)
            if readable:
                self._process_incoming_acks()

            # 3. TIMEOUT
            if time.time() - self.last_ack_time > self.timeout:
                print(f"[Framer] TIMEOUT! Retransmitting from base {self.frame_cursor}")
                # Reset tracker to base to re-send the whole window
                self.sequence_tracker = self.frame_cursor
                self.last_ack_time = time.time()

    def _send_available_frames(self):
        """Sends packets within the window that haven't been sent yet."""
        upper_bound = min(self.frame_cursor + self.window_size, len(self.payload))

        while self.sequence_tracker < upper_bound:
            idx = self.sequence_tracker

            # Demo Drop Logic (Drops packet #1 exactly once)
            if (not self._dropped_once) and idx == self.drop_seq:
                self._dropped_once = True
                print(f"[Framer] *** SIMULATING DROP: Segment {idx} ***")
                self.sequence_tracker += 1
                continue

            seg_pkt = DataPacket(PacketType.PUSH, idx, self.payload[idx])
            self._dispatch(seg_pkt)
            print(f"[Framer] Pushed Segment {idx} (Msg Size: {len(self.payload[idx])})")
            self.sequence_tracker += 1

    def _process_incoming_acks(self):
        try:
            chunk = self.socket.recv(4096).decode('utf-8')
            if not chunk: return

            # Handle multiple JSON objects stuck together (e.g. "}{")
            # We assume your Packet.to_bytes() adds a newline "\n" at the end
            messages = chunk.split('\n')

            for msg in messages:
                if not msg.strip(): continue
                try:
                    p_dict = json.loads(msg)
                except json.JSONDecodeError:
                    continue

                if p_dict.get('flag') == PacketType.ACK.value:
                    ack_obj = AckPacket.json_to_packet(p_dict)
                    self._handle_ack(ack_obj)
        except (BlockingIOError, self.socket.timeout):
            pass

    def _handle_ack(self, ack_obj):
        cum_ack = int(ack_obj.ack)

        # --- DYNAMIC RE-SLICING LOGIC ---
        # If server requested a new block size, we re-slice the remaining text
        if self.is_dynamic and ack_obj.new_block_size is not None:
            new_size = int(ack_obj.new_block_size)
            if new_size != self.msg_size:
                print(f"[Framer] Dynamic Update: Changing Message Size {self.msg_size} -> {new_size}")
                self._reslice_payload(new_size)
        # --------------------------------

        # Slide Window
        if cum_ack >= self.frame_cursor:
            self.frame_cursor = cum_ack + 1
            self.last_ack_time = time.time()

        # Fast Retransmit Logic
        if self.last_ack_seq == cum_ack:
            self.dup_ack_count += 1
        else:
            self.last_ack_seq = cum_ack
            self.dup_ack_count = 1

        if self.dup_ack_count >= 3:
            print(f"[Framer] Fast Retransmit Triggered for Segment {self.frame_cursor}")
            missing = self.frame_cursor
            if missing < len(self.payload):
                pkt = DataPacket(PacketType.PUSH, missing, self.payload[missing])
                self._dispatch(pkt)
                self.dup_ack_count = 0

    def _reslice_payload(self, new_chunk_size):
        """
        Re-calculates the payload list based on the new chunk size.
        Only re-slices the data that hasn't been ACKed yet.
        """
        # 1. Calculate how much text was already ACKed (sent successfully)
        # We sum the lengths of packets 0 to frame_cursor-1
        finished_text_len = sum(len(segment) for segment in self.payload[:self.frame_cursor])

        # 2. Get the remaining raw text
        remaining_text = self.raw_message[finished_text_len:]

        # 3. Slice the remaining text with the NEW size
        new_chunks = [remaining_text[i:i + new_chunk_size] for i in range(0, len(remaining_text), new_chunk_size)]

        # 4. Construct new payload list: [Old Packet 0, Old Packet 1, ... New Packet X, New Packet Y]
        self.payload = self.payload[:self.frame_cursor] + new_chunks

        # 5. Update state
        self.msg_size = new_chunk_size

        # 6. Reset sequence_tracker to frame_cursor
        # We must re-send the current window because the packet at 'frame_cursor'
        # has likely changed its content (it's now a different slice).
        self.sequence_tracker = self.frame_cursor

        print(f"[Framer] Re-sliced! Remaining segments count: {len(new_chunks)}")

    def _dispatch(self, packet_obj):
        self.socket.sendall(packet_obj.to_bytes())