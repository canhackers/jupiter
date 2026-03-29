from packet_functions import get_value, modify_packet_value

# multiplexer 적용 패킷인 경우, multiplexer 개수 정보 추가
mux_address = {'0x3fd': 8}

logging_address = ['0x3fd', '0x3f8']

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

    def update(self, name, signal):
        if name == 'UI_autopilotControl':
            pass
        elif name == 'UI_driverAssistControl':
            pass
            # self.gear = get_value(signal, 21, 3)


class FSD_Control:
    def __init__(self, buffer, dash):
        self.buffer = buffer
        self.dash = dash
        self.following_distance = 1
        self.speed_profile = 2
        self.fsd_enabled = 1
        self.speed_offset = 0

    def check(self, bus, address, byte_data):
        ret = byte_data
        print('변조전 메시지: ', ret)
        if bus == 0 and address == 0x3f8:   # 1016
            self.following_distance = get_value(ret, 45, 3)
            if self.following_distance == 1:
                self.speed_profile = 2
            elif self.following_distance == 2:
                self.speed_profile = 1
            elif self.following_distance == 3:
                self.speed_profile = 0

            print(f'following distance : {self.following_distance} speed_profile : {self.speed_profile}')
            return ret

        if bus == 0 and address == 0x3fd:   # 1021
            mux = get_value(ret, 0, 3)
            print(mux, '0x3fd 진입. FSD활성화여부', self.fsd_enabled)
            if mux == 0:
                # self.fsd_enabled = get_value(ret, 38, 1)
                self.fsd_enabled = 1
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
                    print('mux 0 변조된 메시지', ret)
                    self.buffer.write_message_buffer(0, address, ret)
                return ret

            elif mux == 1:
                # UI_applyEceR79를 False로
                ret = modify_packet_value(ret, 19, 1, 0)
                self.buffer.write_message_buffer(0, address, ret)
                print('mux 1 변조된 메시지', ret)
                return ret

            elif mux == 2:
                self.fsd_enabled = get_value(ret, 38, 1)
                if self.fsd_enabled == 1:
                    ret = modify_packet_value(ret, 6, 2, self.speed_offset % 4)
                    ret = modify_packet_value(ret, 8, 6, self.speed_offset // 4)
                    self.buffer.write_message_buffer(0, address, ret)
                    print('mux 2 변조된 메시지', ret)
                return ret

        return ret

