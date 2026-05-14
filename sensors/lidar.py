import carla
import os
import numpy as np

def attach_lidar(world, vehicle, save_path="data/lidar"):
    """
    Attaches a LiDAR sensor to the vehicle.

    What is LiDAR?
    - Stands for Light Detection and Ranging
    - Shoots laser beams in 360 degrees around the car
    - Each beam bounces back and tells us the distance to that object
    - Result is a 3D point cloud — thousands of (x, y, z) points
      representing everything around the car

    Why is it important for your research?
    - Camera gives us a 2D image (looks nice but no depth info)
    - LiDAR gives us 3D spatial data (exact distances to objects)
    - ML segmentation models use both together for better accuracy
    - Radar research builds on top of LiDAR understanding

    What we save:
    - Each frame saved as a .npy file (numpy array)
    - Shape: (N, 4) where N = number of points
    - Each point has: (x, y, z, intensity)
    """

    os.makedirs(save_path, exist_ok=True)

    blueprint_library = world.get_blueprint_library()
    lidar_bp = blueprint_library.find('sensor.lidar.ray_cast')

    # --- LiDAR settings, explained ---

    # number of laser beams firing at once (more = denser point cloud)
    lidar_bp.set_attribute('channels', '32')

    # max distance each beam can reach in metres
    lidar_bp.set_attribute('range', '50')

    # how many points captured per second across all beams
    lidar_bp.set_attribute('points_per_second', '100000')

    # how many full 360 rotations per second
    lidar_bp.set_attribute('rotation_frequency', '10')

    # horizontal field of view in degrees (360 = full surround scan)
    lidar_bp.set_attribute('upper_fov', '10')
    lidar_bp.set_attribute('lower_fov', '-30')

    # mount on roof of car
    # x=0 = center, z=2.8 = just above roof
    lidar_transform = carla.Transform(carla.Location(x=0, z=2.8))

    lidar = world.spawn_actor(lidar_bp, lidar_transform, attach_to=vehicle)
    print("LiDAR sensor attached")

    # callback — runs every rotation (10 times per second)
    def save_lidar(point_cloud):
        # convert raw data to numpy array of (x, y, z, intensity)
        points = np.frombuffer(point_cloud.raw_data, dtype=np.float32)
        points = points.reshape((-1, 4))

        filepath = os.path.join(save_path, f"lidar_{point_cloud.frame:06d}.npy")
        np.save(filepath, points)

    lidar.listen(save_lidar)
    return lidar