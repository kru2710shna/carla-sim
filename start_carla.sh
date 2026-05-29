#!/bin/bash

CARLA_PATH="$HOME/Downloads/CARLA_0.9.15"

echo "Starting CARLA..."

VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/nvidia_icd.json \
    "$CARLA_PATH/CarlaUE4.sh" \
    -quality-level=High \
    -ResX=1280 \
    -ResY=720 &

echo "Waiting for CARLA to boot..."
sleep 15

echo "Checking connection..."
python3 -c "
import carla
try:
    client = carla.Client('localhost', 2000)
    client.set_timeout(60.0)
    client.get_server_version()
    print('CARLA is ready!')
except Exception as e:
    print(f'CARLA not ready: {e}')
"