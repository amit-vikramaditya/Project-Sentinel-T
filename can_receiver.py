import socket
import struct
import os
import time

# Linux specific constants for SocketCAN and Timestamping
PF_CAN = 29
SOCK_RAW = 3
CAN_RAW = 1
SOL_CAN_RAW = 101
SOL_SOCKET = 1
# SO_TIMESTAMP is 29 on many architectures, including ARM64/x86_64 Linux
SO_TIMESTAMP = 29 
SCM_TIMESTAMP = SO_TIMESTAMP

class CANReceiver:
    """
    Low-level SocketCAN receiver that extracts Kernel Timestamps (SO_TIMESTAMP)
    using recvmsg for high-precision physical clock analysis.
    """
    def __init__(self, interface="vcan0"):
        self.interface = interface
        self.sock = socket.socket(PF_CAN, SOCK_RAW, CAN_RAW)
        
        # Enable SO_TIMESTAMP to get the kernel-level packet arrival time
        try:
            self.sock.setsockopt(SOL_SOCKET, SO_TIMESTAMP, 1)
        except OSError as e:
            print(f"[ERROR] Could not enable SO_TIMESTAMP: {e}")
            raise

        try:
            self.sock.bind((interface,))
        except OSError as e:
            print(f"[ERROR] Could not bind to {interface}. Ensure it exists (sudo modprobe vcan && sudo ip link add dev {interface} type vcan && sudo ip link set up {interface}).")
            raise

    def receive(self):
        """
        Receives a CAN frame and its associated kernel timestamp.
        Returns: (can_id, data, timestamp_s)
        """
        # CAN frame: 4 bytes ID, 1 byte DLC, 3 bytes padding, 8 bytes Data = 16 bytes
        # Ancillary data buffer: CMSG_SPACE(sizeof(struct timeval))
        # struct timeval is usually 16 bytes (8s, 8s on 64-bit)
        can_frame_fmt = "<IB3x8s"
        cmsg_capacity = socket.CMSG_SPACE(16) 

        msg, ancdata, flags, addr = self.sock.recvmsg(16, cmsg_capacity)

        # 1. Parse CAN Frame
        can_id, dlc, data = struct.unpack(can_frame_fmt, msg)
        # Handle Extended IDs if necessary
        can_id &= socket.CAN_EFF_MASK if (can_id & socket.CAN_EFF_FLAG) else socket.CAN_SFF_MASK

        # 2. Parse Ancillary Data (Kernel Timestamp)
        kernel_timestamp = 0.0
        for cmsg_level, cmsg_type, cmsg_data in ancdata:
            if cmsg_level == SOL_SOCKET and cmsg_type == SCM_TIMESTAMP:
                # struct timeval: time_t tv_sec, suseconds_t tv_usec
                # On 64-bit Linux, these are typically 'q' (long long / 8 bytes)
                seconds, microseconds = struct.unpack("qq", cmsg_data)
                kernel_timestamp = seconds + (microseconds / 1000000.0)
                break

        return can_id, data[:dlc], kernel_timestamp

    def close(self):
        self.sock.close()

if __name__ == "__main__":
    # Quick test if vcan0 is available
    print(f"Listening on vcan0... (Press Ctrl+C to stop)")
    try:
        receiver = CANReceiver("vcan0")
        while True:
            can_id, data, t_kernel = receiver.receive()
            print(f"[Kernel Time: {t_kernel:.6f}] ID: 0x{can_id:03x} | Data: {data.hex()}")
    except KeyboardInterrupt:
        print("\nStopping...")
    except Exception as e:
        print(f"Error: {e}")