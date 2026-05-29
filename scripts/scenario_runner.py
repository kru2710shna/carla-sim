import sys
sys.path.append('/home/tmpadmin/Downloads/CARLA_0.9.15/PythonAPI/carla')
from agents.navigation.behavior_agent import BehaviorAgent

def run_scenario(scenario_name, route_name):
    # ... setup world, weather, session folder ...

    # STEP 1 — enable synchronous mode
    settings = world.get_settings()
    settings.synchronous_mode = True
    settings.fixed_delta_seconds = 0.05  # 20 FPS
    world.apply_settings(settings)

    # STEP 2 — spawn at fixed route start
    start = spawn_points[route["start_index"]]
    end   = spawn_points[route["end_index"]].location
    vehicle = world.try_spawn_actor(vehicle_bp, start)

    # STEP 3 — create BehaviorAgent
    agent = BehaviorAgent(vehicle, behavior='normal')
    agent.set_destination(end)

    # STEP 4 — attach sensors
    camera = attach_rgb_camera(world, vehicle, ...)
    gnss   = attach_gnss(world, vehicle, ...)
    lidar  = attach_lidar(world, vehicle, ...)

    # STEP 5 — run loop (THIS is the key change)
    while True:
        world.tick()              # advance simulation one step

        if agent.done():
            print("Route complete!")
            break

        # agent computes steering/throttle/brake
        control = agent.run_step()
        vehicle.apply_control(control)

    # STEP 6 — disable sync mode and cleanup
    settings.synchronous_mode = False
    world.apply_settings(settings)
    cleanup_all(sensors, actors, vehicle)