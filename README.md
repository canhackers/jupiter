★ 비상업적 용도로 수정, 재배포가 가능합니다.
   상업적인 이용은 금지 합니다.

★ 운전자는 현지의 법률을 준수할 의무가 있습니다.
   대한민국의 도로교통법은 운전 중 전방 주시 의무, 정확한 조향을 할 의무를 운전자에게 부여하고 있습니다.
   대한민국의 튜닝 법률은 '경미한 튜닝'으로서 승인 의무가 없는 튜닝이라 하더라도, 자동차관리법의 안전기준을 준수하도록 하고 있습니다.
   위에 위배되는 튜닝 및 장치 사용은 사용자 개인의 책임입니다.

★ CAN Bus에 장치를 추가하거나, 추가된 장치를 통해 패킷을 읽고/보내는 작업은 차의 기능을 고장내거나, 주행 중 차량이 멈출 수 있는 리스크가 있습니다.
   이 레포지토리에서 제공되는 코드는 충분히 검증되지 않았습니다.
   사용 중 발생할 수 있는 모든 문제는 개인의 책임입니다.

★ 본 리포지토리는 Tesla Model Y 2021 (Made in USA) 에서 테스트 되었습니다.
   Model3용 DBC 파일을 기준으로 만들었기 때문에 동일한 연식에서는 사용 가능할 것으로 보이나,
   차종에 따라 모듈의 구성, 주소, 패킷 규칙이 달라져 동작하지 않을 수 있습니다.
   또한 차량 업데이트를 통해 주소, 패킷주소가 달라져 잘 동작하던 기능이 추후 사용할 수 없게 될 수 있습니다.

기능 문의 / 건의 및 인클로져 제작 문의 등은 https://cafe.naver.com/canhacker 를 방문해 주세요.

커피 한잔 사주고 싶으신 분은 https://toss.me/canhackers





★ 하드웨어 구성 준비물

1. 라즈베리파이 2W 또는 2WH : 만약 2W를 구입했다면 HAT을 연결하기 위한 헤더핀을 별도로 구입해 납땜 해야 합니다.
2. Waveshare RS485 CAN HAT
3. 12V → 5V Step Down 모듈 (MP1584EN 外)
4. Micro USB Male Vertical PCB (https://www.aliexpress.com/item/1005002320414960.html)
5. Micro SD 메모리 최소 8GB, 권장 32GB 이상
6. DIY용 OBD 커넥터 (https://www.aliexpress.com/item/1468276483.html)
- 6번 핀 CAN High, 14번 핀 Can Low, 16번 핀 12V, 4번핀 GND
7. 전용 인클로져 (https://cafe.naver.com/canhacker/27) 또는 직접 디자인 한 케이스
8. Tesla용 OBD 컨버터 케이블 (https://www.aliexpress.com/item/1005006022463035.html)


★ 설치 방법
1. https://www.raspberrypi.com/software/
   에서 Raspberry Pi Imager를 다운로드 받습니다.

2. 디바이스 Raspberry Pi Zero 2W , 운영체제는 Raspberry Pi OS (other)에 들어간 뒤 Raspberry Pi OS Lite (64-bit)을 선택합니다.
   저장소는 MicroSD를 선택합니다. 최소 8GB 이상에 설치할 수 있지만 주행 로그 기록을 위해 32GB 이상을 권장합니다.
  
   ※ 실수로 MicroSD 메모리 카드가 아닌 중요한 디스크를 지우지 않도록 주의하세요!!

3. "OS 커스터마이징을 사용하십니까?" 질문에서 "설정을 편집하기"를 선택합니다.
 3-1. '일반' 탭에서 hostname과 사용자 이름/비밀번호, 무선LAN 등을 설정하고 체크가 활성화 되도록 해줍니다.
   예시) 
   hostname: zero
   사용자이름: zero
   비밀번호: 0000              (라즈베리파이에 원격접속할 때 쓸 비밀번호)
   무선LAN SSID: myrouter     (집 공유기 또는 스마트폰 핫스팟 주소)
   비밀번호: 00000000          (공유기 또는 핫스팟 비밀번호)
   무선LAN국가: GB              (한국이라고 KR이라고 바꾸면 잘 접속되지 않는 이슈가 있습니다)
   로케일 설정 시간대 : Asia/Seoul
   키보드 레이아웃: us

   ※ 이어질 설명에서 계정명이 zero라는 가정 하에 작성함
   ※ hostname은 Bonjour 서비스가 활성화 된 PC에서 ip주소 대신 hostname.local 이라는 주소로 접속할 수 있게 해줍니다.
      Wifi는 2.4GHz 공유기의 SSID를 입력하시기 바랍니다.

 3-2. '서비스' 탭에서 SSH 사용에 체크하고, '비밀번호 인증 사용'을 선택합니다.

4. OS 커스터마이징 설정을 적용하시곘습니까? 질문에 '예'를 선택한 뒤 Micro SD카드에 이미지를 기록합니다.

5. 이미지 기록이 완료되면 PC에서 MicroSD카드를 제거한 뒤 다시 삽입합니다.
    그리고 config.txt 파일을 열어 가장 아래에 다음 두 줄을 추가합니다.

dtparam=spi=on
dtoverlay=mcp2515-can0,oscillator=12000000,interrupt=25,spimaxfrequency=2000000

6. 이제 MicroSD 카드를 라즈베리파이에 삽입하고 USB 선을 연결해 Wifi에 접속되기를 기다립니다. 
   이 과정에서 CAN HAT은 빨간 LED가 상시점등, 라즈베리파이 본체에는 녹색 LED가 지속 점등 되다가 간헐적으로 깜빡입니다.

7. 라즈베리파이의 IP주소를 확인하기 위해 Wifi 공유기 설정화면 또는 스마트폰의 핫스팟 설정에 들어가서 접속되었는지 확인합니다.
   ※ 첫 부팅에서는 접속까지 5분 이상 걸리기도 합니다.
    정상적으로 Wifi에 연결되었다면 위에서 지정한 RASPI-Z2W라는 장치가 접속됩니다.

   ※ 추후 접속할 네트워크를 추가하려면 ssh에서 sudo nmtui 명령어를 이용해 추가할 수 있습니다.
     차에서 노트북을 연결해 모니터링 할 수 있도록 스마트폰 핫스팟을 추가 네트워크로 등록해 줍니다.

8. 명령프롬프트를 열고 ssh zero@192.168.1.xxx 형태로 ssh에 접속합니다.
   접속 시 yes/no/fingerprint를 물어보면 yes를 입력합니다.
   비밀번호는 위에서 설정한대로 0000를 입력합니다.

   ※ 만약 기기를 접속한 이력이 있는데 초기화 후 다시 접속하는 경우 접속이 차단되기도 합니다.
      이 때는 C:\Users\내ID\.ssh\ 안에 있는 known_hosts 파일을 삭제후 재시도 합니다.

9. 깃헙에서 소스 다운로드 받기
9-1. sudo apt install git  을 입력합니다. 도중에 물어보는 항목은 Y를 입력합니다.
  9-2. git clone https://github.com/canhackers/jupiter.git
       위 명령을 이용하여 소스를 다운로드 받습니다.
  9-3. 이미 설치된 소스를 업데이트 할 때는 git pull 명령어를 사용합니다.
     기기에서 로컬로 수정한 파일은 git stash 명령으로 변경점을 폐기할 수 있습니다.
     본인의 소스코드 변경점을 유지하고 싶다면 Github에 별도의 레포지토리 사본을 만들어 관리하시기 바랍니다.
10. sudo apt install screen (백그라운드에서 프로세스가 실행될수 있도록 하는 기능 설치)

11. 파이썬 가상환경 생성하기
라즈베리파이는 가상환경을 생성하지 않으면 설치할 수 있는 모듈의 종류에 한계가 있습니다.
10-1. cd jupiter    (경로 이동)
10-2. python3 -m venv .    (가상환경 생성.  . 점은 현재 폴더에 생성한다는 의미이니 빼먹지 마세요)

11. 가상환경 내 모듈 설치하기
11-1. cd bin
11-2. source activate
11-3. pip install python-can       (canbus 통신 모듈)
     pip install vcgencmd         (온도 모니터링용 모듈)
11-4. deactivate

12. 자동 실행 환경 만들기
12-1. sudo nano /etc/rc.local
12-2. exit 0 위 공간에 다음 두 줄 추가
 . /home/zero/jupiter/bin/activate
screen -dmS jupiter python /home/zero/jupiter/jupiter.py
12-3.  ctrl-x, y(저장)으로 빠져나옵니다.


13. sudo reboot으로 재부팅합니다.


★ NAVDY HUD 지원은 별도의 개조된 전용 펌웨어가 필요합니다.
단종으로 인해 구하기 힘든 물건이니 참고하시고, 기존 보유자 중 전용 펌웨어를 사용 중이지 않는 분은 카페 채팅으로 별도 문의 바랍니다.
사용을 위해서는 Clone 후 Jupiter 기기의 /home 경로에 mac_address 파일을 만들어 00:00:00:00:00:00 형태로 본인 기기의 Mac Address를 넣어야 합니다.

기본 설치법 외에 추가로 블루투스 페어링 절차가 필요합니다.


sudo bluetoothctl

scan on  (접속 가능한 블루투스 장치 목록이 뜹니다. Navdy를 찾으면 MAC Address도 알 수 있습니다.)

pair 54:ED:A3:xx:xx:xx  (본인 Navdy의 MAC Address를 찾아서)

confirm passkey 질문에서 yes 입력, Navdy에서도 Confirm을 눌러줘야 합니다.

trust 54:ED:A3:xx:xx:xx  (본인 Navdy의 MAC Address를 찾아서)

exit (bluetoothctl 빠져 나오기)

cd Jupiter

git checkout navdy  (나브디 브랜치로 변경. 기존 설치 과정에서 git clone 되어 있어야 함.)

sudo nano /home/mac_address

Navdy MAC Address 입력 54:ED:A3:xx:xx:xx (Ctrl-X, Y로 저장)

sudo apt-get install python3-dev

sudo apt-get install libbluetooth-dev

source ./bin/activate

pip3 install git+https://github.com/pybluez/pybluez.git#egg=PyBluez

sudo reboot
