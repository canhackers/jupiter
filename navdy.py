import threading
import asyncio
import bluetooth
import struct
import json
import time


class Navdy:
    def __init__(self, mac_address):
        self.mac_address = mac_address
        self.uuid = "dfce890e-6631-4e4a-800d-9415d98ccff7"
        self.connected = False
        self.sock = None

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


class HudConnector:
    def __init__(self):
        self.connected = asyncio.Event()
        self.connect_try_cnt = 0
        try:
            with open('/home/mac_address', 'r') as f:
                mac_address = (f.readline()).strip()
            self.mac_address = mac_address
            self.navdy = Navdy(mac_address)
            self.init = True
        except Exception as e:
            print(e)
            self.mac_address = 'Not Available'
            self.navdy = Navdy('00:00:00:00:00:00')
            print('Can not find Navdy MAC Address file. check /home/mac_address')
            self.init = False

    async def connect_hud(self):
        while self.init:
            if not self.connected.is_set():
                self.connect_try_cnt += 1
                print(f'Attempting to connect to Navdy...{self.connect_try_cnt}')
                self.navdy.connected = self.navdy.connect()
                if self.navdy.connected:
                    print('Navdy Connected ', self.navdy.mac_address)
                    self.connected.set()
                    self.connect_try_cnt = 0
            await asyncio.sleep(5)

    async def monitor_connection(self):
        while self.init:
            if self.connected.is_set():
                await asyncio.sleep(5)
                if self.navdy.connected == False:
                    print('NAVDY 접속이 끊겼습니다')
                    self.connected.clear()
            await asyncio.sleep(1)

    def stop(self):
        self.init = False


class Hud(threading.Thread):
    def __init__(self, dash):
        super().__init__()
        self.connector = HudConnector()
        self.navdy = self.connector.navdy
        self.dash = dash
        self.thread_online = True
        self.loop = asyncio.new_event_loop()

    def start_event_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.create_task(self.connector.connect_hud())
        self.loop.create_task(self.connector.monitor_connection())
        self.loop.run_forever()
    def run(self):
        loop_thread = threading.Thread(target=self.start_event_loop)
        loop_thread.start()
        last_update_fast = 0
        last_update_slow = 0
        while self.thread_online:
            if not self.navdy.connected:
                time.sleep(5)
                continue
            else:
                self.dash.navdy_connected = 1
            time.sleep(0.2)
            current_time = self.dash.current_time
            try:
                if (current_time - last_update_fast) >= 0.2:
                    last_update_fast = current_time
                    if self.dash.parked:
                        gear = 1
                    else:
                        if self.dash.autopilot == 1:
                            gear = 6 if self.dash.nag_disabled == 1 else 5
                        else:
                            gear = self.dash.gear
                    payload = {'__speed__': self.dash.ui_speed,
                               '__tachometer__': abs(self.dash.torque_front + self.dash.torque_rear),
                               'gear': gear
                               }
                    if (current_time - last_update_slow) >= 2:
                        last_update_slow = current_time
                        payload['voltage'] = self.dash.LVB_voltage
                        payload['soc'] = self.dash.soc
                        payload['hv_temp'] = self.dash.HVB_max_temp
                        payload['ui_range'] = self.dash.ui_range
                        payload['ui_range_map'] = self.dash.ui_range
                        payload['raspi_temp'] = self.dash.device_temp
                    self.navdy.send_message(payload)
            except Exception as e:
                print("Exception caught while processing Navdy Dash", e)

    def stop(self):
        self.thread_online = False
        self.loop.call_soon_threadsafe(self.loop.stop)
