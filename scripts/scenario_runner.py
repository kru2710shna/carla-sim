import carla
import os
import sys
import json
import time
import random
import subprocess

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.weather_presets import PRESETS
from sensors.camera import attach_rgb_camera
from sensors.gnss   import attach_gnss
from sensors.lidar  import attach_lidar


def create_session_folder(scenario_name, base="Data"):
    os.makedirs(base, exist_ok=True)
    existing = [
        d for d in os.listdir(base)
        if d.startswith("session_") and os.path.isdir(os.path.join(base, d))
    ]
    next_num = len(existing) + 1
    session  = f"session_{next_num:03d}_{scenario_name}"
    path     = os.path.join(base, session)
    os.makedirs(os.path.join(path, "images"), exist_ok=True)
    os.makedirs(os.path.join(path, "lidar"),  exist_ok=True)
    os.makedirs(os.path.join(path, "gnss"),   exist_ok=True)
    print(f"Session created: {path}")
    return path


def save_metadata(session_path, scenario_name, preset, map_name):
    metadata = {
        "scenario":         scenario_name,
        "description":      preset["description"],
        "map":              map_name,
        "traffic":          preset["traffic"],
        "pedestrians":      preset["pedestrians"],
        "duration_seconds": preset["duration"],
        "sensor_config": {
            "camera": "1920x1080, fov=105, sensor_tick=0.05",
            "lidar":  "32ch, range=50m, 100k pts/sec",
            "gnss":   "tick=0.05s"
        },
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    with open(os.path.join(session_path, "metadata.json"), "w") as f:
        json.dump(metadata, f, indent=4)
    print("Metadata saved.")


def spawn_ego_vehicle(world, client):
    """
    Spawns ego vehicle following CARLA docs pattern.
    Uses random spawn point and simple autopilot.
    """
    blueprint_library = world.get_blueprint_library()
    vehicle_bp = blueprint_library.find('vehicle.tesla.model3')
    vehicle_bp.set_attribute('role_name', 'hero')

    # try multiple random spawn points until one works
    spawn_points = world.get_map().get_spawn_points()
    random.shuffle(spawn_points)

    vehicle = None
    for sp in spawn_points:
        vehicle = world.try_spawn_actor(vehicle_bp, sp)
        if vehicle:
            print(f"Ego spawned at: {sp.location}")
            break

    if not vehicle:
        raise RuntimeError("Could not spawn ego vehicle")

    # simple autopilot as per CARLA docs
    vehicle.set_autopilot(True)
    print("Autopilot enabled")
    return vehicle


def spawn_npc_traffic(client, world, num_vehicles, num_pedestrians):
    """
    Uses CARLA's official generate_traffic.py approach.
    Spawns NPCs using Traffic Manager properly.
    """
    vehicles_list = []
    walkers_list  = []
    all_actors    = []

    blueprint_library = world.get_blueprint_library()
    spawn_points      = world.get_map().get_spawn_points()
    random.shuffle(spawn_points)

    # spawn vehicles
    vehicle_bps = blueprint_library.filter('vehicle.*')
    vehicle_bps = [bp for bp in vehicle_bps
                   if bp.get_attribute('number_of_wheels').as_int() == 4]

    for sp in spawn_points[:num_vehicles]:
        bp     = random.choice(vehicle_bps)
        actor  = world.try_spawn_actor(bp, sp)
        if actor:
            vehicles_list.append(actor)

    # set all NPCs to autopilot via TM
    tm = client.get_trafficmanager()
    tm.set_global_distance_to_leading_vehicle(2.0)
    for v in vehicles_list:
        v.set_autopilot(True, tm.get_port())

    print(f"Spawned {len(vehicles_list)} NPC vehicles")

    # spawn walkers
    walker_bp        = blueprint_library.filter('walker.pedestrian.*')
    walker_ctrl_bp   = blueprint_library.find('controller.ai.walker')
    walker_actors    = []

    for _ in range(num_pedestrians):
        loc = world.get_random_location_from_navigation()
        if not loc:
            continue
        bp  = random.choice(walker_bp)
        if bp.has_attribute('is_invincible'):
            bp.set_attribute('is_invincible', 'false')
        actor = world.try_spawn_actor(bp, carla.Transform(loc))
        if actor:
            walker_actors.append(actor)

    # spawn controllers for walkers
    ctrl_actors = []
    for walker in walker_actors:
        ctrl = world.try_spawn_actor(
            walker_ctrl_bp,
            carla.Transform(),
            attach_to=walker
        )
        if ctrl:
            ctrl_actors.append(ctrl)

    # start walker controllers
    world.wait_for_tick()
    for ctrl in ctrl_actors:
        ctrl.start()
        ctrl.go_to_location(world.get_random_location_from_navigation())
        ctrl.set_max_speed(1.4)

    all_actors = vehicles_list + walker_actors + ctrl_actors
    print(f"Spawned {len(walker_actors)} pedestrians")
    return all_actors


def cleanup_all(sensors, actors, vehicle):
    print("Cleaning up...")

    for sensor in sensors:
        try:
            if sensor and sensor.is_alive:
                sensor.stop()
        except Exception:
            pass

    for sensor in sensors:
        try:
            if hasattr(sensor, '_csv_file'):
                sensor._csv_file.close()
        except Exception:
            pass

    for sensor in sensors:
        try:
            if sensor and sensor.is_alive:
                sensor.destroy()
        except Exception:
            pass

    for actor in actors:
        try:
            if actor and actor.is_alive and 'controller' in actor.type_id:
                actor.stop()
        except Exception:
            pass

    for actor in actors:
        try:
            if actor and actor.is_alive:
                actor.destroy()
        except Exception:
            pass

    try:
        if vehicle and vehicle.is_alive:
            vehicle.destroy()
    except Exception:
        pass

    print("Cleanup complete.")


def run_scenario(scenario_name):
    if scenario_name not in PRESETS:
        print(f"Unknown scenario: {scenario_name}")
        return

    preset = PRESETS[scenario_name]

    client = carla.Client('localhost', 2000)
    client.set_timeout(10.0)
    world  = client.get_world()

    print(f"Map: {world.get_map().name}")
    print(f"Scenario: {scenario_name} — {preset['description']}")

    session_path = create_session_folder(scenario_name)
    save_metadata(session_path, scenario_name, preset, world.get_map().name)

    vehicle = None
    sensors = []
    actors  = []

    try:
        # 1. set weather
        world.set_weather(preset["weather"])
        print(f"Weather: {scenario_name}")

        # 2. spawn ego and enable autopilot
        vehicle = spawn_ego_vehicle(world, client)

        # 3. let ego move away from spawn (5 seconds)
        print("Letting ego vehicle settle...")
        time.sleep(5)

        # 4. spawn NPC traffic
        actors = spawn_npc_traffic(
            client, world,
            num_vehicles    = preset["traffic"],
            num_pedestrians = preset["pedestrians"]
        )

        # 5. attach sensors using vehicle extent for correct positioning
        extent = vehicle.bounding_box.extent

        camera = attach_rgb_camera(
            world, vehicle,
            save_path=os.path.join(session_path, "images")
        )
        gnss = attach_gnss(
            world, vehicle,
            save_path=os.path.join(session_path, "gnss")
        )
        lidar = attach_lidar(
            world, vehicle,
            save_path=os.path.join(session_path, "lidar")
        )
        sensors = [camera, gnss, lidar]

        # 6. warmup
        print("Sensor warmup (3s)...")
        time.sleep(3)

        # 7. record
        print(f"Recording {preset['duration']}s...")
        time.sleep(preset["duration"])

    except KeyboardInterrupt:
        print("\nStopped by user.")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        cleanup_all(sensors, actors, vehicle)
        print(f"Done → {session_path}")


if __name__ == "__main__":
    if len(sys.argv) == 2:
        run_scenario(sys.argv[1])
    else:
        for scenario in PRESETS.keys():
            print(f"\n{'='*50}")
            print(f"SCENARIO: {scenario.upper()}")
            print(f"{'='*50}")
            subprocess.run([sys.executable, __file__, scenario])
            print("Waiting 8s...")
            time.sleep(8)

        print("\nALL SCENARIOS COMPLETE!")