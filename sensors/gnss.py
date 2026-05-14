import carla
import os
import csv

def attach_gnss(world,vehicle,save_path='data/gnss'):

    # 1 - create folder if not 
    os.makedirs(save_path,exist_ok=True)

    # 2- get blueprinm lib for sensors
    blueprint_lib = world.get_blueprint_library()
    gnss_bp = blueprint_lib.find('sensor.other.gnss')

    # 3- record time interval
    gnss_bp.set_attribute("sensor_tick",'0.1')

    # 4- mount on top ot camera
    gnss_transform = carla.Transform(carla.Location(x=0,z=2.0))

    # 5- attach to vehicle 
    gnss = world.spawn_actor(gnss_bp,gnss_transform,attach_to=vehicle)

    #save logs to csv 
    csv_file = open(os.path.join(save_path, "gnss_logs.csv"),"w",newline="")
    csv_writer= csv.writer(csv_file)
    csv_writer.writerow(["frame", "timestamp", "latitude", "longitude", "altitude"])

    def save_gnss(data):
        csv_writer.writerow([
            data.frame,
            data.timestamp,
            data.latitude,
            data.longitude,
            data.altitude
        ])
    gnss.listen(save_gnss)

    gnss._csv_file = csv_file
    return gnss


def stop_gnss(gnss):
    gnss.stop()
    gnss._csv_file.close()
    gnss.destroy()
    print("GNSS stopped and data saved")
    