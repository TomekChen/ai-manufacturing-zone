#!/bin/bash
LOG="/root/ai-manufacturing-zone/watchdog.log"
while true; do
    python3 -c "import socket; exit(0 if socket.socket().connect_ex(('127.0.0.1',8804))==0 else 1)" 2>/dev/null
    if [ $? -ne 0 ]; then
        echo "$(date) service down, restarting..." >> "$LOG"
        bash /root/ai-manufacturing-zone/start.sh
    fi
    sleep 30
done
