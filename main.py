import multiprocessing as mp
import time
import cv2

from setup_environment import setup, start_traffic_light_sequence
from pid_controller import controlLoop as pid_main
import pid_controller
from perception import main as perception_main
from controller import main as controller_main
from hal.products.mats import SDCSRoadMap

# === Pose Setup ===
nodeSequence = [10, 4, 20, 10, 2, 4, 20, 10]
roadmap = SDCSRoadMap(leftHandTraffic=False)
waypointSequence = roadmap.generate_path(nodeSequence)
initialPose = roadmap.get_node_pose(nodeSequence[0]).squeeze()

def display_images(image_queue: mp.Queue):
    try:
        while True:
            if not image_queue.empty():
                img_display = image_queue.get()
                cv2.imshow("YOLOv8 Detection", img_display)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    print("Viewer closed by user.")
                    break
            else:
                time.sleep(0.01)
    except (KeyboardInterrupt, InterruptedError):
        print("Display interrupted by user.")
    finally:
        cv2.destroyAllWindows()

if __name__ == "__main__":
    mp.set_start_method("spawn", force=True)

    perception_queue = mp.Queue()
    image_queue = mp.Queue()
    command_queue = mp.Queue()
    v2x_queue = mp.Queue()  # 🔥 NEW

    manager = mp.Manager()
    shared_pose = manager.dict({"x": 0.0, "y": 0.0})

    pid_controller.perception_queue = perception_queue
    pid_controller.command_queue = command_queue

    print("Initializing simulation environment...")
    qcar, traffic_lights, light_metadata = setup(
        initialPosition=[initialPose[0], initialPose[1], 0],
        initialOrientation=[0, 0, initialPose[2]],
    )

    time.sleep(2)

    shutdown_event = mp.Event()

    perception_process = mp.Process(
        target=perception_main,
        args=(perception_queue, image_queue, shutdown_event)
    )

    v2x_process = mp.Process(   # 🔥 NEW
        target=__import__("V2X").main,
        args=(v2x_queue, shared_pose, light_metadata)
    )

    controller_process = mp.Process(
        target=controller_main,
        args=(perception_queue, command_queue, v2x_queue)
    )

    pid_process = mp.Process(
        target=pid_main,
        args=(command_queue, shared_pose)
    )

    print("Starting perception, V2X, controller, and control processes...")
    perception_process.start()
    v2x_process.start()
    controller_process.start()
    time.sleep(1)
    pid_process.start()

    start_traffic_light_sequence(traffic_lights)

    display_images(image_queue)

    print("Shutting down all subprocesses...")
    shutdown_event.set()
    perception_queue.put("TERMINATE")

    time.sleep(1)
    for proc in [perception_process, v2x_process, controller_process, pid_process]:
        proc.terminate()
        proc.join()

    print("All subprocesses terminated.")
