import csv
import time
import can
from functions import initialize_canbus_connection

initialize_canbus_connection()
can_bus = can.interface.Bus(channel='can0', interface='socketcan')

logging_address = ['0x132', '0x292', '0x29d', '0x312', '0x321', '0x332', '0x33a', '0x352', '0x3f2', '0x401', '0x75d']

f = open('/home/zero/jupiter/canlog.csv', 'w', newline='')
csvwriter = csv.writer(f)
csvwriter.writerow(['Time', 'MessageID', 'Message'])

while True:
    try:
        recv_message = can_bus.recv(1)
    except KeyboardInterrupt:
        f.close()
        break
    except Exception as e:
        recv_message = None
        continue
    if recv_message is not None:
        address = recv_message.arbitration_id
        signal = recv_message.data
        time_txt = time.strftime('%m/%d %H:%M:%S', time.localtime(recv_message.timestamp))
        csvwriter.writerow([time_txt, str(hex(address)), '0x' + str(signal.hex())])

print('기록 종료')