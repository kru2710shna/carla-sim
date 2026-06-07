#!/bin/bash

CARLA_PATH="$HOME/Downloads/CARLA_0.9.15"

echo "Killing any existing CARLA instances..."
pkill -f CarlaUE4 2>/dev/null
pkill -f CarlaUE4-Linux 2>/dev/null
sleep 5

# free ports
fuser -k 2000/tcp 2>/dev/null
fuser -k 2001/tcp 2>/dev/null
fuser -k 2002/tcp 2>/dev/null
sleep 3

echo "Freeing memory..."
sync && echo 3 | sudo tee /proc/sys/vm/drop_caches > /dev/null

echo "Starting CARLA..."
"$CARLA_PATH/CarlaUE4.sh" \
    -RenderOffScreen \
    -opengl \
    -quality-level=High \
    -benchmark &

CARLA_PID=$!
echo "CARLA PID: $CARLA_PID"

echo "Waiting for CARLA to boot (30s)..."
sleep 30

echo "Checking connection..."
for i in {1..10}; do
    result=$(python3 -c "
import carla
try:
    client = carla.Client('localhost', 2000)
    client.set_timeout(10.0)
    v = client.get_server_version()
    print(f'CARLA ready! version={v}')
except Exception as e:
    print(f'NOT READY: {e}')
" 2>&1)
    echo "Attempt $i: $result"

    if echo "$result" | grep -q "CARLA ready"; then
        echo "CARLA is up!"
        break
    fi

    if [ $i -eq 10 ]; then
        echo "CARLA failed to start"
        exit 1
    fi
    sleep 5
done

echo ""
nvidia-smi --query-gpu=memory.used,memory.free --format=csv
echo "Ready!"