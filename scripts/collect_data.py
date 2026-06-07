import carla
import os
import sys
import json
import time
import random
import subprocess

sys.path.append('/home/tmpadmin/Downloads/CARLA_0.9.15/PythonAPI/carla')
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.navigation.behavior_agent import BehaviorAgent
from config.route            import LOOP_ROUTE
from config.weather_presets  import PRESETS
from utils.helper            import connect, spawn_ego, spawn_npc_vehicles, spawn_pedestrians, cleanup
from sensors.camera import attach_rgb_camera
from sensors.gnss   import attach_gnss
from sensors.lidar  import attach_lidar
from sensors.radar  import attach_radar


def create_session(scenario_name, base="data"):
    os.makedirs(base, exist_ok=True)
    existing = [
        d for d in os.listdir(base)
        if d.startswith("session_") and os.path.isdir(os.path.join(base, d))
    ]
    num  = len(existing) + 1
    name = f"session_{num:03d}_{scenario_name}"
    path = os.path.join(base, name)
    for sub in ["camera/front", "lidar", "radar", "gnss"]:
        os.makedirs(os.path.join(path, sub), exist_ok=True)
    print(f"Session: {path}")
    return path


def save_metadata(path, scenario, preset):
    meta = {
        "scenario":    scenario,
        "description": preset["description"],
        "map":         LOOP_ROUTE["map"],
        "route":       LOOP_ROUTE["description"],
        "traffic":     preset["traffic"],
        "pedestrians": preset["pedestrians"],
        "duration":    preset["duration"],
        "sync_mode":   True,
        "fps":         20,
        "sensors": {
            "camera_front": {
                "type":       "sensor.camera.rgb",
                "resolution": [1280, 720],
                "fov":        90,
                "mount":      {"x": 1.5, "y": 0.0, "z": 2.4,
                               "pitch": 0, "yaw": 0, "roll": 0}
            },
            "lidar": {
                "type":                "sensor.lidar.ray_cast",
                "channels":            16,
                "range":               50,
                "points_per_second":   50000,
                "rotation_frequency":  20,
                "mount":               {"x": 0.0, "y": 0.0, "z": 2.8,
                                        "pitch": 0, "yaw": 0, "roll": 0}
            },
            "radar": {
                "type":           "sensor.other.radar",
                "horizontal_fov": 30,
                "vertical_fov":   10,
                "range":          100,
                "mount":          {"x": 2.0, "y": 0.0, "z": 1.0,
                                   "pitch": 5, "yaw": 0, "roll": 0}
            },
            "gnss": {
                "type":  "sensor.other.gnss",
                "mount": {"x": 0.0, "y": 0.0, "z": 2.0}
            }
        },
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    with open(os.path.join(path, "metadata.json"), "w") as f:
        json.dump(meta, f, indent=4)
    print("Metadata saved.")


def run(scenario_name):
    if scenario_name not in PRESETS:
        print(f"Unknown scenario: {scenario_name}")
        print(f"Available: {list(PRESETS.keys())}")
        return

    preset       = PRESETS[scenario_name]
    session_path = create_session(scenario_name)
    save_metadata(session_path, scenario_name, preset)

    client, world     = connect()
    original_settings = world.get_settings()
    spawn_points      = world.get_map().get_spawn_points()

    vehicle     = None
    sensors     = []
    actors      = []
    annotations = []

    try:
        # 1. sync mode ON
        settings = world.get_settings()
        settings.synchronous_mode    = True
        settings.fixed_delta_seconds = 0.05   # 20 FPS
        world.apply_settings(settings)
        tm = client.get_trafficmanager()
        tm.set_synchronous_mode(True)
        print("Sync mode ON (20 FPS)")

        # 2. set weather
        world.set_weather(preset["weather"])
        world.tick()
        print(f"Weather: {scenario_name}")

        # 3. spawn ego at fixed route start
        vehicle = spawn_ego(world, LOOP_ROUTE["start_index"])
        world.tick()

        # 4. BehaviorAgent
        agent = BehaviorAgent(vehicle, behavior='aggressive')
        agent.ignore_traffic_lights(active=True)
        next_dest = spawn_points[LOOP_ROUTE["spawn_indices"][1]].location
        agent.set_destination(next_dest)
        print("BehaviorAgent ready (aggressive, ignores lights)")

        # 5. spawn traffic off-route
        actors  = spawn_npc_vehicles(client, world, count=preset["traffic"])
        actors += spawn_pedestrians(world, count=preset["pedestrians"])

        # 6. attach all 4 sensors
        camera = attach_rgb_camera(world, vehicle,
                    save_path=os.path.join(session_path, "camera/front"))
        gnss   = attach_gnss(world, vehicle,
                    save_path=os.path.join(session_path, "gnss"))
        lidar  = attach_lidar(world, vehicle,
                    save_path=os.path.join(session_path, "lidar"))
        radar  = attach_radar(world, vehicle,
                    save_path=os.path.join(session_path, "radar"))
        sensors = [camera, gnss, lidar, radar]

        # 7. warmup — let sensors initialise
        print("Warming up (60 ticks)...")
        for _ in range(60):
            world.tick()

        # 8. main sync loop
        print(f"Recording for {preset['duration']}s...")
        max_ticks  = int(preset["duration"] / 0.05)
        tick_count = 0
        route_idx  = 1

        while tick_count < max_ticks:
            world.tick()
            tick_count += 1

            # advance agent to next waypoint when current is reached
            if agent.done():
                route_idx = (route_idx + 1) % len(LOOP_ROUTE["spawn_indices"])
                next_sp   = spawn_points[LOOP_ROUTE["spawn_indices"][route_idx]]
                agent.set_destination(next_sp.location)
                print(f"  → waypoint: spawn[{LOOP_ROUTE['spawn_indices'][route_idx]}]")

            # agent drives
            control = agent.run_step()
            vehicle.apply_control(control)

            # log ego pose every tick
            t = vehicle.get_transform()
            v = vehicle.get_velocity()
            annotations.append({
                "frame":     tick_count,
                "timestamp": round(tick_count * 0.05, 3),
                "ego_pose": {
                    "x":     t.location.x,
                    "y":     t.location.y,
                    "z":     t.location.z,
                    "yaw":   t.rotation.yaw,
                    "pitch": t.rotation.pitch,
                    "roll":  t.rotation.roll
                },
                "ego_velocity": {
                    "vx": v.x,
                    "vy": v.y,
                    "vz": v.z
                }
            })

            if tick_count % 400 == 0:
                loc = vehicle.get_location()
                print(f"  tick {tick_count}/{max_ticks} | "
                      f"x={loc.x:.1f} y={loc.y:.1f}")

    except KeyboardInterrupt:
        print("\nStopped by user.")
    except Exception as e:
        import traceback
        print(f"Error: {e}")
        traceback.print_exc()
    finally:
        ann_path = os.path.join(session_path, "annotations.json")
        with open(ann_path, "w") as f:
            json.dump(annotations, f, indent=2)
        print(f"Annotations saved: {len(annotations)} frames")

        cleanup(world, original_settings, sensors, actors, vehicle)
        print(f"Done → {session_path}")


if __name__ == "__main__":
    if len(sys.argv) == 2:
        run(sys.argv[1])
    else:
        for scenario in PRESETS.keys():
            print(f"\n{'='*60}")
            print(f"SCENARIO: {scenario.upper()}")
            print(f"{'='*60}")
            subprocess.run([sys.executable, __file__, scenario])
            print("Waiting 15s before next scenario...")
            time.sleep(15)
        print("\nALL SCENARIOS COMPLETE!")