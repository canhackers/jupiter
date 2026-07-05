import os


def initialize_canbus_connection():
    try:
        os.system('sudo modprobe -r mcp251x')
        os.system('sudo modprobe mcp251x')
        os.system('sudo ip link set can0 type can bitrate 500000')
        os.system('sudo ifconfig can0 down')
        os.system('sudo ifconfig can0 up')
        print('can bus initialized')
        return True
    except Exception as e:
        print('CAN Bus Initialize Error', e)
        return False
