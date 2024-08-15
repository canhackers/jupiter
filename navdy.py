import bluetooth
import struct
import json

class Navdy:
    def __init__(self, mac_address):
        self.mac_address = mac_address
        self.uuid = "dfce890e-6631-4e4a-800d-9415d98ccff7"
        self.connected = False
        self.connect_try_cnt = 0
        self.sock = None
        self.last_update_fast = 0
        self.last_update_slow = 0

    def connect(self):
        service_matches = bluetooth.find_service(address=self.mac_address, uuid=self.uuid)
        if len(service_matches) == 0:
            print(f"Could not find any services with the specified UUID {self.uuid} on device {self.mac_address}.")
            return False
        else:
            service = service_matches[0]
            try:
                sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
                sock.connect((service["host"], service["port"]))
                self.sock = sock
                return True
            except Exception as e:
                print(f"An error occurred: {e}")

    def send_message(self, payload):
        serialized = json.dumps(payload).encode('utf-8')
        length = struct.pack('>H', len(serialized))
        try:
            self.sock.send(length + serialized)
            return True
        except:
            self.connected = False
            return False
