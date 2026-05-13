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
    spawn_point = random.choice(world.get_map().get_spawn_points())
    vehicle = world.spawn_actor(vehicle_bp, spawn_point)
    print(f"Spawned: {vehicle.type_id} at {spawn_point.location}")
    return vehicle

def focus_spectator_on(world, actor):
    spectator = world.get_spectator()
    transform = actor.get_transform()
    transform.location.z += 30
    transform.rotation.pitch = -90
    spectator.set_transform(transform)
    print("Spectator focused on vehicle")

