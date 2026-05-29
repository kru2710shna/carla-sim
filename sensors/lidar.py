import carla
import os
import numpy as np

def attach_lidar(world, vehicle, save_path="data/lidar"):
    os.makedirs(save_path, exist_ok=True)

    bp_lib   = world.get_blueprint_library()
    lidar_bp = bp_lib.find('sensor.lidar.ray_cast')
    lidar_bp.set_attribute('channels',          '32')
    lidar_bp.set_attribute('range',             '50')
    lidar_bp.set_attribute('points_per_second', '100000')
    lidar_bp.set_attribute('rotation_frequency','10')
    lidar_bp.set_attribute('upper_fov',         '10')
    lidar_bp.set_attribute('lower_fov',         '-30')

    lidar_transform = carla.Transform(
        carla.Location(x=0.0, y=0.0, z=2.8)
    )

    lidar = world.spawn_actor(lidar_bp, lidar_transform, attach_to=vehicle)
    print("LiDAR sensor attached")

    def save_lidar(point_cloud):
        points = np.frombuffer(point_cloud.raw_data, dtype=np.float32)
        points = points.reshape((-1, 4))
        # industry standard: zero-padded frame number as filename
        filepath = os.path.join(save_path, f"{point_cloud.frame:010d}.npy")
        np.save(filepath, points)

    lidar.listen(save_lidar)
    return lidar