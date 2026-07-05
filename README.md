# Jupiter

Tesla 차량 CAN 메시지를 Raspberry Pi Zero 2W에서 읽고, 선택 기능에 따라 일부 패킷을 변조해 보내는 실험용 런타임입니다.

## 안전 고지

- CAN Bus에 장치를 추가하거나 패킷을 송수신하는 작업은 차량 기능 이상, 주행 중 장애, 법적 문제를 만들 수 있습니다.
- 운전자는 항상 현지 법률, 전방 주시 의무, 조향 의무, 차량 안전기준을 지켜야 합니다.
- 이 코드는 충분히 검증된 상용 제품이 아니며, 사용 중 발생하는 모든 문제는 사용자 책임입니다.
- 본 프로젝트는 Tesla Model Y 2021 Made in USA 차량 기준으로 테스트되었습니다. 차종, 연식, 제조국, 차량 업데이트에 따라 CAN 주소와 패킷 규칙이 달라질 수 있습니다.

## 제공 기능

- 설정과 동작 방식
  - 대부분의 기능은 `/home/jupiter_settings.json`에서 켜거나 끌 수 있습니다. 일반적으로 `1`은 사용, `0`은 사용 안 함입니다.
  - 맵등 버튼 동작은 설정 파일의 `MapLampLeftShort`, `MapLampLeftLong`, `MapLampLeftDouble`, `MapLampRightShort`, `MapLampRightLong`, `MapLampRightDouble` 값으로 다시 매핑할 수 있습니다.
  - 버튼 매핑값을 `null`로 두면 해당 조작은 아무 동작도 하지 않습니다. 예를 들어 왼쪽 맵등 짧게 누르기를 비우려면 `"MapLampLeftShort": null`로 둡니다.
  - 매핑값에 쉼표로 두 기능을 적으면 앞의 기능은 주차 상태, 뒤의 기능은 주행 상태에서 실행됩니다. 예를 들어 `"open_door_rr,buckle_emulator"`는 주차 중 뒷좌석 우측 도어 열림, 주행 중 안전벨트 경고 해제 토글입니다.
  - 설정을 바꾼 뒤에는 `sudo systemctl restart jupiter.service`로 서비스를 재시작해야 새 설정이 적용됩니다.
- 맵등과 파킹 버튼
  - 기본 설정에서 좌측 맵등을 길게 누르면 사이드미러가 접히거나 펼쳐집니다. 이 동작은 `MapLampLeftLong` 값을 바꾸면 다른 기능으로 바꿀 수 있습니다.
  - 스토크에 있는 파킹 버튼을 0.5초 이상 누르면 사이드미러가 접히거나 펼쳐집니다. 파킹 버튼 롱클릭은 설정 파일 매핑 대상이 아니며 고정 동작입니다.
  - 기본 설정에서 주차 중 오른쪽 맵등을 길게 누르면 뒷좌석 우측 도어 열림 요청을 보냅니다.
  - 기본 설정에서 주차 중 오른쪽 맵등을 더블클릭하면 조수석 도어 열림 요청을 보냅니다.
  - 기본 설정에서 주행 중 오른쪽 맵등을 길게 누르면 뒷좌석 안전벨트 경고 해제 기능을 켜거나 끕니다. `RearCenterBuckle` 값이 `1`이면 뒷좌석 중앙 기준, `2`이면 뒷좌석 전체 기준으로 동작합니다.
- 공개 매핑 기능 이름
  - `mirror_fold`는 사이드미러 접기/펴기 요청입니다.
  - `open_door_fl`, `open_door_fr`, `open_door_rl`, `open_door_rr`은 각각 앞좌측, 앞우측, 뒤좌측, 뒤우측 도어 열림 요청입니다.
  - 도어 열림 요청은 반드시 주차 중 동작으로만 매핑하세요. 주행 중 도어 관련 기능이 실행되도록 설정하는 것은 매우 위험합니다.
  - `buckle_emulator`는 뒷좌석 안전벨트 경고 해제 기능을 켜거나 끄는 요청입니다.
  - 문서에 없는 내부 기능명은 임의로 바꾸지 않는 것을 권장합니다. 잘못된 이름을 넣으면 해당 버튼 조작은 사실상 동작하지 않습니다.
- 미러 자동화
  - `MirrorAutoFold`를 `1`로 바꾸면 주행을 마치고 기어가 P로 바뀐 뒤 모든 승객이 내린 것으로 인식될 때 사이드미러가 자동으로 접힙니다.
  - `MirrorAutoFold` 기본값은 `0`입니다. 자동 접힘을 원하지 않으면 기본값 그대로 두면 됩니다.
- 방향지시등과 오토파일럿 보조
  - `AltTurnSignal`이 `1`이면 오른쪽 다이얼을 좌우로 움직여 방향지시등 신호를 보낼 수 있습니다. `0`으로 바꾸면 오른쪽 다이얼 방향지시등 기능을 사용하지 않습니다.
  - 오토파일럿 또는 TACC 상태에서는 오른쪽 다이얼이 차간거리 조절과 충돌할 수 있어 기본적으로 방향지시등 기능이 제한됩니다.
  - 오토파일럿 또는 TACC 상태에서 우측 스토크를 아래로 길게 유지하면 오른쪽 다이얼 방향지시등 기능을 활성화할 수 있습니다. 이 상태에서 거리 조절을 시도하면 의도치 않은 방향지시등 신호가 나갈 수 있으므로 고속도로 등 제한된 상황에서만 주의해서 사용하세요.
  - 오토파일럿 구동 상태에서 우측 스토크를 깊게 누르면 Continuous Autopilot 보조 기능이 활성화됩니다. 브레이크를 밟거나 우측 스토크를 위로 깊게 누르면 비활성화됩니다.
  - Continuous Autopilot 보조 기능은 방향지시등을 켜고 오토파일럿을 해제한 뒤, 방향지시등이 꺼지고 조건이 맞으면 다시 오토파일럿 조작을 요청합니다. 조건은 시속 30km 이상이면서 가속페달을 밟고 있는 경우입니다.
  - `AutoFollowingDistance`가 `1`이면 최근 3초 평균 속도에 따라 차간거리를 자동으로 조절합니다. 기본 목표값은 `~20kph: 3`, `~60kph: 2`, `~80kph: 3`, `~100kph: 4`, `100kph~: 5`입니다.
  - 운전자가 직접 차간거리를 조절하면 오토파일럿이 유지되는 동안은 수동 지정값을 우선합니다. 자동 차간거리 조절을 원하지 않으면 `AutoFollowingDistance`를 `0`으로 바꾸면 됩니다.
- 와이퍼, 주행모드, 공조 보조
  - `KeepWiperSpeed`가 `1`이면 오토파일럿 중 Auto 와이퍼가 자동으로 바뀌는 상황에서 마지막 와이퍼 설정을 유지하도록 보조합니다.
  - `SlowWiper`가 `1`이면 시속 3km 이하 저속에서 와이퍼 속도를 멈추거나 낮추도록 요청합니다.
  - `KickDown`이 `1`이면 주행모드가 Comfort일 때 가속페달을 깊게 밟으면 Sport 페달맵 요청을 보냅니다. 브레이크를 밟으면 킥다운 상태가 해제됩니다.
  - `AutoRecirculation`이 `1`이면 공조기가 Auto recirc 상태일 때 탑승 인원과 시간 조건에 따라 내기/외기 모드를 자동으로 바꾸도록 요청합니다.
- 기록과 복구
  - `Logger`가 `1`이면 주행 기록을 1초 단위로 CSV에 저장하고, 주행 종료 시 ZIP 파일로 압축합니다.
  - 주행 시작과 종료 시 배터리 health 로그를 남깁니다.
  - 주행 중 5분마다 배터리 dynamics 로그를 남깁니다.
  - 총 구동 토크가 높은 상황에서는 배터리 고부하 이벤트 로그를 남깁니다.
  - CAN 통신이 끊기거나 반복 오류가 발생하면 CAN interface를 재초기화하고, 오류가 누적되면 기기를 재부팅합니다.
  - 스티어링 휠 양쪽 다이얼을 동시에 1초 이상 누르면 Jupiter 기기 재부팅을 요청합니다.
- 선택 연동
  - `NavdyHud`가 `1`이면 Navdy HUD로 속도, 토크, 기어, 전압, SOC, 고전압 배터리 온도, 주행 가능 거리, Raspberry Pi 온도 등을 전송할 수 있습니다.
  - Holy-IOT BLE 비콘을 사용하는 경우 비콘 버튼의 press/release 상태를 Jupiter 상태에 반영할 수 있습니다.

## 하드웨어 준비물

- Raspberry Pi Zero 2W 또는 Zero 2WH
- Waveshare RS485 CAN HAT
- 12V → 5V Step Down 모듈
- Micro SD 카드 8GB 이상, 주행 로그 저장을 고려하면 32GB 이상 권장
- DIY OBD 커넥터
  - 6번 핀: CAN High
  - 14번 핀: CAN Low
  - 16번 핀: 12V
  - 4번 핀: GND
- Tesla용 OBD 컨버터 케이블
- 전용 인클로저 또는 직접 제작한 케이스

`jupiter_slim_case.stl`은 배포 대상에 포함되는 케이스 모델 파일입니다.

## 1. Raspberry Pi OS 준비

Raspberry Pi Imager에서 다음 기준으로 Micro SD 카드를 만듭니다.

- 디바이스: Raspberry Pi Zero 2W
- 운영체제: Raspberry Pi OS Lite 64-bit
- 사용자 이름: `zero`
- SSH: 활성화
- Wi-Fi: 2.4GHz 네트워크 입력
- 시간대: `Asia/Seoul`
- 키보드: `us`

SD 카드 선택을 잘못하면 PC의 다른 디스크가 지워질 수 있으니 반드시 대상 장치를 확인하세요.

## 2. SSH 접속

Pi가 부팅되고 Wi-Fi에 연결되면 PC나 스마트폰 Termius에서 접속합니다.

```bash
ssh zero@<라즈베리파이 IP>
```

예전 같은 hostname/IP로 접속한 이력이 있어 SSH fingerprint 오류가 나면 PC의 `known_hosts` 항목을 정리한 뒤 다시 접속합니다.

## 3. 소스 받기

Pi에서 `/home/zero/jupiter` 경로로 클론합니다.

```bash
cd /home/zero
git clone https://github.com/canhackers/jupiter.git jupiter
cd /home/zero/jupiter
```

이미 받은 소스를 업데이트할 때는 다음을 사용합니다.

```bash
cd /home/zero/jupiter
git pull
```

## 4. 대화형 설치 실행

설치는 대화형 스크립트 하나로 진행합니다. 아래 명령 하나를 실행합니다.

```bash
cd /home/zero/jupiter
bash setup/install_interactive.sh
```

스크립트는 각 단계마다 아래 형식으로 진행합니다.

```text
1단계: 무엇을 합니다.
진행할까요? 계속하려면 Y를 입력하세요: Y
1단계 진행 중입니다...
1단계 진행 결과 성공입니다.
```

실패하면 해당 단계에서 멈추고 실패 사유와 로그 위치를 출력합니다.

```text
3단계 진행 결과 실패입니다.
실패 사유는 ... 입니다.
전체 설치 로그: /home/zero/jupiter/.setup/install.log
```

설치기는 다음 단계를 순서대로 진행합니다.

1. 환경설정 기본 확인
2. 시스템 패키지 설치
3. Python 실행환경 구성
4. CAN HAT 부팅 설정
5. Smoke Test
6. 자동 실행 서비스 등록
7. 재부팅 전 수동 실행 여부 확인

CAN HAT 부팅 설정이 새로 추가되면 재부팅이 필요합니다. 이 경우 설치기가 재부팅 여부를 묻고 멈춥니다. 재부팅 후 같은 명령을 다시 실행하면 앞 단계는 확인만 하고 이어서 진행합니다.

```bash
cd /home/zero/jupiter
bash setup/install_interactive.sh
```

## 5. Smoke Test와 서비스 등록

설치기는 Smoke Test까지 한 번에 실행한 뒤 이상 여부를 알려줍니다.

Smoke Test에서 확인하는 항목:

- Python 파일 문법
- 핵심 모듈 import
- 단위 테스트
- `can0` 인터페이스 존재

Smoke Test가 모두 성공해야 `jupiter.service` 자동 실행 서비스를 등록합니다.

이미 서비스가 같은 내용으로 등록되어 있으면 중복 등록하지 않습니다. 기존 서비스 파일이 다른 내용이면 백업 후 교체할지 다시 묻습니다.

## 6. 수동 실행

서비스 등록 후 설치기는 다음을 묻습니다.

```text
재부팅 전 지금 직접 서비스를 실행해볼까요? [Y/n]:
```

`Y`를 입력하면 `jupiter.service`를 즉시 시작하고 active 상태와 최근 로그를 확인합니다.

건너뛰면 다음 재부팅 때 서비스가 자동으로 시작됩니다.

수동으로 직접 시작/재시작하려면 다음 명령을 사용합니다.

```bash
sudo systemctl start jupiter.service
sudo systemctl restart jupiter.service
sudo systemctl stop jupiter.service
```

## 7. 모니터링과 강제 중지

설치기가 `/usr/local/bin/jupiter.sh`를 설치합니다. 설치 후에는 어느 경로에서든 아래 명령으로 실행/모니터링 세션에 들어갈 수 있습니다.

```bash
jupiter.sh
```

`jupiter.service`가 꺼져 있으면 먼저 서비스를 시작하고, 이미 실행 중이면 바로 로그를 표시합니다.

키 동작은 다음과 같습니다.

- `q`: 로그 보기만 종료하고 `jupiter.service`는 계속 실행
- `Ctrl+C`: `jupiter.service`를 중지하고 종료

기기가 이상 동작할 때 기기를 분리하지 않고 SSH/Termius에서 `jupiter.sh`에 들어간 뒤 `Ctrl+C`로 서비스를 멈출 수 있습니다.

설치 전이거나 `/usr/local/bin/jupiter.sh`가 아직 없으면 프로젝트 폴더에서 직접 실행할 수 있습니다.

```bash
cd /home/zero/jupiter
bash setup/jupiter.sh
```

이미 설치된 장치에서 `git pull`로 최신 버전만 받은 경우에는 아래 명령으로 `jupiter.sh`를 전역 명령으로 다시 등록할 수 있습니다.

```bash
cd /home/zero/jupiter
git pull
sudo install -m 0755 setup/jupiter.sh /usr/local/bin/jupiter.sh
```

현재 서비스 상태는 다음 명령으로 확인합니다.

```bash
sudo systemctl status jupiter.service
```

최근 로그만 보려면 다음 명령을 사용합니다.

```bash
sudo journalctl -u jupiter.service -n 100 --no-pager
```

## 설정 파일

런타임 설정 파일은 `/home/jupiter_settings.json`입니다.

파일이 없으면 첫 실행 시 기본값으로 생성됩니다. 기존 설정 파일에 새 기본 key가 없으면 사용자 값을 보존하면서 기본 key를 병합합니다.

수동으로 수정할 때는 JSON 문법을 지켜야 합니다. 쉼표 하나가 빠져도 설정 파일을 읽을 수 없으므로, 수정 전 백업을 권장합니다.

```bash
sudo cp /home/jupiter_settings.json /home/jupiter_settings.json.bak
sudo nano /home/jupiter_settings.json
python3 -m json.tool /home/jupiter_settings.json >/dev/null
sudo systemctl restart jupiter.service
```

대표 설정 예시는 다음과 같습니다. 실제 파일에는 더 많은 key가 있을 수 있으며, 문서에 없는 내부 key는 기본값 그대로 두는 것을 권장합니다.

```json
{
    "Logger": 1,
    "MapLampLeftLong": "mirror_fold",
    "MapLampRightLong": "open_door_rr,buckle_emulator",
    "RearCenterBuckle": 1,
    "AutoRecirculation": 1,
    "KickDown": 1,
    "KeepWiperSpeed": 1,
    "SlowWiper": 1,
    "AltTurnSignal": 1,
    "AutoFollowingDistance": 1,
    "MirrorAutoFold": 0,
    "NavdyHud": 0
}
```

자주 바꾸는 값은 다음과 같습니다.

- 버튼 매핑
  - `MapLampLeftShort`, `MapLampLeftLong`, `MapLampLeftDouble`은 좌측 맵등의 짧게 누르기, 길게 누르기, 더블클릭 동작을 정합니다.
  - `MapLampRightShort`, `MapLampRightLong`, `MapLampRightDouble`은 우측 맵등의 짧게 누르기, 길게 누르기, 더블클릭 동작을 정합니다.
  - 값으로는 `null`, `mirror_fold`, `open_door_fl`, `open_door_fr`, `open_door_rl`, `open_door_rr`, `buckle_emulator`를 사용할 수 있습니다.
  - `"open_door_rr,buckle_emulator"`처럼 쉼표로 두 값을 넣으면 주차 중에는 앞의 값, 주행 중에는 뒤의 값이 실행됩니다.
- 안전벨트 경고 해제
  - `RearCenterBuckle`을 `0`으로 두면 기능을 사용하지 않습니다.
  - `RearCenterBuckle`을 `1`로 두면 뒷좌석 중앙 착좌센서 기준으로 동작합니다.
  - `RearCenterBuckle`을 `2`로 두면 뒷좌석 전체 기준으로 동작합니다. 실제 승객이 안전벨트를 하지 않은 상태에서 이 기능을 사용하는 것은 매우 위험하며 법규 위반이 될 수 있습니다.
- 주행 보조 기능
  - `AutoFollowingDistance`, `AltTurnSignal`, `KeepWiperSpeed`, `SlowWiper`, `KickDown`, `AutoRecirculation`은 각각 해당 기능을 `1`로 켜고 `0`으로 끕니다.
  - 기능을 잘 모르면 한 번에 여러 값을 바꾸지 말고 하나씩 바꾼 뒤 `jupiter.sh`로 로그를 확인하는 것을 권장합니다.

## Navdy HUD 선택 기능

Navdy HUD를 사용하지 않으면 이 항목은 건너뜁니다.

Navdy는 별도의 개조 펌웨어, Bluetooth 페어링, PyBluez 의존성이 필요합니다. 먼저 `bluetoothctl`로 장치를 `pair`, `trust` 처리하고 `/home/mac_address`에 MAC 주소를 저장해야 합니다.

```bash
sudo bluetoothctl
scan on
pair 54:ED:A3:xx:xx:xx
trust 54:ED:A3:xx:xx:xx
exit
```

필요 패키지와 PyBluez는 다음과 같이 설치합니다.

```bash
sudo apt-get install -y python3-dev libbluetooth-dev bluetooth bluez
cd /home/zero/jupiter
. .venv/bin/activate
pip install git+https://github.com/pybluez/pybluez.git#egg=PyBluez
deactivate
```

MAC 주소와 설정 파일을 저장합니다.

```bash
echo "54:ED:A3:xx:xx:xx" | sudo tee /home/mac_address
sudo nano /home/jupiter_settings.json
```

JSON에서 `NavdyHud` 값을 `1`로 설정합니다.

```json
{
    "NavdyHud": 1
}
```

## 프로젝트 구조

- `jupiter.py`: 실행 진입점과 CAN 수신/송신 루프
- `feature_stack.py`: 기능 객체 생성과 버튼 매핑
- `runtime.py`: CAN buffer, 일반 logger, battery logger
- `can_io.py`: CAN 초기화 명령
- `settings.py`: 설정 파일 로드/병합
- `state.py`: 차량/장치 상태 dataclass
- `can_registry.py`: CAN 주소, mux, monitoring mapping
- `packets.py`: bit field 읽기/쓰기와 checksum helper
- `features/`: Autopilot, 버튼, 안전벨트, 공조, 킥다운, 방향지시등, reboot 기능
- `navdy.py`: Navdy HUD 선택 기능
- `beacon.py`: Holy-IOT BLE 비콘 선택 기능
- `setup/install_interactive.sh`: 대화형 설치기
- `setup/jupiter.sh`: 서비스 실행, 모니터링, 강제 중지

## 문제 확인

`can0`가 보이지 않으면 다음을 확인합니다.

```bash
ip -details link show can0
```

보이지 않는 경우:

- 설치기 4단계 이후 재부팅했는지 확인
- CAN HAT 장착 상태 확인
- `/boot/firmware/config.txt` 또는 `/boot/config.txt`에 아래 두 줄이 있는지 확인

```text
dtparam=spi=on
dtoverlay=mcp2515-can0,oscillator=12000000,interrupt=25,spimaxfrequency=2000000
```

서비스가 바로 종료되면 로그를 확인합니다.

```bash
sudo journalctl -u jupiter.service -n 100 --no-pager
```

설치기 전체 로그는 다음 위치에 저장됩니다.

```text
/home/zero/jupiter/.setup/install.log
```

## 문의

최신 리팩토링 버전은 Codex가 만들었습니다. 설치나 간단한 트러블 슈팅은 LLM의 도움을 받으세요.

버그 리포트, 기능 건의, 인클로저 제작 문의는 CAN Hackers 카페를 참고하세요.

https://cafe.naver.com/canhacker
