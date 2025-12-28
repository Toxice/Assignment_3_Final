Reliable JSON Transfer Protocol (RJTP)
A Python implementation of a reliable, TCP-like data transfer protocol running on top of standard sockets. This project simulates core networking concepts—including sliding windows, flow control, fast retransmit, and connection handshakes—using JSON-formatted packets.

🚀 Features
Reliable Data Transfer: Ensures data delivery using Sequence Numbers and Acknowledgments (ACKs).

3-Way Handshake: Establishes connections using SYN, SYN/ACK, and ACK packets.

Sliding Window Protocol: Implements a sender-side window to manage in-flight packets for efficiency.

Congestion & Error Control:

Timeout Retransmission: Automatically resends the window if an ACK isn't received in time.

Fast Retransmit: Detects packet loss via triple duplicate ACKs and resends the missing segment immediately.

Dynamic Message Sizing: A unique feature where the receiver (Server) can instruct the sender (Client) to resize the message chunks mid-transmission.

Graceful Teardown: Closes connections cleanly using FIN/ACK packets.

📂 Project Structure
To run this code successfully, ensure your directory structure matches the Python imports:

Plaintext
```
.
├── client.py                # Entry point for the sender
├── server.py                # Entry point for the receiver
├── config.txt               # Configuration file (created by user)
├── Network_Packets/         # Package for packet logic
│   ├── __init__.py
│   ├── packet.py            # Abstract and concrete Packet classes
│   ├── packet_type.py       # Enums for packet flags (SYN, PUSH, etc.)
│   └── window_framer.py     # Core sliding window logic
└── Utils/                   # Package for utility scripts
    ├── __init__.py
    ├── configuration.py     # Parses config settings
    ├── config_writer.py     # Writes manual configs
    └── file_handler.py      # Reads raw file data
```
⚙️ Configuration
The system uses a configuration file (default config.txt) to set protocol parameters.

Format (config.txt):

Plaintext
```
message: path/to/source_file.txt
maximum_msg_size: 15
window_size: 5
timeout: 2000
dynamic_message_size: True
message: Path to the text file you want to send.
```
maximum_msg_size: Size of the payload (in characters/bytes) per packet.

window_size: Number of unacknowledged packets allowed in flight.

timeout: Time (in milliseconds) before retransmission.

dynamic_message_size: True/False. If True, the server may request chunk size changes.

🔧 Installation & Usage
1. Prerequisites
Python 3.x

No external pip dependencies required (uses standard socket, json, select, time).

2. Setup
Create the required source file (the message to be sent):

Bash

echo "This is a test message to simulate TCP transfer." > message.txt
3. Running the Server
Start the receiver first. It will listen for incoming connections.

Bash
```
python server.py -port 5555
```
Note: Port defaults to 5555 if not specified.

4. Running the Client
Start the sender in a separate terminal.

Bash
```
python client.py
```
Follow the on-screen prompts:

Config from file: Loads settings from config.txt.

Config manually: Allows you to type parameters (Window Size, Timeout, etc.) in the terminal.

🧠 Technical Details
Packet Structure
All data is transferred as JSON strings terminated by a newline (\n).

Example Data Packet (PUSH):

JSON
```jsonc
{
  "flag": "PUSH",
  "sequence": 1,
  "payload": "Hello World"
}
```
Example ACK Packet:

JSON
```jsonc
{
  "flag": "ACK",
  "ack": 2,
  "new_block_size": 10
}
```
The Dynamic Sizing Feature
One of the advanced features of this implementation is the ability to handle Dynamic Payload Resizing.

The server.py randomly decides to change the block size (e.g., to simulate changing network conditions).

It attaches a new_block_size field to an ACK packet.

The window_framer.py on the client receives this, calculates the remaining raw text, and re-slices the remaining payload into new chunk sizes on the fly.

🤝 Contributing
Feel free to fork this project and submit pull requests. Suggestions for implementing congestion control (like TCP Tahoe/Reno) are welcome.

Internal Reasoning for the User: I have organized the README to highlight the "Dynamic Sizing" feature, as that is the most complex and unique part of your implementation. I also inferred the directory structure (Network_Packets and Utils) based on the import statements found in client.py, as the code will not run without those folders existing.
