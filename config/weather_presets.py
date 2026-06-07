import carla 

PRESETS = {
    "baseline": {
        "weather": carla.WeatherParameters(
            cloudiness=10.0,
            precipitation=0.0,
            precipitation_deposits=0.0,
            wind_intensity=5.0,
            sun_azimuth_angle=45.0,
            sun_altitude_angle=70,
            fog_density=0.0,
            fog_distance=0.0,
            wetness=0.0
        ),
        "traffic": 20,
        "pedestrians": 15,
        "duration": 160,
        "description": "Clear Day, Light Traffic, Full Visibility"
    },

    "rain": {
        "weather": carla.WeatherParameters(
            cloudiness=80.0,
            precipitation=80.0,
            precipitation_deposits=80.0,
            wind_intensity=40.0,
            sun_azimuth_angle=45.0,
            sun_altitude_angle=30,
            fog_density=10.0,
            fog_distance=20.0,
            wetness=80.0
        ),
        "traffic": 8,
        "pedestrians": 5,
        "duration": 120,
        "description": "Heavy Rain, Wet Roads, Reduced Visibility"
    },

    "fog": {
        "weather": carla.WeatherParameters(
            cloudiness=60.0,
            precipitation=0.0,
            precipitation_deposits=0.0,
            wind_intensity=5.0,
            sun_azimuth_angle=45.0,
            sun_altitude_angle=70,
            fog_density=10.0,
            fog_distance=20.0,
            wetness=60.0
        ),
        "traffic": 20,
        "pedestrians": 10,
        "duration": 120,
        "description": "Dense Fog, No Rain, ~10m Visibility"
    },

    "night": {
        "weather": carla.WeatherParameters(
            cloudiness=20.0,
            precipitation=0.0,
            precipitation_deposits=0.0,
            wind_intensity=0.0,
            sun_azimuth_angle=45.0,
            sun_altitude_angle=-90,
            fog_density=0.0,
            fog_distance=0.0,
            wetness=0.0
        ),
        "traffic": 15,
        "pedestrians": 10,
        "duration": 120,
        "description": "Night Time, No Moon, Street Lights Only"
    },

    "strom": {
        "weather": carla.WeatherParameters(
            cloudiness=100.0,
            precipitation=100.0,
            precipitation_deposits=90.0,
            wind_intensity=100.0,
            sun_azimuth_angle=45.0,
            sun_altitude_angle=-10,
            fog_density=30.0,
            fog_distance=10.0,
            wetness=100.0
        ),
        "traffic": 10,
        "pedestrians": 5,
        "duration": 120,
        "description": "Severe Storm, Maximum Rain and Wind, Near Darkness"
    },

    "heavy_traffic": {
        "weather": carla.WeatherParameters(
            cloudiness=10.0,
            precipitation=0.0,
            precipitation_deposits=0.0,
            wind_intensity=5.0,
            sun_azimuth_angle=45.0,
            sun_altitude_angle=70,
            fog_density=0.0,
            fog_distance=0.0,
            wetness=0.0
        ),
        "traffic": 50,
        "pedestrians": 30,
        "duration": 120,
        "description": "Clear Day, Rush Hour Traffic Density"
    },
}