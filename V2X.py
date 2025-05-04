# === V2X.py ===
import multiprocessing
import time
from qvl.qlabs import QuanserInteractiveLabs
from qvl.traffic_light import QLabsTrafficLight

# Constants
SCALING_FACTOR = 0.0912

def euclidean_distance(p1, p2):
    return ((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)**0.5

def get_nearest_light_status(qcar_position, traffic_lights):
    min_dist = float("inf")
    nearest_light = None

    for light in traffic_lights:
        dist = euclidean_distance(qcar_position, light["location"])
        if dist < min_dist:
            min_dist = dist
            nearest_light = light

    if nearest_light is not None:
        try:
            status, color_code = nearest_light["traffic_light"].get_color()
            if status:
                if color_code == QLabsTrafficLight.COLOR_RED:
                    return "RED"
                elif color_code == QLabsTrafficLight.COLOR_GREEN:
                    return "GREEN"
                elif color_code == QLabsTrafficLight.COLOR_YELLOW:
                    return "YELLOW"
        except Exception as e:
            print(f"[V2X] Error reading nearest light: {e}")

    return "UNKNOWN"

def main(v2x_queue: multiprocessing.Queue, shared_pose, light_metadata):
    qlabs = QuanserInteractiveLabs()
    try:
        qlabs.open("localhost")
        print("[V2X] Connected to QLabs for traffic light access")
    except Exception as e:
        print(f"[V2X] Failed to connect to QLabs: {e}")
        return

    traffic_lights = []
    for meta in light_metadata:
        tl = QLabsTrafficLight(qlabs)
        tl.actorNumber = meta["id"]

        scaled_location = [coord * SCALING_FACTOR for coord in meta["location"]]
        traffic_lights.append({
            "id": meta["id"],
            "location": scaled_location,
            "traffic_light": tl
        })

    print("[V2X] Traffic lights initialized.")

    try:
        while True:
            qcar_pos = [shared_pose.get("x", 0.0), shared_pose.get("y", 0.0)]

            if not (abs(qcar_pos[0]) < 0.001 and abs(qcar_pos[1]) < 0.001):
                status = get_nearest_light_status(qcar_pos, traffic_lights)
                if not v2x_queue.full():
                    v2x_queue.put(status)
            else:
                if not v2x_queue.full():
                    v2x_queue.put("UNKNOWN")

            time.sleep(1)

    except KeyboardInterrupt:
        print("[V2X] Shutdown requested.")
