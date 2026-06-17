import carla

PRESETS = {
    "baseline": {
        "weather": carla.WeatherParameters.ClearNoon,
        "traffic": 25,
        "pedestrians": 20,
        "duration": 70,
        "description": "Clear Day, Light Traffic, Full Visibility"
    },
    "rain": {
        "weather": carla.WeatherParameters.HardRainNoon,
        "traffic": 8,
        "pedestrians": 5,
        "duration": 120,
        "description": "Heavy Rain, Wet Roads, Reduced Visibility"
    },
    "fog": {
        "weather": carla.WeatherParameters.CloudyNoon,
        "traffic": 20,
        "pedestrians": 10,
        "duration": 120,
        "description": "Cloudy, Reduced Visibility"
    },
    "night": {
        "weather": carla.WeatherParameters.ClearNight,
        "traffic": 15,
        "pedestrians": 10,
        "duration": 120,
        "description": "Night Time, Street Lights Only"
    },
    "strom": {
        "weather": carla.WeatherParameters.HardRainNight,
        "traffic": 10,
        "pedestrians": 5,
        "duration": 120,
        "description": "Storm, Maximum Rain, Near Darkness"
    },
    "heavy_traffic": {
        "weather": carla.WeatherParameters.ClearNoon,
        "traffic": 50,
        "pedestrians": 30,
        "duration": 120,
        "description": "Clear Day, Rush Hour Traffic Density"
    },
}