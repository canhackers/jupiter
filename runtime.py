import csv
import os
import shutil
import time
import zipfile

from can_registry import logging_address, mux_address
from packets import get_value

csv_path = '/home/drive_record/'


class Buffer:
    def __init__(self):
        self.logging_address = [int(x, 16) for x in logging_address]
        self.mux_address = mux_address
        self.can_buffer = {}
        self.message_buffer = []
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


class Logger:
    def __init__(self, buffer, dash, cloud=0, enabled=0):
        self.buffer = buffer
        self.dash = dash
        self.cloud = cloud if cloud is not None else 0
        self.filename = None
        self.file = None
        self.csvwriter = None
        self.enabled = enabled if enabled is not None else 0

    def initialize(self):
        if self.enabled == 0:
            return False
        if not os.path.exists(csv_path):
            os.makedirs(csv_path)
        if self.cloud == 1 and not os.path.exists(csv_path + 'sync/'):
            os.makedirs(csv_path + 'sync/')

        self.filename = time.strftime('DLOG_%y%m%d_%H%M%S.csv', time.localtime(self.dash.di.unix_time))
        self.file = open(csv_path + self.filename, 'w', newline='')
        self.csvwriter = csv.writer(self.file)
        self.csvwriter.writerow(['Time', 'Bus', 'MessageID', 'Multiplexer', 'Message'])

    def close(self):
        if self.enabled == 0:
            return False
        if self.file is None:
            return False
        if not self.file.closed:
            self.file.close()
            zip_filename = self.filename.split('.')[0] + '.zip'
            if self.cloud:
                with zipfile.ZipFile(csv_path + zip_filename, 'w', zipfile.ZIP_LZMA) as myzip:
                    myzip.write(csv_path + self.filename, arcname=self.filename)
                shutil.move(csv_path + zip_filename, csv_path + 'sync/' + zip_filename)
                os.remove(csv_path + self.filename)
            else:
                with zipfile.ZipFile(csv_path + zip_filename, 'w', zipfile.ZIP_DEFLATED) as myzip:
                    myzip.write(csv_path + self.filename, arcname=self.filename)

    def write(self):
        if self.enabled == 0:
            return False
        if self.file is None:
            print('Need Initialize')
            return False
        if (not self.file.closed) and (self.csvwriter is not None):
            for address in self.buffer.can_buffer[0]:
                for mux, signal in self.buffer.can_buffer[0][address].items():
                    if signal is not None:
                        self.csvwriter.writerow([self.dash.di.clock, 0, str(hex(address)), mux, '0x' + str(signal.hex())])


class BatteryLogger:
    def __init__(self, buffer, dash):
        self.buffer = buffer
        self.dash = dash
        self.csv_path = '/home/drive_record/battery/'
        if not os.path.exists(self.csv_path):
            os.makedirs(self.csv_path)

    def _write_safe(self, filename, headers, row_data):
        filepath = self.csv_path + filename
        file_exists = os.path.isfile(filepath)
        with open(filepath, 'a', newline='') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(headers)
            writer.writerow(row_data)
            f.flush()
            os.fsync(f.fileno())

    def _safe_get(self, address, mux):
        try:
            return self.buffer.can_buffer[0][address][mux]
        except KeyError:
            return None

    def log_health(self, event_type="UNKNOWN"):
        soh = full_pack_energy = cac_max = cac_min = cac_avg = 0
        kwh_discharge = kwh_charge = ac_kwh = dc_kwh = 0
        brick_cac = [0] * 108

        sig_352_0 = self._safe_get(0x352, 0)
        if sig_352_0:
            full_pack_energy = get_value(sig_352_0, 16, 16) * 0.02

        sig_3b2_0 = self._safe_get(0x3b2, 0)
        if sig_3b2_0:
            cac_avg = get_value(sig_3b2_0, 8, 13) * 0.1
            cac_min = get_value(sig_3b2_0, 24, 13) * 0.1
            cac_max = get_value(sig_3b2_0, 44, 13) * 0.1

        sig_3b2_83 = self._safe_get(0x3b2, 83)
        if sig_3b2_83:
            soh = get_value(sig_3b2_83, 35, 10) * 0.1

        sig_3d2_0 = self._safe_get(0x3d2, 0)
        if sig_3d2_0:
            kwh_discharge = get_value(sig_3d2_0, 0, 32) * 0.001
            kwh_charge = get_value(sig_3d2_0, 32, 32) * 0.001

        sig_3f2_0 = self._safe_get(0x3f2, 0)
        if sig_3f2_0:
            ac_kwh = get_value(sig_3f2_0, 8, 32) * 0.001

        sig_3f2_1 = self._safe_get(0x3f2, 1)
        if sig_3f2_1:
            dc_kwh = get_value(sig_3f2_1, 8, 32) * 0.001

        for mux in range(108):
            sig_782 = self._safe_get(0x782, mux)
            if sig_782:
                brick_cac[mux] = round(get_value(sig_782, 22, 13) * 0.1, 2)

        headers = ['Time', 'Event', 'SoH(%)', 'FullPackEnergy(kWh)', 'CAC_Max(Ah)', 'CAC_Min(Ah)', 'CAC_Avg(Ah)',
                   'Total_Dchg(kWh)', 'Total_Chg(kWh)', 'AC_Chg(kWh)', 'DC_Chg(kWh)'] + [f'Brick{i + 1}_CAC' for i in
                                                                                         range(108)]

        row = [self.dash.di.clock, event_type, round(soh, 1), round(full_pack_energy, 2), round(cac_max, 1),
               round(cac_min, 1), round(cac_avg, 1), round(kwh_discharge, 2), round(kwh_charge, 2),
               round(ac_kwh, 2), round(dc_kwh, 2)] + brick_cac

        self._write_safe('Battery_Health_Log.csv', headers, row)
        print(
            f"[{self.dash.di.clock}] 🔋 Health Log ({event_type}): SoH {soh:.1f}%, Energy {full_pack_energy:.2f}kWh, CAC Avg {cac_avg:.1f}Ah")

    def log_dynamics(self):
        soc_min = soc_max = soc_avg = 0
        brick_v_max = brick_v_min = t_max = t_min = t_avg = 0
        brick_v = [0] * 108

        sig_292_0 = self._safe_get(0x292, 0)
        if sig_292_0:
            soc_min = get_value(sig_292_0, 0, 10) * 0.1
            soc_max = get_value(sig_292_0, 20, 10) * 0.1
            soc_avg = get_value(sig_292_0, 30, 10) * 0.1

        sig_332_0 = self._safe_get(0x332, 0)
        if sig_332_0:
            t_max = get_value(sig_332_0, 16, 8) * 0.5 - 40
            t_min = get_value(sig_332_0, 24, 8) * 0.5 - 40
            t_avg = get_value(sig_332_0, 32, 8) * 0.5 - 40

        sig_332_1 = self._safe_get(0x332, 1)
        if sig_332_1:
            brick_v_max = get_value(sig_332_1, 2, 12) * 0.002
            brick_v_min = get_value(sig_332_1, 16, 12) * 0.002

        for mux in range(36):
            sig_401 = self._safe_get(0x401, mux)
            if sig_401:
                idx1, idx2, idx3 = mux * 3, mux * 3 + 1, mux * 3 + 2
                if idx1 < 108:
                    brick_v[idx1] = round(get_value(sig_401, 16, 16) * 0.0001, 4)
                if idx2 < 108:
                    brick_v[idx2] = round(get_value(sig_401, 32, 16) * 0.0001, 4)
                if idx3 < 108:
                    brick_v[idx3] = round(get_value(sig_401, 48, 16) * 0.0001, 4)

        headers = ['Time', 'SOC_Max(%)', 'SOC_Min(%)', 'SOC_Avg(%)',
                   'Brick_V_Max(V)', 'Brick_V_Min(V)', 'T_Max(C)', 'T_Min(C)', 'T_Avg(C)'] + [f'Brick{i + 1}_V' for i in
                                                                                              range(108)]

        row = [self.dash.di.clock, round(soc_max, 1), round(soc_min, 1), round(soc_avg, 1),
               round(brick_v_max, 3), round(brick_v_min, 3), round(t_max, 1), round(t_min, 1),
               round(t_avg, 1)] + brick_v

        self._write_safe('Battery_Dynamics_Log.csv', headers, row)
        print(
            f"[{self.dash.di.clock}] ⚡ Dynamics Log: SOC {soc_avg:.1f}%, Brick V: {brick_v_min:.3f}~{brick_v_max:.3f}V, Temp: {t_avg:.1f}C")

    def log_high_load(self, torque_total):
        brick_v_max = brick_v_min = t_max = t_min = 0

        sig_332_1 = self._safe_get(0x332, 1)
        if sig_332_1:
            brick_v_max = get_value(sig_332_1, 2, 12) * 0.002
            brick_v_min = get_value(sig_332_1, 16, 12) * 0.002

        sig_332_0 = self._safe_get(0x332, 0)
        if sig_332_0:
            t_max = get_value(sig_332_0, 16, 8) * 0.5 - 40
            t_min = get_value(sig_332_0, 24, 8) * 0.5 - 40

        headers = ['Time', 'Total_Torque(Nm)', 'Brick_V_Max(V)', 'Brick_V_Min(V)', 'T_Max(C)', 'T_Min(C)', 'SOC_Avg(%)']
        row = [self.dash.di.clock, torque_total, round(brick_v_max, 3), round(brick_v_min, 3),
               round(t_max, 1), round(t_min, 1), round(self.dash.bms.soc, 1)]

        self._write_safe('Battery_HighLoad_Event.csv', headers, row)

        delta_v = brick_v_max - brick_v_min
        print(
            f"!!! HIGH LOAD !!! Torque: {torque_total}Nm | V_Drop: {brick_v_min:.3f}V (Delta {delta_v:.3f}V) | Temp: {t_max:.1f}C")
