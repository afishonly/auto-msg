#!/bin/bash
# 每天随机时间发送一次（配合 crontab 每分钟调用）
# 以当天日期为随机种子生成发送时间，同一天内稳定，跨天自动变化。
# 用法: 添加到 crontab 每分钟执行（见 install_cron.sh）
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG="${SCRIPT_DIR}/config.json"
LOG="${SCRIPT_DIR}/run.log"
STATEFILE="${SCRIPT_DIR}/.send_done_date"

# 读取窗口与固定时间
WINDOW_START=$(python3 -c "import json;c=json.load(open('${CONFIG}'));w=c.get('send_window',['08:00','22:00']);print(w[0])" 2>/dev/null)
WINDOW_END=$(python3 -c "import json;c=json.load(open('${CONFIG}'));w=c.get('send_window',['08:00','22:00']);print(w[1])" 2>/dev/null)
SEND_TIMES=$(python3 -c "import json;c=json.load(open('${CONFIG}'));print(c.get('send_times',['09:00'])[0])" 2>/dev/null)

# 计算今天的随机目标时间
TARGET=$(python3 - "${WINDOW_START}" "${WINDOW_END}" "${SEND_TIMES}" <<'PYEOF'
import random, sys
w_start, w_end, fallback = sys.argv[1], sys.argv[2], sys.argv[3]
def parse(hhmm):
    h, m = map(int, hhmm.split(":"))
    return h * 60 + m
try:
    s, e = parse(w_start), parse(w_end)
    if e < s:
        e = 23 * 60 + 59
    random.seed(__import__("datetime").date.today().isoformat())
    p = random.randint(s, e)
    print(f"{p // 60:02d}:{p % 60:02d}")
except Exception:
    print(fallback)
PYEOF
)

TODAY=$(date +%Y-%m-%d)
NOW=$(date +%H:%M)

LAST_DONE=""
[ -f "$STATEFILE" ] && LAST_DONE=$(cat "$STATEFILE")

if [ "$LAST_DONE" != "$TODAY" ]; then
    if [ "$NOW" \> "$TARGET" ] || [ "$NOW" = "$TARGET" ]; then
        echo "[$(date '+%F %T')] 到达今日随机发送时间 ${TARGET}，开始发送" >> "$LOG"
        cd "${SCRIPT_DIR}" && python3 send_msg.py >> "$LOG" 2>&1
        echo "$TODAY" > "$STATEFILE"
        echo "[$(date '+%F %T')] 今日发送完成" >> "$LOG"
    fi
fi
