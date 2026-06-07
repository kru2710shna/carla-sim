import carla
import os
import sys
import json
import time
import random
import subprocess

# add CARLA agents to path
sys.path.append('/home/tmpadmin/Downloads/CARLA_0.9.15/PythonAPI/carla')
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.navigation.behavior_agent import BehaviorAgent
from config.route import ROUTES
from config.weather_presets import PRESETS
from sensors.camera import attach_rgb_camera
from sensors.lidar import attach_lidar


def create_session_folder(route_name, scenario_name, base="Data"):
    os.makedirs(base, exist_ok=True)
    existing = [
        d for d in os.listdir(base)
        if d.startswith("session_") and os.path.isdir(os.path.join(base, d))
    ]
    next_num  = len(existing) + 1
    session   = f"session_{next_num:03d}_{route_name}_{scenario_name}"
    path      = os.path.join(base, session)
    os.makedirs(os.path.join(path, "images"), exist_ok=True)
    os.makedirs(os.path.join(path, "lidar"),  exist_ok=True)
    print(f"Session: {path}")
    return path


def save_metadata(session_path, route_name, scenario_name, route, preset, map_name):
    metadata = {
        "route":            route_name,
        "scenario":         scenario_name,
        "description":      route["description"],
        "weather":          preset["description"],
        "map":              map_name,
        "start_index":      route["start_index"],
        "end_index":        route["end_index"],
        "traffic":          preset["traffic"],
        "pedestrians":      preset["pedestrians"],
        "agent":            "BehaviorAgent — normal",
        "sync_mode":        True,
        "fixed_delta_seconds": 0.05,
        "sensor_config": {
            "camera": "1280x720, fov=90, x=1.5 z=2.4",
            "lidar":  "32ch, range=50m, 100k pts/sec"
        },
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    with open(os.path.join(session_path, "metadata.json"), "w") as f:
        json.dump(metadata, f, indent=4)
    print("Metadata saved.")


def spawn_npc_traffic(client, world, num_vehicles, num_pedestrians):
    actors = []
    bp_lib = world.get_blueprint_library()

    # vehicles — 4 wheel only
    vehicle_bps  = [
        bp for bp in bp_lib.filter('vehicle.*')
        if bp.get_attribute('number_of_wheels').as_int() == 4
    ]
    spawn_points = world.get_map().get_spawn_points()
    random.shuffle(spawn_points)

    tm = client.get_trafficmanager()
    tm.set_global_distance_to_leading_vehicle(2.0)
    tm.set_synchronous_mode(True)  # TM must also be in sync mode

    for sp in spawn_points[:num_vehicles]:
        bp    = random.choice(vehicle_bps)
        actor = world.try_spawn_actor(bp, sp)
        if actor:
            actor.set_autopilot(True, tm.get_port())
            actors.append(actor)

    print(f"Spawned {len(actors)} NPC vehicles")

    # pedestrians
    walker_bp      = bp_lib.filter('walker.pedestrian.*')
    walker_ctrl_bp = bp_lib.find('controller.ai.walker')

    ped_actors  = []
    ctrl_actors = []

    for _ in range(num_pedestrians):
        loc = world.get_random_location_from_navigation()
        if not loc:
            continue
        bp = random.choice(walker_bp)
        if bp.has_attribute('is_invincible'):
            bp.set_attribute('is_invincible', 'false')
        actor = world.try_spawn_actor(bp, carla.Transform(loc))
        if actor:
            ped_actors.append(actor)

    world.tick()

    for ped in ped_actors:
        ctrl = world.try_spawn_actor(
            walker_ctrl_bp,
            carla.Transform(),
            attach_to=ped
        )
        if ctrl:
            ctrl_actors.append(ctrl)

    world.tick()

    for ctrl in ctrl_actors:
        ctrl.start()
        ctrl.go_to_location(world.get_random_location_from_navigation())
        ctrl.set_max_speed(1.4)

    actors.extend(ped_actors)
    actors.extend(ctrl_actors)
    print(f"Spawned {len(ped_actors)} pedestrians")
    return actors


def cleanup_all(world, sensors, actors, vehicle, original_settings):
    print("Cleaning up...")

    # restore async mode first
    try:
        world.apply_settings(original_settings)
    except Exception:
        pass

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


def run(route_name, scenario_name):
    """
    Runs one route + weather combination using BehaviorAgent.
    """
    if route_name not in ROUTES:
        print(f"Unknown route: {route_name}")
        return
    if scenario_name not in PRESETS:
        print(f"Unknown scenario: {scenario_name}")
        return

    route  = ROUTES[route_name]
    preset = PRESETS[scenario_name]

    client = carla.Client('localhost', 2000)
    client.set_timeout(60.0)
    world  = client.get_world()

    print(f"\nMap:      {world.get_map().name}")
    print(f"Route:    {route_name} — {route['description']}")
    print(f"Weather:  {scenario_name} — {preset['description']}")

    session_path     = create_session_folder(route_name, scenario_name)
    original_settings = world.get_settings()
    save_metadata(session_path, route_name, scenario_name, route, preset, world.get_map().name)

    vehicle = None
    sensors = []
    actors  = []

    try:
        # 1. enable synchronous mode
        settings = world.get_settings()
        settings.synchronous_mode    = True
        settings.fixed_delta_seconds = 0.05   # 20 FPS
        world.apply_settings(settings)
        print("Sync mode ON (20 FPS)")

        # 2. set weather
        world.set_weather(preset["weather"])
        world.tick()

        # 3. spawn ego at fixed route start
        spawn_points = world.get_map().get_spawn_points()
        start_transform = spawn_points[route["start_index"]]
        end_location    = spawn_points[route["end_index"]].location

        bp_lib     = world.get_blueprint_library()
        vehicle_bp = bp_lib.find('vehicle.tesla.model3')
        vehicle_bp.set_attribute('role_name', 'hero')
        vehicle = world.try_spawn_actor(vehicle_bp, start_transform)

        if not vehicle:
            print("Failed to spawn ego vehicle.")
            return

        world.tick()
        print(f"Ego spawned at spawn[{route['start_index']}]")

        # 4. create BehaviorAgent
        agent = BehaviorAgent(vehicle, behavior='normal')
        agent.set_destination(end_location)
        print(f"BehaviorAgent destination: spawn[{route['end_index']}]")

        # 5. spawn NPC traffic
        actors = spawn_npc_traffic(
            client, world,
            num_vehicles    = preset["traffic"],
            num_pedestrians = preset["pedestrians"]
        )

        # 6. attach sensors
        camera = attach_rgb_camera(world, vehicle,
                    save_path=os.path.join(session_path, "images"))
        lidar  = attach_lidar(world, vehicle,
                    save_path=os.path.join(session_path, "lidar"))
        sensors = [camera, lidar]

        # 7. warmup ticks
        print("Warming up (60 ticks)...")
        for _ in range(60):
            world.tick()

        # 8. main loop — agent drives the car
        print("Recording — BehaviorAgent driving...")
        tick_count = 0
        max_ticks  = int(preset["duration"] / 0.05)  # duration in ticks

        settings = world.get_settings()
        settings.synchronous_mode    = True
        settings.fixed_delta_seconds = 0.05
        world.apply_settings(settings)

        
        while tick_count < max_ticks:
            world.tick()
            tick_count += 1

            if agent.done():
                print(f"Route complete at tick {tick_count}!")
                # loop back — set destination again for more data
                agent.set_destination(
                    random.choice(spawn_points).location
                )

            # agent computes and applies control every tick
            control = agent.run_step()
            vehicle.apply_control(control)

            # log progress every 200 ticks
            if tick_count % 200 == 0:
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
        cleanup_all(world, sensors, actors, vehicle, original_settings)
        print(f"Done → {session_path}")


if __name__ == "__main__":
    if len(sys.argv) == 3:
        # called as subprocess: route_name scenario_name
        run(sys.argv[1], sys.argv[2])
    else:
        # run all combinations
        for route_name in ROUTES.keys():
            for scenario_name in PRESETS.keys():
                print(f"\n{'='*60}")
                print(f"ROUTE: {route_name.upper()} | SCENARIO: {scenario_name.upper()}")
                print(f"{'='*60}")
                subprocess.run([
                    sys.executable, __file__,
                    route_name, scenario_name
                ])
                print("Waiting 10s...")
                time.sleep(10)

        print("\nALL 18 SESSIONS COMPLETE!")