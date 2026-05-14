import time
from utils.helper import is_carla_there, get_world, spawn_vehicle, focus_spectator_on
from sensors.camera import attach_rgb_camera
from sensors.gnss import attach_gnss,stop_gnss
from sensors.lidar import attach_lidar

def main():
    # step 1 - check CARLA is running
    if not is_carla_there():
        print("CARLA is not running. Start it first.")
        return

    # step 2 - connect and get the world
    world = get_world()
    if not world:
        return

    print("World:", world.get_map().name)

    # step 3 - spawn our ego vehicle
    vehicle = spawn_vehicle(world)

    # step 3.1 - autopilot to collect data more easily 
    vehicle.set_autopilot(True)
    print("Vehicle is on Autopilot Mode")

    # step 4 - move spectator camera above vehicle
    focus_spectator_on(world, vehicle)

    # step 5 - attach RGB camera , gnss to vehicle
    camera = attach_rgb_camera(world, vehicle)
    gnss = attach_gnss(world,vehicle)
    lidar  = attach_lidar(world, vehicle)

    # step 5.1 add a time so it can adjust sensor 
    time.sleep(3)

    # step 6 - let it run for 10 seconds and collect frames
    print("Collecting data for 60 seconds...")
    time.sleep(60)

    # step 7 - clean up, always destroy sensors and vehicles after
    print("Cleaning up...")
    camera.stop()
    camera.destroy()
    stop_gnss(gnss)
    lidar.stop()
    lidar.destroy()
    vehicle.destroy()
    print("Done. Check data/images/ , data/gnss and data/lidar for saved frames.")

if __name__ == "__main__":
    main()