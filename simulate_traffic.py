import socket
import struct
import time
import random

def simulate_traffic(interface="vcan0", can_id=0x123, interval=0.01):
    """
    Simulates a CAN sender with slight 'Smart Attacker' jitter.
    """
    # Create raw CAN socket
    sock = socket.socket(socket.PF_CAN, socket.SOCK_RAW, socket.CAN_RAW)
    try:
        sock.bind((interface,))
    except OSError:
        print(f"Error: Could not bind to {interface}. Is it up?")
        return

    print(f"Sending messages to {interface} (ID: 0x{can_id:x})...")
    print("Press Ctrl+C to stop.")

    # CAN frame: ID (4b), DLC (1b), Pad (3b), Data (8b)
    can_frame_fmt = "<IB3x8s"
    data = b"\xDE\xAD\xBE\xEF\x00\x00\x00\x00"

    try:
        while True:
            # Send frame
            msg = struct.pack(can_frame_fmt, can_id, len(data), data)
            sock.send(msg)
            
            # Sleep with some random 'smart' jitter (e.g. 50us)
            jitter = random.normalvariate(0, 0.00005)
            time.sleep(max(0, interval + jitter))
    except KeyboardInterrupt:
        print("
Stopped simulation.")
    finally:
        sock.close()

if __name__ == "__main__":
    simulate_traffic()
