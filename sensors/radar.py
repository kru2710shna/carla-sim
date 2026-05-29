import carla
import os
import csv

def attach_radar(world, vehicle, save_path="data/radar"):
    os.makedirs(save_path, exist_ok=True)

    bp_lib   = world.get_blueprint_library()
    radar_bp = bp_lib.find('sensor.other.radar')
    radar_bp.set_attribute('horizontal_fov',    '30')
    radar_bp.set_attribute('vertical_fov',      '10')
    radar_bp.set_attribute('range',             '100')
    radar_bp.set_attribute('points_per_second', '1500')

    radar_transform = carla.Transform(
        carla.Location(x=2.0, y=0.0, z=1.0),
        carla.Rotation(pitch=5, yaw=0, roll=0)
    )

    radar = world.spawn_actor(radar_bp, radar_transform, attach_to=vehicle)
    print("Radar sensor attached")

    def on_radar_data(data):
        if not data:
            return
        # industry standard: one CSV per frame
        filepath = os.path.join(save_path, f"{data.frame:010d}.csv")
        with open(filepath, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["altitude", "azimuth", "depth", "velocity"])
            for det in data:
                writer.writerow([
                    det.altitude,
                    det.azimuth,
                    det.depth,
                    det.velocity
                ])

    radar.listen(on_radar_data)
    return radar