import carla

def main():
    client = carla.Client("localhost", 2000)
    client.set_timeout(30.0)

    world = client.get_world()

    print("Connected to CARLA")
    print("Map:", world.get_map().name)
    print("Actors:", len(world.get_actors()))

if __name__ == "__main__":
    main()
