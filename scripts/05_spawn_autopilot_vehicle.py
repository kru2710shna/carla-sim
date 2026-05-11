import carla
import random
import time

def main():
    client = carla.Client("localhost", 2000)
    client.set_timeout(30.0)

    world = client.get_world()
    blueprint_library = world.get_blueprint_library()

    traffic_manager = client.get_trafficmanager(8000)
    traffic_manager.set_synchronous_mode(False)

    vehicle_bp = blueprint_library.filter("vehicle.tesla.model3")[0]
    spawn_points = world.get_map().get_spawn_points()

    vehicle = None

    for spawn_point in random.sample(spawn_points, len(spawn_points)):
        vehicle = world.try_spawn_actor(vehicle_bp, spawn_point)
        if vehicle is not None:
            break

    if vehicle is None:
        raise RuntimeError("Could not spawn vehicle")

    vehicle.set_autopilot(True, traffic_manager.get_port())

    spectator = world.get_spectator()

    print("Spawned ego vehicle with autopilot")
    print("Vehicle ID:", vehicle.id)
    print("Watch the CARLA window. Press Ctrl+C here to stop.")

    try:
        while True:
            transform = vehicle.get_transform()

            # Camera behind and above vehicle

            forward_vector = transform.get_forward_vector()
            spectator_location = transform.location - 8 * forward_vector + carla.Location(z=4)
            spectator_rotation = carla.Rotation(
                pitch=-20,
                yaw=transform.rotation.yaw,
                roll=0
            )

            spectator.set_transform(carla.Transform(spectator_location, spectator_rotation))
            time.sleep(0.05)

    except KeyboardInterrupt:
        print("Stopping...")

    finally:
        vehicle.destroy()
        print("Destroyed vehicle")

if __name__ == "__main__":
    main()
