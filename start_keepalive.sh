#!/bin/bash
# 启动 keepalive 常驻保活进程（nohup 方式，重启后需手动重新执行）
# 用法: ./start_keepalive.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PIDFILE="${SCRIPT_DIR}/keepalive.pid"

if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
    echo "keepalive 已在运行 (PID: $(cat "$PIDFILE"))"
    exit 0
fi

nohup python3 -u "${SCRIPT_DIR}/keepalive.py" >> "${SCRIPT_DIR}/keepalive.log" 2>&1 &
echo $! > "$PIDFILE"
echo "keepalive 已启动 (PID: $(cat "$PIDFILE"))"
echo "日志: ${SCRIPT_DIR}/keepalive.log"
