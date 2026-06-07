import carla
import os

def attach_rgb_camera(world, vehicle, save_path="data/camera/front"):
    os.makedirs(save_path, exist_ok=True)

    bp_lib    = world.get_blueprint_library()
    camera_bp = bp_lib.find('sensor.camera.rgb')

    # basic settings only
    camera_bp.set_attribute('image_size_x', '1280')
    camera_bp.set_attribute('image_size_y', '720')
    camera_bp.set_attribute('fov',          '90')

    # CARLA default exposure — works best for most conditions
    # camera_bp.set_attribute('exposure_mode',         'auto')
    # camera_bp.set_attribute('gamma',                 '2.2')

    camera_transform = carla.Transform(
        carla.Location(x=1.5, y=0.0, z=2.4),
        carla.Rotation(pitch=0, yaw=0, roll=0)
    )

    camera = world.spawn_actor(camera_bp, camera_transform, attach_to=vehicle)
    print("RGB Camera attached to vehicle")

    def save_image(image):
        filepath = os.path.join(save_path, f"{image.frame:010d}.png")
        image.save_to_disk(filepath)

    camera.listen(save_image)
    return camera


def save_image(image):
    filepath = os.path.join(save_path, f"{image.frame:010d}.png")
    # convert to RGB array and save — fixes color channel issues
    import numpy as np
    array = np.frombuffer(image.raw_data, dtype=np.uint8)
    array = array.reshape((image.height, image.width, 4))  # BGRA
    array = array[:, :, :3]                                 # drop alpha → BGR
    array = array[:, :, ::-1]                               # BGR → RGB
    import cv2
    cv2.imwrite(filepath, array[:, :, ::-1])                # save as BGR for cv2