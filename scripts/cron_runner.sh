#!/bin/bash
# cron_runner.sh — cron job 실행 + 실패 시 Discord 알림
# 사용법: cron_runner.sh <job_name> <command...>
#
# 환경변수:
#   DISCORD_BOT_TOKEN  — Discord 봇 토큰
#   DISCORD_ALERT_CHANNEL — 알림 채널 ID (기본: 1502591461063917670)

set -euo pipefail

JOB_NAME="${1:?job name required}"
shift

DISCORD_TOKEN="${DISCORD_BOT_TOKEN:-}"
CHANNEL_ID="${DISCORD_ALERT_CHANNEL:-1502591461063917670}"
LOG_FILE="/tmp/cron_${JOB_NAME}.log"

# 환경변수 미설정 시 .env에서 로드
if [ -z "$DISCORD_TOKEN" ]; then
    ENV_FILE="$HOME/.claude/channels/discord/.env"
    if [ -f "$ENV_FILE" ]; then
        DISCORD_TOKEN=$(grep "^DISCORD_BOT_TOKEN=" "$ENV_FILE" | cut -d= -f2)
    fi
fi

send_discord_alert() {
    local message="$1"
    if [ -z "$DISCORD_TOKEN" ]; then return; fi
    curl -s -X POST \
        "https://discord.com/api/v10/channels/${CHANNEL_ID}/messages" \
        -H "Authorization: Bot ${DISCORD_TOKEN}" \
        -H "Content-Type: application/json" \
        -d "{\"content\": $(echo "$message" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))')}" \
        > /dev/null 2>&1 || true
}

START_TIME=$(date '+%Y-%m-%d %H:%M:%S')

# 실행
set +e
"$@" > "$LOG_FILE" 2>&1
EXIT_CODE=$?
set -e

END_TIME=$(date '+%Y-%m-%d %H:%M:%S')

if [ $EXIT_CODE -ne 0 ]; then
    # 실패 — 마지막 20줄 로그 첨부
    TAIL=$(tail -20 "$LOG_FILE" 2>/dev/null || echo "(로그 없음)")
    send_discord_alert "⛔ [CRON 오류] **${JOB_NAME}** 실패 (exit ${EXIT_CODE})
시작: ${START_TIME}
종료: ${END_TIME}
\`\`\`
${TAIL}
\`\`\`"
    cat "$LOG_FILE"
    exit $EXIT_CODE
fi

# 성공 — 로그 출력
cat "$LOG_FILE"
exit 0
