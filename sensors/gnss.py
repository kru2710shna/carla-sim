import carla
import os
import csv

def attach_gnss(world, vehicle, save_path="data/gnss"):
    os.makedirs(save_path, exist_ok=True)

    blueprint_library = world.get_blueprint_library()
    gnss_bp = blueprint_library.find('sensor.other.gnss')
    gnss_bp.set_attribute('sensor_tick', '0.0')

    gnss_transform = carla.Transform(carla.Location(x=0, z=2.0))
    gnss = world.spawn_actor(gnss_bp, gnss_transform, attach_to=vehicle)
    print("GNSS sensor attached")

    csv_file = open(os.path.join(save_path, "gnss_log.csv"), "w", newline="")
    csv_writer = csv.writer(csv_file)
    csv_writer.writerow(["frame", "timestamp", "latitude", "longitude", "altitude"])

    def save_gnss(data):
        csv_writer.writerow([
            data.frame,
            data.timestamp,
            data.latitude,
            data.longitude,
            data.altitude
        ])
        csv_file.flush()   

    gnss.listen(save_gnss)
    gnss._csv_file = csv_file
    return gnss


def stop_gnss(gnss):
    try:
        gnss.stop()
    except Exception:
        pass
    try:
        gnss._csv_file.close()
    except Exception:
        pass
    try:
        gnss.destroy()
    except Exception:
        pass
    print("GNSS stopped and data saved")
    