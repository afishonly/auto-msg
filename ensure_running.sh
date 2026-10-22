#!/bin/sh
# auto-msg 自愈守护：确保 keepalive.py 在运行（由 .zshrc/.bashrc 开机钩子调用）
DIR="/workspace/auto_web_msg_deploy/auto_web_msg"
LOG="$DIR/autostart.log"
LOCK="/tmp/.autostart_msg.lock"

# 防并发（多个 shell 同时打开时只拉起一次）
[ -f "$LOCK" ] && exit 0
touch "$LOCK"
trap 'rm -f "$LOCK"' EXIT

# 已在运行则直接退出
if pgrep -f "keepalive.py" >/dev/null 2>&1; then
    exit 0
fi

echo "[$(date '+%F %T')] [自启] 未检测到 keepalive，正在自动拉起..." >> "$LOG"
cd "$DIR" || { echo "[$(date '+%F %T')] [自启] 进入目录失败" >> "$LOG"; exit 1; }
./start_keepalive.sh >> "$LOG" 2>&1
sleep 2
if pgrep -f "keepalive.py" >/dev/null 2>&1; then
    echo "[$(date '+%F %T')] [自启] keepalive 已成功拉起" >> "$LOG"
else
    echo "[$(date '+%F %T')] [自启] 拉起失败，请检查 start_keepalive.sh" >> "$LOG"
fi
