import os
import time

from packets import get_value


class Reboot:
    def __init__(self, dash):
        self.dash = dash
        self.last_pressed = 0
        self.requested = 0

    def check(self, bus, address, byte_data):
        if (bus == 0) and (address == 0x3c2):
            mux = get_value(byte_data, 0, 2)
            if mux == 1:
                left_clicked = get_value(byte_data, 5, 2)
                right_clicked = get_value(byte_data, 12, 2)
                if left_clicked == 2 and right_clicked == 2:
                    if self.requested == 0:
                        self.requested = 1
                        print('Reboot Request counted')
                        self.last_pressed = time.time()
                    else:
                        if time.time() - self.last_pressed >= 1:
                            print('Reboot Request')
                            os.system('sudo reboot')
                else:
                    self.requested = 0
        return byte_data
