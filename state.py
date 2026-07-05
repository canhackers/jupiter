import time
from dataclasses import dataclass, field
from typing import Optional

from packets import get_value


@dataclass
class RuntimeState:
    bus_error_count: int = 0
    current_time: float = 0
    last_update: float = 0


@dataclass
class DriveInfoState:
    unix_time: int = 0
    clock: Optional[str] = None
    parked: int = 1
    drive_finished: int = 0
    drive_time: int = 0
    gear: int = 0
    accel_pedal_pos: float = 0
    speed: int = 0


@dataclass
class PowertrainState:
    torque_front: int = 0
    torque_rear: int = 0


@dataclass
class DriveConfigState:
    pedal_map: int = 0


@dataclass
class UiControlsState:
    wiper_state: int = 0
    wiper_off_request: int = 0


@dataclass
class UiHvacState:
    fresh_request: int = 0
    recirc_mode: int = 0  # 0 Auto, 1 내기, 2 외기


@dataclass
class UiDisplayState:
    range_km: int = 0


@dataclass
class BmsState:
    lv_voltage: float = 0
    soc: float = 0
    hv_max_temp: float = 0
    hv_min_temp: float = 0
    nominal_full: float = 0
    health: dict = field(default_factory=lambda: {
        'soh': 0, 'full_pack_energy': 0, 'cac_max': 0, 'cac_min': 0, 'cac_avg': 0,
        'kwh_discharge': 0, 'kwh_charge': 0, 'ac_kwh': 0, 'dc_kwh': 0,
        'brick_cac': [0] * 108
    })
    dynamics: dict = field(default_factory=lambda: {
        'bus_v_min': 0, 'bus_v_max': 0, 'soc_min': 0, 'soc_max': 0, 'soc_avg': 0,
        'brick_v_max': 0, 'brick_v_min': 0, 't_max': 0, 't_min': 0, 't_avg': 0,
        'brick_v': [0] * 108
    })


@dataclass
class IbstState:
    driver_brake: int = 0


@dataclass
class CabinState:
    seat_occupancy_fl: int = 0
    seat_occupancy_fr: int = 0
    seat_occupancy_rl: int = 0
    seat_occupancy_rc: int = 0
    seat_occupancy_rr: int = 0
    occupant_count: int = 0
    is_occupied: int = 1
    occupancy_timer: float = 0

    def update_occupant_count(self):
        self.occupant_count = sum((
            self.seat_occupancy_fl,
            self.seat_occupancy_fr,
            self.seat_occupancy_rl,
            self.seat_occupancy_rc,
            self.seat_occupancy_rr,
        ))


@dataclass
class BodyState:
    mirror_folded_left: int = 0
    mirror_folded_right: int = 0
    turn_indicator_left: int = 0
    turn_indicator_right: int = 0


@dataclass
class AutopilotState:
    tacc: int = 0
    autopilot: int = 0
    mars_mode: int = 0
    turn_signal_on_ap: int = 0
    nag_disabled: int = 0


@dataclass
class FeatureState:
    buckle_emulator: int = 0
    alt_turn_signal: int = 0


@dataclass
class DeviceState:
    temperature: float = 0
    navdy_connected: int = 0
    beacon: dict = field(default_factory=dict)


@dataclass
class Dashboard:
    runtime: RuntimeState = field(default_factory=RuntimeState)
    di: DriveInfoState = field(default_factory=DriveInfoState)
    powertrain: PowertrainState = field(default_factory=PowertrainState)
    drive_config: DriveConfigState = field(default_factory=DriveConfigState)
    ui_controls: UiControlsState = field(default_factory=UiControlsState)
    ui_hvac: UiHvacState = field(default_factory=UiHvacState)
    ui_display: UiDisplayState = field(default_factory=UiDisplayState)
    bms: BmsState = field(default_factory=BmsState)
    ibst: IbstState = field(default_factory=IbstState)
    cabin: CabinState = field(default_factory=CabinState)
    body: BodyState = field(default_factory=BodyState)
    ap: AutopilotState = field(default_factory=AutopilotState)
    features: FeatureState = field(default_factory=FeatureState)
    device: DeviceState = field(default_factory=DeviceState)

    def update(self, name, signal):
        if name == 'UnixTime':
            self.di.unix_time = int.from_bytes(signal, byteorder='big')
            self.di.clock = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.di.unix_time))
        elif name == 'DriveSystemStatus':
            self.di.gear = get_value(signal, 21, 3)
            self.di.accel_pedal_pos = get_value(signal, 32, 8) * 0.4
        elif name == 'UI_powertrainControl':
            self.drive_config.pedal_map = get_value(signal, 5, 2)  # 0 Comport, 1 Sport 2 Performance
        elif name == 'DIspeed':
            self.di.speed = max(0, get_value(signal, 24, 9))
        elif name == 'DIR_torque':
            self.powertrain.torque_rear = get_value(signal, 27, 13, signed=True) * 2
        elif name == 'DIF_torque':
            self.powertrain.torque_front = get_value(signal, 27, 13, signed=True) * 2
        elif name == 'IBST_status':
            self.ibst.driver_brake = get_value(signal, 16, 2)  # 1 Not Apply, 2 Apply
        elif name == '12vBattStatus':
            mux = get_value(signal, 0, 3)
            if mux == 1:
                self.bms.lv_voltage = get_value(signal, 32, 12) * 0.00544368
        elif name == 'BMS_SOC':
            self.bms.soc = get_value(signal, 10, 10) * 0.1
        elif name == 'UI_rangeSOC':
            self.ui_display.range_km = int(get_value(signal, 0, 10) * 1.6)
        elif name == 'BMS_energyStatus':
            self.bms.nominal_full = get_value(signal, 0, 11) * 0.1
        elif name == 'BMSthermal':
            mux = get_value(signal, 0, 2)
            if mux == 0:
                self.bms.hv_max_temp = get_value(signal, 43, 11) * 0.1 - 40
                self.bms.hv_min_temp = get_value(signal, 32, 10) * 0.2 - 40
        elif name == 'UI_hvacRequest':
            self.ui_hvac.recirc_mode = get_value(signal, 20, 2)
        elif name == 'VCLEFT_switchStatus':
            mux = get_value(signal, 0, 2)
            if mux == 0:
                self.cabin.seat_occupancy_fl = 1 if get_value(signal, 50, 2) == 2 else 0
                self.cabin.seat_occupancy_rl = 1 if get_value(signal, 56, 2) == 2 else 0
                self.cabin.seat_occupancy_rc = 1 if get_value(signal, 54, 2) == 2 else 0
                self.cabin.seat_occupancy_rr = 1 if get_value(signal, 58, 2) == 2 else 0
                self.cabin.update_occupant_count()
        elif name == 'VCRIGHT_switchStatus':
            mux = get_value(signal, 0, 2)
            if mux == 0:
                self.cabin.seat_occupancy_fr = 1 if get_value(signal, 40, 2, 'little') == 2 else 0
                self.cabin.update_occupant_count()
        elif name == 'UI_vehicleControl':
            self.ui_controls.wiper_state = get_value(signal, 56, 3)
        elif name == 'VCLEFT_doorStatus':
            state = get_value(signal, 52, 3)
            if state in [2, 4]:
                self.body.mirror_folded_left = 0
            elif state in [1, 3]:
                self.body.mirror_folded_left = 1
        elif name == 'VCRIGHT_doorStatus':
            state = get_value(signal, 52, 3)
            if state in [2, 4]:
                self.body.mirror_folded_right = 0
            elif state in [1, 3]:
                self.body.mirror_folded_right = 1
        elif name == 'VCFRONT_lighting':
            self.body.turn_indicator_left = 0 if get_value(signal, 0, 2) == 0 else 1
            self.body.turn_indicator_right = 0 if get_value(signal, 2, 2) == 0 else 1

        if self.cabin.occupant_count > 0:
            if self.cabin.is_occupied == 0:
                self.cabin.occupancy_timer = time.time()
                self.cabin.is_occupied = 1
        else:
            if self.cabin.is_occupied == 1:
                if self.cabin.occupancy_timer != 0 and time.time() - self.cabin.occupancy_timer > 10:
                    self.cabin.is_occupied = 0
                    self.cabin.occupancy_timer = 0
