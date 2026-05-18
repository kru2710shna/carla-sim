import carla
import random

def is_carla_there(host="localhost", port=2000, timeout=5.0):
    try:
        client = carla.Client(host, port)
        client.set_timeout(timeout)
        client.get_server_version()
        return True
    except Exception:
        return False

def get_world(host="localhost", port=2000, timeout=5.0):
    try:
        client = carla.Client(host, port)
        client.set_timeout(timeout)
        return client.get_world()
    except Exception as e:
        print(f"Failed to get world: {e}")
        return None

def spawn_vehicle(world):
    blueprint_library = world.get_blueprint_library()
    vehicle_bp = blueprint_library.filter('vehicle.tesla.model3')[0]
    vehicle_bp.set_attribute('role_name', 'ego')

    spawn_points = world.get_map().get_spawn_points()
    random.shuffle(spawn_points)

    # try each spawn point until one works
    for spawn_point in spawn_points:
        vehicle = world.try_spawn_actor(vehicle_bp, spawn_point)
        if vehicle:
            print(f"Spawned: {vehicle.type_id} at {spawn_point.location}")
            return vehicle

    print("Failed to spawn ego vehicle — all spawn points occupied")
    return None


def configure_npc_traffic(client, actors, ego_vehicle=None):
    tm = client.get_trafficmanager()
    tm.set_global_distance_to_leading_vehicle(3.0)

    for actor in actors:
        if actor.type_id.startswith('vehicle.'):
            try:
                tm.vehicle_percentage_speed_difference(actor, 30.0)
                tm.auto_lane_change(actor, False)
                tm.ignore_lights_percentage(actor, 0)
            except Exception:
                pass

    # configure ego separately
    if ego_vehicle:
        tm.vehicle_percentage_speed_difference(ego_vehicle, 40.0)
        tm.auto_lane_change(ego_vehicle, False)
        tm.keep_right_rule_percentage(ego_vehicle, 100)
        tm.distance_to_leading_vehicle(ego_vehicle, 5.0)

    print("NPC traffic configured for safe driving")

    
def focus_spectator_on(world, actor):
    spectator = world.get_spectator()
    transform = actor.get_transform()
    transform.location.z += 30
    transform.rotation.pitch = -90
    spectator.set_transform(transform)
    print("Spectator focused on vehicle")


def spawn_traffic(world, num_vehicles=30, num_pedestrians=20):
    actors = []
    blueprint_lib = world.get_blueprint_library()

    # add vehciles 
    vehicle_bp = blueprint_lib.filter("vehicle.*")
    spawn_point = world.get_map().get_spawn_points()
    random.shuffle(spawn_point)

    for i , spawn_p in enumerate(spawn_point[:num_vehicles]):
        bp = random.choice(vehicle_bp)

        # skip bike and cycles, as they are hard to track
        if 'bike' in bp.id or 'bicycle' in bp.id or 'motorcycle' in bp.id:
            continue
        
        actor = world.try_spawn_actor(bp, spawn_p)
        if actor:
            actor.set_autopilot(True)   # every NPC drives itself
            actors.append(actor)
    print(f"Spawned {len(actors)} NPC vehicles")


    # add pedestrians 
    pedestrians_bp = blueprint_lib.filter("walker.pedestrian.*")
    ped_controller_bp = blueprint_lib.find('controller.ai.walker')

    SPWAN_POINTS = []
    for _ in range(num_pedestrians):
        loc = world.get_random_location_from_navigation()
        if loc:
            SPWAN_POINTS.append(carla.Transform(loc))
    
    for sp in SPWAN_POINTS:
        ped_bp = random.choice(pedestrians_bp)
        pedestrian = world.try_spawn_actor(ped_bp, sp)
        if pedestrian:
            actors.append(pedestrian)

            # attach AI controller so pedestrian walks around
            controller = world.spawn_actor(ped_controller_bp, carla.Transform(), attach_to=pedestrian)
            controller.start()
            controller.go_to_location(world.get_random_location_from_navigation())
            controller.set_max_speed(1.4)   
            actors.append(controller)

    print(f"Spawned pedestrians")
    return actors
