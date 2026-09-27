#!/bin/bash
export PORT=8804
cd /root/ai-manufacturing-zone
pkill -9 -f "/root/ai-manufacturing-zone/app.py" 2>/dev/null
pkill -9 -f "python3 app.py" 2>/dev/null
fuser -k 8804/tcp 2>/dev/null
sleep 2
setsid python3 /root/ai-manufacturing-zone/app.py > /root/ai-manufacturing-zone/server.log 2>&1 < /dev/null &
echo "ai-manufacturing-zone backend started on port 8804"
