from packet_functions import get_value, modify_packet_value

# multiplexer 적용 패킷인 경우, multiplexer 개수 정보 추가
mux_address = {'0x3fd': 8}

logging_address = ['0x3fd', '0x3f8', '0x155']

# 상시 모니터링 할 주요 차량정보 접근 주소
# monitoring_addrs = {0x3fd: 'UI_autopilotControl',
#                     0x3f8: 'UI_driverAssistControl',
#                     }

monitoring_addrs = {}


class Buffer:
    def __init__(self):
        self.mux_address = mux_address
        self.can_buffer = {}
        self.message_buffer = []
        self.logging_address = [int(x, 16) for x in logging_address]
        self.initial_can_buffer()

    def initial_can_buffer(self):
        self.can_buffer = {0: {x: {0: None} for x in self.logging_address}}
        for m_address, byte in self.mux_address.items():
            for i in range(2 ** byte):
                self.can_buffer[0][int(m_address, 16)][i] = None

    def flush_message_buffer(self):
        self.message_buffer = []

    def write_can_buffer(self, bus: int, address: int, signal: bytes):
        if hex(address) in self.mux_address.keys():
            mux = signal[0] & (2 ** self.mux_address[hex(address)] - 1)
        else:
            mux = 0
        if self.can_buffer[bus].get(address):
            self.can_buffer[bus][address][mux] = signal

    def write_message_buffer(self, bus, address, signal):
        self.message_buffer.append([bus, address, signal])


class Dashboard:
    def __init__(self):
        self.bus_error_count = 0
        self.current_time = 0
        self.last_update = 0
        self.occupancy = 1
        self.vehicle_speed = 0
        self.standstill = 0

    def update(self, name, signal):
        if name == 'UI_autopilotControl':
            pass
        elif name == 'UI_driverAssistControl':
            pass

    def check(self, bus, address, byte_data):
        if bus == 0 and address == 0x155:
            self.standstill = get_value(byte_data, 41, 1)
            self.vehicle_speed = get_value(byte_data, 42, 10) * 0.5
            print('현재 차 속도: ', self.vehicle_speed, '정지상태: ', self.standstill)
        return byte_data

class FSD_Control:
    def __init__(self, buffer, dash):
        self.buffer = buffer
        self.dash = dash
        self.following_distance = 1
        self.speed_profile = 2
        self.fsd_enabled = 1    # UI에서 활성화 불가하여 강제로 1 고정
        self.speed_offset = 0

    def check(self, bus, address, byte_data):
        ret = byte_data
        if bus == 0 and address == 0x3f8:   # 1016
            self.following_distance = get_value(ret, 45, 3)
            if self.following_distance == 1:
                self.speed_profile = 2
            elif self.following_distance == 2:
                self.speed_profile = 1
            elif self.following_distance == 3:
                self.speed_profile = 0
            return ret

        if bus == 0 and address == 0x3fd:   # 1021
            mux = get_value(ret, 0, 3)
            if mux == 0:
                # self.fsd_enabled = get_value(ret, 38, 1)
                if self.fsd_enabled == 1:
                    off = int(get_value(ret, 25, 6) - 30)
                    self.speed_offset = max(min(off * 5, 100), 0)

                    if off == 2:
                        self.speed_profile = 2
                    elif off == 1:
                        self.speed_profile = 1
                    elif off == 0:
                        self.speed_profile = 0

                    ret = modify_packet_value(ret, 46, 1, 1)
                    ret = modify_packet_value(ret, 49, 2, self.speed_profile)
                    self.buffer.write_message_buffer(0, address, ret)
                return ret

            elif mux == 1:
                # UI_applyEceR79를 False로
                ret = modify_packet_value(ret, 19, 1, 0)
                self.buffer.write_message_buffer(0, address, ret)
                return ret

            elif mux == 2:
                if self.fsd_enabled == 1:
                    ret = modify_packet_value(ret, 6, 2, self.speed_offset % 4)
                    ret = modify_packet_value(ret, 8, 6, self.speed_offset // 4)
                    self.buffer.write_message_buffer(0, address, ret)
                return ret
        return ret

