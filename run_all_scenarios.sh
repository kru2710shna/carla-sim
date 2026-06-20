#!/bin/bash

SCENARIOS=("baseline" "rain" "fog" "night" "strom" "heavy_traffic")

for scenario in "${SCENARIOS[@]}"; do
    echo ""
    echo "============================================================"
    echo "COLLECTING: $scenario"
    echo "============================================================"

    # kill any existing CARLA and wait for full VRAM release
    pkill -9 -f CarlaUE4 2>/dev/null
    sleep 10
    fuser -k 2000/tcp 2>/dev/null
    fuser -k 2001/tcp 2>/dev/null
    sleep 5

    # free system memory
    sync
    echo 3 | sudo tee /proc/sys/vm/drop_caches > /dev/null

    # wait until VRAM is actually freed (under 1000MB used)
    echo "Waiting for VRAM to clear..."
    for i in {1..12}; do
        used=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits)
        echo "  VRAM used: ${used}MB"
        if [ "$used" -lt 1000 ]; then
            echo "  VRAM clear"
            break
        fi
        sleep 5
    done

    # start CARLA
    VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/nvidia_icd.json \
        ~/Downloads/CARLA_0.9.15/CarlaUE4.sh \
        -RenderOffScreen -quality-level=Epic -benchmark -fps=20 &

    echo "Waiting for CARLA to boot..."
    sleep 30

    for i in {1..10}; do
        if python3 -c "import carla; carla.Client('localhost',2000).get_server_version()" 2>/dev/null; then
            echo "CARLA ready"
            break
        fi
        sleep 5
    done

    python3 scripts/collect_data.py "$scenario"
    echo "Done with $scenario"
done

pkill -9 -f CarlaUE4 2>/dev/null

echo ""
echo "ALL 6 SCENARIOS COMPLETE!"
for session in data/session_*; do
    python3 scripts/validate_session.py "$session"
done