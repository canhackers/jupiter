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


설치 가이드는 추후 업데이트 할 예정입니다.

당분간 https://cafe.naver.com/canhacker 를 방문해 확인해주세요.

후원계좌
https://toss.me/canhackers




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

cd jupiter

git checkout navdy  (나브디 브랜치로 변경. 기존 설치 과정에서 git clone 되어 있어야 함.)

sudo nano /home/mac_address

Navdy MAC Address 입력 54:ED:A3:xx:xx:xx (Ctrl-X, Y로 저장)

sudo apt-get install python3-dev

sudo apt-get install libbluetooth-dev

source ./bin/activate

pip3 install git+https://github.com/pybluez/pybluez.git#egg=PyBluez

sudo reboot