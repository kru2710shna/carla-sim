import carla
import random
import time

def main():
    client = carla.Client("localhost", 2000)
    client.set_timeout(30.0)

    world = client.get_world()
    blueprint_library = world.get_blueprint_library()

    # Choose a vehicle blueprint
    vehicle_bp = blueprint_library.filter("vehicle.tesla.model3")[0]

    # Choose a random spawn point
    spawn_points = world.get_map().get_spawn_points()
    spawn_point = random.choice(spawn_points)

    vehicle = None

    try:
        vehicle = world.spawn_actor(vehicle_bp, spawn_point)

        print("Spawned ego vehicle successfully")
        print("Vehicle ID:", vehicle.id)
        print("Vehicle type:", vehicle.type_id)
        print("Location:", vehicle.get_location())

        # Let it exist for a few seconds
        time.sleep(5)

    finally:
        if vehicle is not None:
            vehicle.destroy()
            print("Destroyed ego vehicle cleanly")

if __name__ == "__main__":
    main()
