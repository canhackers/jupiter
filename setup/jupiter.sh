#!/usr/bin/env bash

set -euo pipefail

SERVICE_NAME="${SERVICE_NAME:-jupiter.service}"
LOG_PID=""

require_command() {
    command -v "$1" >/dev/null 2>&1 || {
        printf "'%s' 명령을 찾을 수 없습니다.\n" "$1" >&2
        exit 1
    }
}

stop_log_follow() {
    if [[ -n "${LOG_PID}" ]] && kill -0 "${LOG_PID}" >/dev/null 2>&1; then
        kill "${LOG_PID}" >/dev/null 2>&1 || true
        wait "${LOG_PID}" >/dev/null 2>&1 || true
    fi
}

exit_monitor_only() {
    printf '\n모니터링만 종료합니다. %s 서비스는 계속 실행됩니다.\n' "${SERVICE_NAME}"
    stop_log_follow
    exit 0
}

stop_service_and_exit() {
    trap - INT TERM
    printf '\nCtrl+C 감지: %s 서비스를 중지합니다...\n' "${SERVICE_NAME}"
    stop_log_follow
    sudo systemctl stop "${SERVICE_NAME}" || true
    if sudo systemctl is-active --quiet "${SERVICE_NAME}"; then
        printf '%s 서비스 중지에 실패했습니다. 상태를 확인하세요.\n' "${SERVICE_NAME}" >&2
        sudo systemctl --no-pager --full status "${SERVICE_NAME}" || true
        exit 1
    fi
    printf '%s 서비스를 중지했습니다.\n' "${SERVICE_NAME}"
    exit 130
}

trap stop_service_and_exit INT TERM
trap stop_log_follow EXIT

require_command sudo
require_command journalctl
require_command systemctl

sudo -v

if ! sudo systemctl cat "${SERVICE_NAME}" >/dev/null 2>&1; then
    printf '%s 서비스가 등록되어 있지 않습니다.\n' "${SERVICE_NAME}" >&2
    printf '먼저 설치기를 실행하세요: bash setup/install_interactive.sh\n' >&2
    exit 1
fi

printf '\nJupiter 실행/모니터링 세션\n'
printf '- 서비스가 꺼져 있으면 먼저 시작합니다.\n'
printf '- 서비스가 이미 실행 중이면 바로 로그를 표시합니다.\n'
printf '- q: 모니터링만 종료하고 서비스는 계속 실행\n'
printf '- Ctrl+C: %s 서비스 중지 후 종료\n\n' "${SERVICE_NAME}"

if sudo systemctl is-active --quiet "${SERVICE_NAME}"; then
    printf '%s 서비스 상태: active\n\n' "${SERVICE_NAME}"
else
    printf '%s 서비스가 꺼져 있어 시작합니다...\n' "${SERVICE_NAME}"
    sudo systemctl start "${SERVICE_NAME}"
    sleep 3
    if sudo systemctl is-active --quiet "${SERVICE_NAME}"; then
        printf '%s 서비스를 시작했습니다.\n\n' "${SERVICE_NAME}"
    else
        printf '%s 서비스 시작에 실패했습니다. 최근 로그를 표시합니다.\n\n' "${SERVICE_NAME}" >&2
        sudo journalctl -u "${SERVICE_NAME}" -n 120 --no-pager || true
        exit 1
    fi
fi

sudo journalctl -u "${SERVICE_NAME}" -n 80 -f -o cat &
LOG_PID="$!"

while kill -0 "${LOG_PID}" >/dev/null 2>&1; do
    key=""
    if IFS= read -r -s -n 1 -t 1 key; then
        case "${key}" in
            q|Q) exit_monitor_only ;;
        esac
    fi
done

wait "${LOG_PID}" || true
