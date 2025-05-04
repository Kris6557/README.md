import os
import time
from threading import Thread
from qvl.qlabs import QuanserInteractiveLabs
from qvl.qcar import QLabsQCar
from qvl.free_camera import QLabsFreeCamera
from qvl.traffic_light import QLabsTrafficLight
from qvl.real_time import QLabsRealTime
import pal.resources.rtmodels as rtmodels

# === Traffic Light Configuration ===
TRAFFIC_LIGHTS_CONFIG = [
    {"id": 1, "location": [23.667, 9.893, 0.005], "rotation": [0, 0, 0]},
    {"id": 2, "location": [-21.122, 9.341, 0.005], "rotation": [0, 0, 180]},
]

# === Traffic Light Sequence (no print) ===
def traffic_light_sequence(traffic_light, red_time=15, green_time=7, yellow_time=1, delay=0):
    time.sleep(delay)
    while True:
        traffic_light.set_color(QLabsTrafficLight.COLOR_RED)
        time.sleep(red_time)
        traffic_light.set_color(QLabsTrafficLight.COLOR_GREEN)
        time.sleep(green_time)
        traffic_light.set_color(QLabsTrafficLight.COLOR_YELLOW)
        time.sleep(yellow_time)

# === Launch Sequencing Threads After Fork ===
def start_traffic_light_sequence(traffic_lights):
    for i, light in enumerate(traffic_lights):
        Thread(
            target=traffic_light_sequence,
            args=(light["traffic_light"], 13, 6, 1, i * 5),
            daemon=True
        ).start()

# === Setup Function ===
def setup(initialPosition=[0, 0, 0.005], initialOrientation=[0, 0, 0]):
    os.system("cls" if os.name == "nt" else "clear")
    qlabs = QuanserInteractiveLabs()
    print("Connecting to QLabs...")
    try:
        qlabs.open("localhost")
        print("Connected to QLabs")
    except:
        print("Unable to connect to QLabs")
        quit()

    qlabs.destroy_all_spawned_actors()
    QLabsRealTime().terminate_all_real_time_models()

    # Spawn QCar
    qcar = QLabsQCar(qlabs)
    qcar.spawn_id(
        actorNumber=0,
        location=[p * 10 for p in initialPosition],
        rotation=initialOrientation,
        waitForConfirmation=True,
    )

    # Attach camera and possess QCar
    camera = QLabsFreeCamera(qlabs)
    camera.spawn()
    qcar.possess()

    # Spawn traffic lights
    traffic_lights = []
    for config in TRAFFIC_LIGHTS_CONFIG:
        light = {
            "id": config["id"],
            "location": config["location"],
            "rotation": config["rotation"],
            "traffic_light": QLabsTrafficLight(qlabs)
        }
        light["traffic_light"].actorNumber = light["id"]
        light["traffic_light"].spawn_id_degrees(
            actorNumber=light["id"],
            location=light["location"],
            rotation=light["rotation"],
            scale=[1, 1, 1],
            configuration=0,
            waitForConfirmation=True,
        )
        traffic_lights.append(light)

    QLabsRealTime().start_real_time_model(rtmodels.QCAR)

    # Extract only safe metadata to share across processes
    light_metadata = [
        {"id": light["id"], "location": light["location"]}
        for light in traffic_lights
    ]
    return qcar, traffic_lights, light_metadata


def terminate():
    QLabsRealTime().terminate_real_time_model(rtmodels.QCAR)

if __name__ == "__main__":
    setup()
