# Single fixed closed loop route on Town10HD
# Verified visually on map — clean loop, correct lane directions

LOOP_ROUTE = {
    "map": "Town10HD_Opt",
    "description": "Fixed closed loop — north, east, south, west",
    "spawn_indices": [
        89,   # START — west vertical, going north
        99,   # north leg
        108,
        26,
        68,
        24,
        16,   # NW corner
        69,   # east leg
        17,
        88,
        20,   # NE corner
        41,   # south leg
        98,
        152,  # SE corner
        151,
        148,
        147,
        74,
        72,
        153,
        145,
        109,  # SW corner
    ],
    "start_index": 89,
    "loop": True
}