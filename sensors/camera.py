import carla
import os

def rgb_camera(world, vehicle, save_path="data/images"):
    """
    Attaches an RGB camera to a vehicle and saves images to disk.

    How it works:
    - We get the camera blueprint from CARLA
    - We set its resolution and field of view
    - We define WHERE on the car to mount it (transform)
    - We spawn it attached to the vehicle
    - Every time a new frame arrives, the callback saves it as a .png
    """

    # 1. make sure the save folder exists
    os.makedirs(save_path, exist_ok=True)

    # 2. get the camera blueprint
    blueprint_library = world.get_blueprint_library()
    camera_bp = blueprint_library.find('sensor.camera.rgb')

    # 3. set camera settings
    camera_bp.set_attribute('image_size_x', '1280')  # width in pixels
    camera_bp.set_attribute('image_size_y', '720')   # height in pixels
    camera_bp.set_attribute('fov', '90')             # field of view in degrees

    # 4. where to mount the camera on the car
    #    x=1.5 means 1.5m in front of car center
    #    z=2.4 means 2.4m above car center
    camera_transform = carla.Transform(
        carla.Location(x=1.5, z=2.4)
    )

    # 5. spawn the camera attached to the vehicle
    camera = world.spawn_actor(camera_bp, camera_transform, attach_to=vehicle)
    print("RGB Camera attached to vehicle")

    # 6. callback — runs every time a new frame is captured
    def save_image(image):
        filepath = os.path.join(save_path, f"frame_{image.frame:06d}.png")
        image.save_to_disk(filepath)

    # 7. tell CARLA to call save_image on every new frame
    camera.listen(save_image)

    return camera