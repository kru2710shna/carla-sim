import carla
import random


def is_carla_there(CLIENT):
    try:
        CLIENT = carla.Client('localhost', 2000)
        CLIENT.set_timeout(5.0)
        CLIENT.get_server_version()
        return True          
    except Exception:
        return False         

def get_world(CLIENT):
    try:
        world = CLIENT.get_world()
        return world
    except Exception as e:
        print(f"Failed to get world: {e}")
    return None

def spawn_vehicle(world):
    blueprint_library = world.get_blueprint_library()
    vehicle_bp = blueprint_library.filter('vehicle.tesla.model3')[0]

    spawn_points = world.get_map().get_spawn_points()
    spawn_point = random.choice(spawn_points)

    vehicle = world.spawn_actor(vehicle_bp,spawn_point)
    print(f"Spawned: {vehicle.type_id} at {spawn_point.location}")
    return vehicle

def focus_spectator_on(world, actor):
    spectator = world.get_spectator()
    transform = actor.get_transform()
    
    # position camera behind and above the vehicle
    transform.location.z += 30
    transform.rotation.pitch = -90
    
    spectator.set_transform(transform)
    print("Spectator focused on vehicle")

if __name__ == "__main__":

    CLIENT = carla.Client('localhost', 2000)
    ###################################### ACTIVE CARLA ###################################
    status = is_carla_there(CLIENT)
    if status:
        print("Connected to Carla")
        
        world = get_world(CLIENT)
        if world:
            print("World:", world.get_map().name) 
            vehicle = spawn_vehicle(world)
            focus_spectator_on(world, vehicle)
            
    else:
        print("Carla is not Connected")





    
    #
