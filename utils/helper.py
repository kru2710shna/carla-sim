import carla
import random


def connect(host="localhost", port=2000, timeout=60.0):
    """Connect to CARLA and return client + world."""
    client = carla.Client(host, port)
    client.set_timeout(timeout)
    world = client.get_world()
    print(f"Connected: {world.get_map().name}")
    return client, world


def set_sync_mode(world, delta=0.05):
    """Enable synchronous mode. Returns original settings for restore."""
    original = world.get_settings()
    settings = world.get_settings()
    settings.synchronous_mode    = True
    settings.fixed_delta_seconds = delta
    world.apply_settings(settings)
    print(f"Sync mode ON ({int(1/delta)} FPS)")
    return original


def restore_async_mode(world, original_settings):
    """Restore original async settings."""
    try:
        world.apply_settings(original_settings)
        print("Async mode restored")
    except Exception:
        pass


def spawn_ego(world, spawn_index):
    """Spawn Tesla Model3 at a fixed spawn point."""
    bp_lib    = world.get_blueprint_library()
    vehicle_bp = bp_lib.find('vehicle.tesla.model3')
    vehicle_bp.set_attribute('role_name', 'hero')
    sp = world.get_map().get_spawn_points()[spawn_index]
    vehicle = world.try_spawn_actor(vehicle_bp, sp)
    if vehicle:
        print(f"Ego spawned at spawn[{spawn_index}] "
              f"x={sp.location.x:.1f} y={sp.location.y:.1f}")
    else:
        raise RuntimeError(f"Failed to spawn ego at spawn[{spawn_index}]")
    return vehicle


def spawn_npc_vehicles(client, world, count=20):
    """
    Batch spawn NPC vehicles at spawn points NOT on our route.
    Batch spawning is more memory efficient than individual spawns.
    """
    from config.route import LOOP_ROUTE
    route_indices = set(LOOP_ROUTE["spawn_indices"])

    bp_lib = world.get_blueprint_library()
    vehicle_bps = [
        bp for bp in bp_lib.filter('vehicle.*')
        if bp.get_attribute('number_of_wheels').as_int() == 4
    ]

    spawn_points = world.get_map().get_spawn_points()
    safe_spawns  = [
        sp for i, sp in enumerate(spawn_points)
        if i not in route_indices
    ]
    random.shuffle(safe_spawns)

    tm      = client.get_trafficmanager()
    tm_port = tm.get_port()
    tm.set_global_distance_to_leading_vehicle(2.5)
    tm.set_synchronous_mode(True)

    # batch spawn — much lighter on memory
    batch = []
    for sp in safe_spawns[:count]:
        bp = random.choice(vehicle_bps)
        batch.append(
            carla.command.SpawnActor(bp, sp)
            .then(carla.command.SetAutopilot(
                carla.command.FutureActor, True, tm_port))
        )

    results = client.apply_batch_sync(batch, True)
    actors  = [
        world.get_actor(r.actor_id)
        for r in results
        if not r.error
    ]

    print(f"Batch spawned {len(actors)} NPC vehicles (off-route)")
    return actors


def spawn_pedestrians(world, count=15):
    """
    Spawn pedestrians at random navigation points.
    """
    bp_lib        = world.get_blueprint_library()
    walker_bps    = bp_lib.filter('walker.pedestrian.*')
    controller_bp = bp_lib.find('controller.ai.walker')

    ped_actors  = []
    ctrl_actors = []

    # spawn pedestrian bodies
    for _ in range(count):
        loc = world.get_random_location_from_navigation()
        if not loc:
            continue
        bp = random.choice(walker_bps)
        if bp.has_attribute('is_invincible'):
            bp.set_attribute('is_invincible', 'false')
        actor = world.try_spawn_actor(bp, carla.Transform(loc))
        if actor:
            ped_actors.append(actor)

    world.tick()

    # attach AI controllers
    for ped in ped_actors:
        ctrl = world.try_spawn_actor(
            controller_bp,
            carla.Transform(),
            attach_to=ped
        )
        if ctrl:
            ctrl_actors.append(ctrl)

    world.tick()

    # start walking
    for ctrl in ctrl_actors:
        ctrl.start()
        dest = world.get_random_location_from_navigation()
        if dest:
            ctrl.go_to_location(dest)
        ctrl.set_max_speed(1.4)

    all_actors = ped_actors + ctrl_actors
    print(f"Spawned {len(ped_actors)} pedestrians")
    return all_actors

def cleanup(world, original_settings, sensors, actors, vehicle):
    """
    Full cleanup — always runs via try/finally.
    Order: restore settings → stop sensors →
           close files → destroy sensors →
           stop controllers → destroy actors → destroy ego
    """
    print("Cleaning up...")
    restore_async_mode(world, original_settings)

    for s in sensors:
        try:
            if s and s.is_alive:
                s.stop()
        except Exception:
            pass

    for s in sensors:
        try:
            if hasattr(s, '_csv_file'):
                s._csv_file.close()
        except Exception:
            pass

    for s in sensors:
        try:
            if s and s.is_alive:
                s.destroy()
        except Exception:
            pass

    for a in actors:
        try:
            if a and a.is_alive and 'controller' in a.type_id:
                a.stop()
        except Exception:
            pass

    for a in actors:
        try:
            if a and a.is_alive:
                a.destroy()
        except Exception:
            pass

    try:
        if vehicle and vehicle.is_alive:
            vehicle.destroy()
    except Exception:
        pass

    print("Cleanup complete.")