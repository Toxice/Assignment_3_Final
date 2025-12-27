import time
import select
import json
import socket  # <--- Added import
from typing import List
from Network_Packets.packet import DataPacket, AckPacket, PacketType


class Framer:
    def __init__(self, socket_obj, raw_message: str, initial_payload: List[str], window_size: int, msg_size: int,
                 timeout: int, is_dynamic: bool):
        self.socket = socket_obj
        self.raw_message = raw_message
        self.payload = initial_payload

        self.window_size = window_size
        self.msg_size = msg_size
        self.timeout = float(timeout)
        self.is_dynamic = is_dynamic

        self.frame_cursor = 0
        self.sequence_tracker = 0
        self.last_ack_time = time.time()
        self.last_ack_seq = None
        self.dup_ack_count = 0

        # NEW: Track actual byte position in raw message
        self.byte_position = 0

        self.drop_seq = 1
        self._dropped_once = False

    def run_transfer_loop(self):
        print(f"[Framer] Starting transfer of {len(self.payload)} segments...")

        while self.frame_cursor < len(self.payload):
            # 1. SEND
            self._send_available_frames()

            # 2. LISTEN
            readable, _, _ = select.select([self.socket], [], [], self.timeout)
            if readable:
                self._process_incoming_acks()

            # 3. TIMEOUT
            if time.time() - self.last_ack_time > (self.timeout / 1000.0):
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

            # Handle multiple JSON objects stuck together
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

        # FIXED: Use 'socket.timeout' instead of 'self.socket.timeout'
        except (BlockingIOError, socket.timeout):
            pass

    def _handle_ack(self, ack_obj):
        cum_ack = int(ack_obj.ack)

        if cum_ack >= self.frame_cursor:
            # Update byte position for all newly ACKed packets
            for i in range(self.frame_cursor, cum_ack + 1):
                if i < len(self.payload):
                    self.byte_position += len(self.payload[i])

            self.frame_cursor = cum_ack + 1
            self.last_ack_time = time.time()

        # --- DYNAMIC RE-SLICING LOGIC (MOVED AFTER byte_position update) ---
        if self.is_dynamic and ack_obj.new_block_size is not None:
            new_size = int(ack_obj.new_block_size)
            if new_size != self.msg_size:
                print(f"[Framer] Dynamic Update: Changing Message Size {self.msg_size} -> {new_size}")
                self._reslice_payload(new_size)
        # --------------------------------

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
        Uses byte_position tracker which must be updated BEFORE this is called.
        """
        # 1. Get remaining raw text using tracked byte position
        remaining_text = self.raw_message[self.byte_position:]

        # 2. Slice the remaining text with the NEW size
        new_chunks = [remaining_text[i:i + new_chunk_size] for i in range(0, len(remaining_text), new_chunk_size)]

        # 3. Construct new payload list: keep ACKed packets, replace rest
        self.payload = self.payload[:self.frame_cursor] + new_chunks

        # 4. Update state
        self.msg_size = new_chunk_size

        # 5. Reset sequence_tracker to frame_cursor
        self.sequence_tracker = self.frame_cursor

        print(f"[Framer] Re-sliced! Remaining segments count: {len(new_chunks)}, Byte position: {self.byte_position}")

    def _dispatch(self, packet_obj):
        self.socket.sendall(packet_obj.to_bytes())