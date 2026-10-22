#!/bin/bash
# 停止 keepalive 常驻保活进程
# 用法: ./stop_keepalive.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PIDFILE="${SCRIPT_DIR}/keepalive.pid"

if [ -f "$PIDFILE" ]; then
    PID="$(cat "$PIDFILE")"
    if kill -0 "$PID" 2>/dev/null; then
        kill "$PID"
        echo "keepalive 已停止 (PID: $PID)"
    else
        echo "keepalive 进程不存在"
    fi
    rm -f "$PIDFILE"
else
    echo "未找到 PID 文件，keepalive 可能未运行"
fi
