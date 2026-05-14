import time
from utils.helper import is_carla_there, get_world, spawn_vehicle, focus_spectator_on
from sensors.camera import attach_rgb_camera
from sensors.gnss import attach_gnss,stop_gnss

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

    # step 6 - let it run for 10 seconds and collect frames
    print("Collecting data for 10 seconds...")
    time.sleep(30)

    # step 7 - clean up, always destroy sensors and vehicles after
    print("Cleaning up...")
    camera.stop()
    camera.destroy()
    stop_gnss(gnss)
    vehicle.destroy()
    print("Done. Check data/images/ and data/gnss for saved frames.")

if __name__ == "__main__":
    main()