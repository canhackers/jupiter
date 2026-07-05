# 리팩터링 사전 질문지 v2

## 검토 방식

이번 문서는 token-router의 DeepSeek fallback 라우팅 결과와 원문 추가 확인을 함께 사용해 다시 작성했습니다. 라우터는 전체 파일에서 관련 line slice를 고르는 용도로만 사용했고, 최종 구조 판단과 질문 작성은 원문 코드 기준으로 정리했습니다.

검토 대상은 `README.md`, `functions.py`, `packet_functions.py`, `jupiter.py`, `tesla.py`, `navdy.py`, `beacon.py`입니다.

## 결정사항

### 1. 리팩터링 목표

- 최우선 목표는 기존 동작을 최대한 보존하면서, 기능 추가와 장기 유지보수가 쉬운 구조로 바꾸는 것입니다.
- 기존 구조는 작성자에게 당시 편한 형태였지만, 시간이 지난 뒤 다시 읽었을 때 구조 파악이 어렵다는 문제가 있습니다.
- 클래스 구조, 기능 단위 구조, 변수 관리는 전반적으로 다시 설계해도 됩니다.
- 단, 원래 실행되던 기능을 해치지 않는 범위에서 리팩터링해야 합니다.

### 2. 보존 우선 영역

- 차량에 패킷을 전달하거나 CAN 채널을 리셋하는 제어 경로는 안정성을 우선합니다.
- `os.system()` 기반 Shell 실행 명령은 명백한 오류가 아니라면 보존합니다.
- Shell 명령을 `subprocess` 등으로 바꾸는 작업은 리팩터링 기본 범위가 아니라, 실제 실패 처리나 명확한 버그가 확인될 때 별도 검토합니다.

### 3. 버그 수정 기준

- 전면 리팩터링 전에 현재 구조를 유지한 상태에서 명백한 버그만 먼저 수정합니다.
- 이 단계의 목표는 기존 old 구조의 개선판을 확정하고 커밋해, 이후 전면 리팩터링의 기준점을 만드는 것입니다.
- `Reboot.check()`가 payload를 반환하지 않는 문제는 다른 `check()` 메서드들의 반환 패턴을 참고해 원본 payload 또는 수정 payload를 반환하도록 고칩니다.
- `Dashboard.bus_error_cout`는 명백한 오타이므로 `bus_error_count`로 정리합니다.
- `KickDown`은 원래 Comfort 모드일 때만 동작하게 하려는 의도였으나, 현재 조건은 갱신되지 않는 `drive_mode`를 보고 있습니다. `UI_powertrainControl`에서 갱신되는 `pedal_map`을 기준으로 조건을 바꾸는 것이 맞습니다.
- `load_settings()`는 설정 파일이 없으면 생성하고, 오래된 설정 파일에 새 key가 없으면 해당 key를 파일에 보충하려는 의도입니다. 기존 사용자 설정값을 보존하면서 새 기본 key를 병합하는 방향을 유지합니다.
- 새 기능 또는 새 설정 key가 추가된 경우, 해당 key는 파일에만 보충되는 것이 아니라 같은 부팅 세션에서도 즉시 적용되어야 합니다. 따라서 병합된 설정값을 반환하도록 보완합니다.

### 4. Old 구조 안정판 수정 목록

전면 리팩터링 전에 아래 항목을 현재 구조 안에서 먼저 수정하고 커밋합니다.

1. `Reboot.check()` 반환값 보정
2. `Dashboard.bus_error_cout` 오타 수정
3. `KickDown` 조건을 갱신되지 않는 `drive_mode`에서 `pedal_map` 기준으로 변경
4. `load_settings()`가 기존 설정과 새 기본 key를 병합한 결과를 현재 부팅 세션에도 반환하도록 변경

### 5. 목표 모듈 구조 방향

- 본격 리팩터링은 런타임 계층 중심으로 분리합니다.
- 기능 클래스들은 루트의 `functions.py`와 충돌하지 않도록 `features/` 패키지 아래에 기능별 파일로 둡니다.
- 1차 리팩터링에서는 기능 클래스의 기존 `check(bus, address, byte_data)` 인터페이스를 유지해 동작 보존을 우선합니다.
- 제안 구조:
  - `jupiter.py`: 진입점과 wiring
  - `runtime.py`: 메인 루프, tick, dispatch 흐름
  - `can_io.py`: CAN 초기화, bus 생성, 송수신 래핑
  - `settings.py`: 설정 로드/병합
  - `state.py`: 차량/장치 상태
  - `buffer.py`: CAN 수신 버퍼와 송신 큐
  - `signals.py`: 주소, mux, signal mapping, scale 정의
  - `packets.py`: bit field, checksum, packet mutation
  - `features/`: reboot, buttons, autopilot, buckle, fresh_air, kickdown, turn_signal, logger, battery_logger, navdy, beacon

### 6. 상태 관리 방향

- `Dashboard` 하나에 모든 값을 평면으로 두는 구조는 Tesla CAN 모듈/신호 출처 중심의 2단계 상태로 정리합니다.
- 리팩터링 이후에는 코딩 에이전트가 주로 코드를 수정할 예정이므로, 문서에 상태 구조와 매핑 원칙을 명확히 남깁니다.
- 목표 상태 구조:
  - `dash.runtime`: Jupiter loop와 실행 상태. 예: `current_time`, `last_update`, `bus_error_count`
  - `dash.di`: drive/driver information 계열. 예: `unix_time`, `clock`, `gear`, `parked`, `drive_time`, `drive_finished`, `speed`, `accel_pedal_pos`
  - `dash.powertrain`: 구동계 실측값. 예: `torque_front`, `torque_rear`
  - `dash.drive_config`: 주행 설정/모드. 예: `pedal_map`
  - `dash.ui_controls`: UI vehicle control 계열. 예: `wiper_state`, `wiper_off_request`
  - `dash.ui_hvac`: UI HVAC request 계열. 예: `recirc_mode`, `fresh_request`
  - `dash.ui_display`: UI 표시값. 예: `range_km`, 필요 시 display SOC
  - `dash.vc_left`: left vehicle controller 계열 raw/decode 상태
  - `dash.vc_right`: right vehicle controller 계열 raw/decode 상태
  - `dash.cabin`: 실내 착좌/탑승 상태. 예: `seat_occupancy_fl`, `seat_occupancy_fr`, `seat_occupancy_rl`, `seat_occupancy_rc`, `seat_occupancy_rr`, `occupant_count`, `is_occupied`
  - `dash.body`: 문/미러/방향지시등 등 차체 상태
  - `dash.bms`: BMS 계열. 예: `soc`, `nominal_full`, `hv_max_temp`, `hv_min_temp`, `health`, `dynamics`
  - `dash.ibst`: brake sensor 계열. 예: `driver_brake`
  - `dash.ap`: Jupiter가 추적하는 Autopilot/TACC 보조 상태. 예: `tacc`, `autopilot`, `mars_mode`, `turn_signal_on_ap`, `nag_disabled`
  - `dash.features`: 기능 토글성 상태. 예: `buckle_emulator`, `alt_turn_signal`
  - `dash.device`: Jupiter 장치/외부 장치 상태. 예: `temperature`, `navdy_connected`, `beacon`
  - 기능별 임시/명령 상태는 `dash`에 올리지 않고 각 feature 클래스 내부에 둡니다. 예: 버튼 요청, Autopilot switch command, FreshAir 타이머, TurnSignal 유지 상태
- 기존 `dash.xxx` 평면 접근은 호환 property로 오래 남기지 않고, 문서화된 매핑표를 기준으로 새 2단계 구조로 직접 변경합니다.
- 변경은 파일/기능 단위로 차근차근 수행하고, 각 단계마다 문법 검사와 targeted test 또는 smoke 검증을 수행합니다.

### 7. 상태 매핑 초안

현재 `Dashboard` 필드는 아래 기준으로 이동합니다. 리팩터링 중 더 적절한 신호 출처가 확인되면 문서를 먼저 갱신한 뒤 코드를 변경합니다.

| 현재 필드 | 목표 필드 |
| --- | --- |
| `bus_error_count` | `dash.runtime.bus_error_count` |
| `current_time` | `dash.runtime.current_time` |
| `last_update` | `dash.runtime.last_update` |
| `unix_time` | `dash.di.unix_time` |
| `clock` | `dash.di.clock` |
| `parked` | `dash.di.parked` |
| `drive_finished` | `dash.di.drive_finished` |
| `drive_time` | `dash.di.drive_time` |
| `gear` | `dash.di.gear` |
| `accel_pedal_pos` | `dash.di.accel_pedal_pos` |
| `ui_speed` | `dash.di.speed` |
| `torque_front` | `dash.powertrain.torque_front` |
| `torque_rear` | `dash.powertrain.torque_rear` |
| `pedal_map` | `dash.drive_config.pedal_map` |
| `drive_mode` | 제거 후보. 현재 갱신되지 않으며 `pedal_map`으로 대체 |
| `wiper_state` | `dash.ui_controls.wiper_state` |
| `wiper_off_request` | `dash.ui_controls.wiper_off_request` |
| `fresh_request` | `dash.ui_hvac.fresh_request` |
| `recirc_mode` | `dash.ui_hvac.recirc_mode` |
| `ui_range` | `dash.ui_display.range_km` |
| `LVB_voltage` | `dash.bms.lv_voltage` |
| `soc` | `dash.bms.soc` |
| `HVB_max_temp` | `dash.bms.hv_max_temp` |
| `HVB_min_temp` | `dash.bms.hv_min_temp` |
| `nominal_full` | `dash.bms.nominal_full` |
| `bat_health` | `dash.bms.health` |
| `bat_dynamics` | `dash.bms.dynamics` |
| `driver_brake` | `dash.ibst.driver_brake` |
| `passenger[0]` | `dash.cabin.seat_occupancy_fl` |
| `passenger[1]` | `dash.cabin.seat_occupancy_fr` |
| `passenger[2]` | `dash.cabin.seat_occupancy_rl` |
| `passenger[3]` | `dash.cabin.seat_occupancy_rc` |
| `passenger[4]` | `dash.cabin.seat_occupancy_rr` |
| `passenger_cnt` | `dash.cabin.occupant_count` |
| `occupancy` | `dash.cabin.is_occupied` |
| `occupancy_timer` | `dash.cabin.occupancy_timer` |
| `mirror_folded[0]` | `dash.body.mirror_folded_left` |
| `mirror_folded[1]` | `dash.body.mirror_folded_right` |
| `turn_indicator_left` | `dash.body.turn_indicator_left` |
| `turn_indicator_right` | `dash.body.turn_indicator_right` |
| `tacc` | `dash.ap.tacc` |
| `autopilot` | `dash.ap.autopilot` |
| `mars_mode` | `dash.ap.mars_mode` |
| `turn_signal_on_ap` | `dash.ap.turn_signal_on_ap` |
| `nag_disabled` | `dash.ap.nag_disabled` |
| `buckle_emulator` | `dash.features.buckle_emulator` |
| `alt_turn_signal` | `dash.features.alt_turn_signal` |
| `device_temp` | `dash.device.temperature` |
| `navdy_connected` | `dash.device.navdy_connected` |
| `beacon` | `dash.device.beacon` |

### 8. Feature 내부 상태 원칙

- `dash`는 차량/장치/사용자 상태처럼 여러 기능이 읽는 공유 상태만 담습니다.
- 특정 기능의 타이밍, 일회성 요청, 내부 상태 기계는 해당 feature 클래스 내부에 유지합니다.
- 예:
  - `ButtonManager.mirror_request`, `door_open_request`
  - `Autopilot.switch_commands`, `stalk_down_count`, `distance_current`
  - `FreshAir.last_mode_change`, 내부 `recirc_mode`
  - `TurnSignal.turn_indicator`, `right_dial_click_time`
- 따라서 별도 `dash.commands` 도메인은 만들지 않습니다.

### 9. Signal/Dispatcher 구조와 패킷 변조 제약

- 주소와 mux 해석은 `signals.py` 또는 `decoders.py`에 모으고, 메인 런타임 흐름에서는 가능한 한 주소 literal 대신 signal 이름을 사용합니다.
- 메인 루프는 다음 순서를 목표로 합니다.
  1. CAN frame 수신
  2. `SignalSpec`으로 address/mux를 signal 이름으로 해석
  3. 수신 버퍼 저장
  4. decoder로 `dash` 상태 갱신
  5. signal 이름 기준으로 feature dispatcher 실행
  6. 변조 결과를 송신 큐에 적재
- 중요한 제약:
  - 하나의 CAN 주소/frame에 여러 feature의 변경점이 동시에 들어갈 수 있습니다.
  - 이 경우 payload 변조는 같은 frame payload 위에 누적 적용되어야 합니다.
  - checksum/counter가 있는 frame은 각 feature가 따로 계산하지 않고, 해당 frame의 모든 변경점이 반영된 뒤 마지막에 한 번만 계산해야 합니다.
  - 이 구조가 깨지면 feature 간 변조가 서로 덮어쓰거나 counter/checksum이 잘못될 수 있습니다.
- 따라서 feature는 가능하면 즉시 완성 payload를 만들기보다, frame별 mutation request를 반환하거나 누적 가능한 mutation context에 변경점을 추가하는 구조를 검토합니다.
- 예: `FrameMutation(address=0x334, changes=[(5, 2, 1)], checksum_policy=...)` 같은 형태를 모아 마지막 단계에서 payload를 확정합니다.
- 단, 기존 동작 보존을 위해 1차 리팩터링에서는 현재 순차 `check()` 흐름을 유지하되, 같은 frame 내 다중 변조와 checksum/counter 최종 계산 제약을 깨지 않는지 테스트로 확인합니다.
- 이 영역은 차량 제어 안정성과 직결되므로 안전하게 단계적으로 진행합니다.
- 1차 리팩터링에서는 기존 `check()` 기반 순차 payload 변조 구조를 유지하고, 파일 분리/상태 구조/signal 이름 기반 dispatcher를 먼저 정리합니다.
- frame별 mutation 누적과 최종 checksum/counter 계산 구조는 2차 리팩터링 후보로 분리합니다.
- 기존 `dash.xxx` 평면 접근은 호환 property로 오래 남기지 않고, 문서화된 매핑표를 기준으로 새 2단계 구조로 직접 변경합니다.
- 변경은 파일/기능 단위로 차근차근 수행하고, 각 단계마다 문법 검사와 targeted test 또는 smoke 검증을 수행합니다.

## 프로젝트 구조 요약

이 프로젝트는 Raspberry Pi Zero 2W에서 `can0` SocketCAN을 열고 Tesla 차량 CAN 메시지를 수신합니다. 수신된 메시지는 `Dashboard` 상태 객체와 `Buffer.can_buffer`에 저장되고, 기능 클래스들이 필요할 때 변조된 payload를 `Buffer.message_buffer`에 넣습니다. `Jupiter.run()` 메인 루프는 매 사이클 수신, 상태 갱신, 기능별 `check()`, 송신, 버퍼 비우기를 수행합니다.

- `README.md`: 안전 경고, 지원 차량, Raspberry Pi 설치, CAN HAT 설정, Python 의존성, 자동 실행, Navdy HUD 설정을 설명합니다.
- `functions.py`: CAN 인터페이스 초기화와 `/home/jupiter_settings.json` 설정 파일 생성/병합/복구를 담당합니다.
- `packet_functions.py`: payload bit field 읽기/쓰기, checksum 계산, counter/checksum 포함 패킷 생성을 담당합니다.
- `jupiter.py`: 전체 런타임 중심입니다. CAN 연결, 수신 루프, Dashboard 업데이트, 기능 호출, 로그 생명주기, 송신 처리를 담당합니다.
- `tesla.py`: 차량 상태 모델, 로그, 배터리 로그, 버튼 입력, Autopilot 보조, 안전벨트 에뮬레이션, 공조, 킥다운, 방향지시등 로직을 모두 담고 있습니다.
- `navdy.py`: Navdy HUD 블루투스 연결과 Dashboard 상태 전송을 담당합니다.
- `beacon.py`: Holy-IOT BLE 비콘 검색, 등록 파일 관리, 버튼 알림 수신, `dash.beacon` 상태 갱신을 담당합니다.

## 핵심 데이터 흐름

1. `main()`이 설정을 읽고 `Dashboard`와 `Jupiter` 스레드를 시작합니다.
2. `Jupiter.run()`이 `can0`를 초기화하고 `Buffer`, `Logger`, `BatteryLogger`, `Autopilot`, `ButtonManager` 등 기능 객체를 생성합니다.
3. CAN 메시지를 수신하면 `Buffer.can_buffer`에 최근 payload를 저장합니다.
4. `monitoring_addrs`에 등록된 주소는 `Dashboard.update()`로 차량 상태를 갱신합니다.
5. 특정 주소별로 기능 객체의 `check(bus, address, signal)`이 호출되어 payload를 유지하거나 변조합니다.
6. 변조 payload는 `Buffer.message_buffer`에 쌓이고, 루프 말미에 `python-can`으로 송신됩니다.
7. 기어가 Drive로 바뀌면 주행 로그와 배터리 health 로그를 시작하고, Park로 바뀌면 주행 로그를 닫고 배터리 health 로그를 남깁니다.
8. `0x528` UnixTime 메시지를 1초 tick처럼 사용해 온도, 주행 시간, 5분 배터리 dynamics 로그, Autopilot tick을 처리합니다.

## 주요 상태와 변수 용도

- `Dashboard`: 차량/기기 공유 상태 저장소입니다. 기어, 페달, 브레이크, 속도, 토크, 배터리, 탑승자, 와이퍼, 미러, 오토파일럿, 방향지시등, HUD, 비콘 상태가 모입니다.
- `Buffer.can_buffer`: 주소와 mux별 최근 CAN payload 저장소입니다. 일반 로그와 배터리 로그가 이 값을 조회합니다.
- `Buffer.message_buffer`: 변조 또는 에뮬레이션된 송신 예정 메시지 큐입니다. 루프마다 송신 후 비웁니다.
- `logging_address`: 일반 CAN 로그에 포함할 주소 목록입니다.
- `mux_address`: mux가 있는 주소의 mux bit 폭입니다. `Buffer.write_can_buffer()`가 payload 첫 byte에서 mux 값을 계산할 때 사용합니다.
- `monitoring_addrs`: CAN 주소를 `Dashboard.update()`의 signal 이름으로 매핑합니다.
- `settings`: 기능 토글과 버튼 매핑입니다. 현재 JSON 한 파일에 평면 key로 저장됩니다.
- `Button.function`/`function_name`: short, long, double과 park/drive 변형 클릭별 실행 함수를 저장합니다.
- `Autopilot.switch_commands`: 스크롤 휠/거리 조절 명령을 순차 실행하기 위한 명령 큐입니다.
- `BatteryLogger.csv_path`: 배터리 전용 CSV 저장 경로입니다.

## 주요 함수와 클래스 용도

- `initialize_canbus_connection()`: `mcp251x` 모듈 재로드, `can0` bitrate 설정, interface down/up을 수행합니다.
- `load_settings()`: 기본 설정을 생성하고 기존 설정을 병합합니다. 깨진 JSON은 `_error.json`으로 rename 후 재생성합니다.
- `get_value()`: payload에서 bit field 값을 읽습니다. little/big endian과 signed 값을 지원합니다.
- `modify_packet_value()`: payload의 bit field 값을 수정합니다. 범위를 벗어나면 원본 payload를 반환합니다.
- `make_new_packet()`: 지정 field 수정 후 counter와 checksum을 갱신합니다.
- `Dashboard.update()`: signal 이름별로 payload를 해석해 Dashboard 상태를 갱신합니다.
- `Logger`: 주행 중 주요 CAN payload를 1초마다 CSV에 쓰고 종료 시 ZIP으로 압축합니다.
- `BatteryLogger`: 주행 시작/종료 health, 5분 dynamics, 고부하 이벤트 CSV를 기록합니다.
- `Button`/`ButtonManager`: 맵등/주차 버튼 click pattern을 기능에 연결하고 미러 접기, 문 열기, buckle emulator, mars mode toggle 요청을 만듭니다.
- `Autopilot`: TACC/AP 상태 추정, 스토크 조작 해석, NAG 제거, Continuous AP, following distance 자동 조절, 와이퍼 설정 유지/저속 조절을 담당합니다.
- `RearCenterBuckle`: 설정과 토글 상태에 따라 뒷좌석 착좌/벨트 payload를 변조합니다.
- `FreshAir`: 탑승자 수 기준으로 내기/외기 시간을 바꾸고 외기 모드를 요청합니다.
- `KickDown`: 가속 페달 조건에서 powertrain control payload를 Sport로 변조합니다.
- `TurnSignal`: 오른쪽 다이얼 입력을 방향지시등 스토크 신호로 변환합니다.
- `Hud`/`HudConnector`/`Navdy`: 블루투스 연결 유지와 HUD payload 전송을 담당합니다.
- `HolyIoT`: BLE 비콘 검색/등록/연결과 press/release 상태 반영을 담당합니다.

## 먼저 답해야 할 핵심 질문

1. 이번 리팩터링의 1순위는 무엇인가요? 안정성 보존, 파일 분리, 테스트 가능성, 기능 추가 준비, 차량별 확장 중 우선순위를 정해야 합니다.
2. 동작 변경 없는 구조 개선만 원하나요, 아니면 명백한 의심 버그는 함께 고쳐도 되나요?
3. 실차 테스트가 가능한가요? 가능하다면 어느 기능까지 실제 차량에서 확인할 수 있나요?
4. 리팩터링 후에도 현재 Raspberry Pi Zero 2W에서 loop timing과 CPU 부담을 거의 그대로 유지해야 하나요?
5. 1차 범위는 `tesla.py` 분리까지인가요, 아니면 설정/테스트/설치 문서까지 포함하나요?

## 기능별 보존 질문

### Autopilot

1. Mars Mode, NAG 제거, Continuous AP, right stalk double-down, following distance 자동 조절 중 반드시 유지할 기능은 무엇인가요?
2. README의 안전 경고와 맞춰 Autopilot 관련 기능을 별도 위험 기능 그룹으로 분리해도 되나요?
3. `AutoFollowingDistance`의 속도 구간별 target distance 값은 현재 값 그대로 유지해야 하나요?
4. 수동 following distance 조작 후 `manual_distance`를 세우는 현재 정책을 유지할까요?
5. `reset_distance()`가 초기화 시 `distance_near`를 6번 큐에 넣는 동작은 의도된 보정 절차인가요?
6. `sender`와 `device`는 현재 생성자에서 저장되지만 실제 송신에는 거의 쓰이지 않습니다. 향후 `panda` 지원을 위해 남겨야 하나요?

### 버튼과 사용자 입력

1. 맵등 좌/우와 ParkingButton만 공식 지원하면 되나요?
2. 버튼 mapping 문자열에서 `open_door_rr,buckle_emulator`처럼 park/drive 동작을 콤마로 나누는 형식을 유지할까요?
3. short/long/double click timing 기본값은 현재 `0.5초`, `1.0초`, ParkingButton long `0.5초`를 유지해야 하나요?
4. `get_function()`이 알 수 없는 함수명을 조용히 no-op 처리하는 방식을 유지할까요, 설정 오류로 로그를 남길까요?
5. 미러 접기와 문 열기 요청은 현재 원본 CAN 메시지 타이밍에 맞춰 한 번만 삽입합니다. 요청 TTL이나 재시도 정책이 필요할까요?

### 안전벨트, 공조, 킥다운, 방향지시등

1. `RearCenterBuckle` mode 2처럼 안전상 위험한 기능은 유지하되 명시적 설정이 있을 때만 활성화할까요?
2. `FreshAir.time_dict`의 탑승자 수별 내기/외기 시간표는 설정 파일로 빼야 하나요?
3. `FreshAir`는 차량 UI가 Auto recirc일 때만 개입합니다. 이 조건을 유지할까요?
4. `KickDown`의 조건은 현재 `drive_mode == 0`, accel pedal > 90, brake 해제입니다. 실제로는 `pedal_map`을 봐야 하는지 확인이 필요합니다.
5. `TurnSignal`의 CRC 테이블은 차량/연식별로 달라질 수 있나요? 별도 signal 정의로 분리해야 하나요?
6. 오른쪽 다이얼 방향지시등은 AP/TACC 중 제한 조건과 일반 주행 조건을 현재처럼 유지해야 하나요?

### 로그와 배터리

1. 일반 주행 로그 CSV 컬럼과 ZIP 형식은 기존 파일과 호환되어야 하나요?
2. 배터리 health/dynamics/high-load CSV 컬럼은 이미 사용 중인 분석 도구와 호환되어야 하나요?
3. `/home/drive_record/`와 `/home/drive_record/battery/`는 고정 경로인가요, 설정으로 이동해도 되나요?
4. 5분마다 `log_dynamics()`를 남기는 주기와 `total_torque > 2000`, 0.5초 high-load 제한은 설정화할까요?
5. `fsync()`를 매 배터리 로그마다 호출하는 현재 안정성 우선 정책은 유지해야 하나요?
6. 오래된 로그 삭제, 용량 제한, cloud sync 폴더 정책이 필요한가요?

### HUD와 BLE 비콘

1. Navdy HUD는 계속 공식 지원 대상인가요, 선택 플러그인처럼 분리해도 되나요?
2. `/home/mac_address`와 `/home/beacons` 경로는 고정해야 하나요?
3. HUD 전송 payload key는 기존 펌웨어와 호환되어야 하므로 변경 금지인가요?
4. HUD/BLE 스레드 종료 시 event loop task cancel, Bluetooth socket close를 추가해도 되나요?
5. BLE 비콘은 현재 저장 파일이 없을 때만 새로 기록합니다. 재스캔/재등록 명령이나 설정이 필요할까요?

## 코드 구조 변경 질문

1. `tesla.py`를 `state.py`, `buffer.py`, `logging.py`, `battery.py`, `buttons.py`, `autopilot.py`, `features.py`, `signals.py`처럼 분리해도 되나요?
2. `Dashboard`를 dataclass로 바꾸고 signal별 update 함수를 분리해도 되나요?
3. CAN 주소, bit 위치, scaling factor, CRC table을 코드에서 분리해 signal 정의 테이블로 관리해도 되나요?
4. 모든 기능 클래스가 `check(bus, address, byte_data)` 인터페이스를 유지하는 구조가 좋나요, 아니면 관심 주소를 선언하고 dispatcher가 호출하는 구조로 바꿀까요?
5. `Buffer.message_buffer`는 단순 list를 유지할까요, 아니면 중복 방지, 우선순위, 만료 시간을 가진 송신 큐로 바꿀까요?
6. `os.system()` 호출은 `subprocess.run()`으로 바꾸고 성공/실패를 명시적으로 검사해도 되나요?
7. `print()` 기반 로그를 `logging` 모듈로 바꾸되 Raspberry Pi 화면/`screen` 사용성을 유지할까요?

## 설정과 배포 질문

1. `/home/jupiter_settings.json` 평면 구조를 유지할까요, `features`, `buttons`, `logging`, `devices`, `paths`로 그룹화해도 되나요?
2. 기존 설정 파일과의 하위 호환이 필수인가요?
3. 기본 설정에 누락된 `MarsMode`, `MapLampLeftShort`, `MapLampLeftDouble`, `MapLampRightShort` 같은 key를 명시적으로 추가할까요?
4. 기존 설정 파일에 새 기본값을 병합한 뒤 반환값도 병합본으로 바꿔 즉시 적용되게 할까요?
5. `rc.local + screen` 자동 실행 방식을 유지할까요, systemd 서비스 파일로 전환할까요?
6. 의존성 설치를 `requirements.txt` 또는 설치 스크립트로 정리할까요?

## 확인이 필요한 의심 지점

1. `Dashboard.__init__()`에는 `bus_error_cout`가 있고 메인 루프는 `bus_error_count`를 동적으로 만듭니다. 오타 수정 대상입니다.
2. `Dashboard.drive_mode`는 갱신되지 않고 `pedal_map`만 갱신됩니다. `KickDown` 조건은 `drive_mode`가 아니라 `pedal_map`을 봐야 할 가능성이 큽니다.
3. `Reboot.check()`는 대부분의 경로에서 payload를 반환하지 않습니다. `signal = REBOOT.check(...)` 이후 `signal`이 `None`이 될 수 있습니다.
4. `load_settings()`는 기본값을 파일에 병합하지만 반환은 원본 `settings`입니다. 새 기본값이 런타임에 즉시 반영되지 않을 수 있습니다.
5. `initialize_canbus_connection()`은 `os.system()` exit code를 확인하지 않으므로 실제 실패를 성공처럼 처리할 수 있습니다.
6. `ButtonManager.check()`의 `p_btn = self.buttons['ParkingButton']`는 버튼 등록 누락 시 예외가 납니다. 현재 등록 순서에 의존합니다.
7. `command` dict, `fold_request_time`, `door_open_start_time`, `Autopilot.continuous_ap_request_time`, `Autopilot.sender`, `Autopilot.device`는 현재 사용 범위가 불분명합니다.
8. `Hud.run()`은 연결이 끊긴 뒤 `dash.navdy_connected`를 0으로 되돌리지 않습니다.
9. `beacon.py`에서 `dash=None`으로 실행하면 notification 수신 시 `self.dash.beacon` 접근이 실패할 수 있습니다.
10. `except:`가 여러 곳에 있어 실제 오류 종류를 놓칠 수 있습니다.

## 테스트 질문

1. 실차 없이도 돌릴 수 있는 unit test를 먼저 만들까요? 우선순위는 `packet_functions.py`, `Dashboard.update()`, 각 기능 클래스의 `check()`입니다.
2. 실제 CAN 로그 샘플을 replay fixture로 저장할 수 있나요?
3. 위험 기능은 기본 비활성화 상태만 테스트할까요, 활성화 시 payload 변조까지 테스트할까요?
4. Raspberry Pi에서만 가능한 smoke test와 PC에서 가능한 CI test를 분리할까요?
5. `python-can`, `vcgencmd`, Bluetooth 의존성은 adapter/mock으로 감싸도 되나요?

## 추천 1차 리팩터링 범위

1. 동작 변경 없는 구조화부터 시작합니다.
2. `packet_functions.py`에 unit test를 추가해 bit 조작의 기준선을 고정합니다.
3. `Dashboard`, `Buffer`, `Logger`, `BatteryLogger`를 `tesla.py`에서 분리합니다.
4. 기능 클래스는 인터페이스를 유지한 채 파일만 나눕니다.
5. 의심 지점은 별도 커밋 또는 별도 단계로 고칩니다. 특히 `Reboot.check()`, `bus_error_count`, `load_settings()` 반환값, `KickDown` 조건은 실차 영향 가능성이 있으므로 사용자 답변 후 처리합니다.

## 답변 템플릿

아래 항목만 먼저 답해도 1차 작업 범위를 확정할 수 있습니다.

1. 리팩터링 목표:
2. 동작 변경 허용 여부:
3. 실차 테스트 가능 여부:
4. 반드시 유지할 기능:
5. 분리해도 되는 선택 기능:
6. 설정 파일 하위 호환 필요 여부:
7. 1차 리팩터링 범위:
