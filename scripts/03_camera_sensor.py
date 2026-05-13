import carla
import random
import time
from pathlib import Path

def main():
    client = carla.Client("localhost", 2000)
    client.set_timeout(30.0)

    world = client.get_world()
    blueprint_library = world.get_blueprint_library()

    output_dir = Path("data/rgb")
    output_dir.mkdir(parents=True, exist_ok=True)

    vehicle = None
    camera = None

    try:
        # ---- Spawn ego vehicle ----
        vehicle_bp = blueprint_library.filter("vehicle.tesla.model3")[0]
        spawn_points = world.get_map().get_spawn_points()

        vehicle = None
        for spawn_point in random.sample(spawn_points, len(spawn_points)):
            vehicle = world.try_spawn_actor(vehicle_bp, spawn_point)
            if vehicle is not None:
                break

        if vehicle is None:
            raise RuntimeError("Could not spawn vehicle. Try again.")

        print("Spawned ego vehicle")
        print("Vehicle ID:", vehicle.id)
        print("Vehicle transform:", vehicle.get_transform())

        # ---- Camera blueprint ----
        camera_bp = blueprint_library.find("sensor.camera.rgb")
        camera_bp.set_attribute("image_size_x", "800")
        camera_bp.set_attribute("image_size_y", "600")
        camera_bp.set_attribute("fov", "90")

        # Camera mounted slightly above and behind the hood
        camera_transform = carla.Transform(
            carla.Location(x=1.5, z=2.4),
            carla.Rotation(pitch=-10)
        )

        camera = world.spawn_actor(
            camera_bp,
            camera_transform,
            attach_to=vehicle
        )

        print("Attached RGB camera")
        print("Camera ID:", camera.id)

        # ---- Save camera frames ----
        def save_image(image):
            image.save_to_disk(str(output_dir / f"frame_{image.frame:06d}.png"))
            print(f"Saved frame {image.frame}")

        camera.listen(save_image)

        print("Collecting RGB images for 10 seconds...")
        time.sleep(10)

    finally:
        if camera is not None:
            camera.stop()
            camera.destroy()
            print("Destroyed camera")

        if vehicle is not None:
            vehicle.destroy()
            print("Destroyed vehicle")

if __name__ == "__main__":
    main()
