import time
import signal
import numpy as np
from multiprocessing import Queue

from pal.products.qcar import QCar, QCarGPS, IS_PHYSICAL_QCAR
from hal.content.qcar_functions import QCarEKF
from hal.products.mats import SDCSRoadMap
from Movement_controller import SpeedController, SteeringController

# ================= Experiment Configuration =================
tf = 6000
startDelay = 1
controllerUpdateRate = 100

v_ref = 0.5
K_p = 0.05
K_i = 0.8

enableSteeringControl = True
K_stanley = 0.5
nodeSequence = [10, 4, 20, 10, 2, 4, 20, 10]

# Global references to be set externally
perception_queue: Queue = None
command_queue: Queue = None

# Global pose store for controller access
ekf_pose = {"x": 0.0, "y": 0.0}

# ================= Setup =================
if enableSteeringControl:
    roadmap = SDCSRoadMap(leftHandTraffic=False)
    waypointSequence = roadmap.generate_path(nodeSequence)
    initialPose = roadmap.get_node_pose(nodeSequence[0]).squeeze()
else:
    initialPose = [0, 0, 0]

if not IS_PHYSICAL_QCAR:
    calibrate = False
else:
    calibrate = "y" in input("Do you want to recalibrate? (y/n): ")

calibrationPose = [0, 2, -np.pi / 2]

# ============== Signal Handling for Safe Exit ==============
KILL_THREAD = False

def sig_handler(*args):
    global KILL_THREAD
    KILL_THREAD = True

signal.signal(signal.SIGINT, sig_handler)

# ============== Control Loop ==============
def controlLoop(cmd_queue=None, shared_pose=None):
    global KILL_THREAD, perception_queue, command_queue, v_ref

    if cmd_queue is not None:
        command_queue = cmd_queue

    speedController = SpeedController(kp=K_p, ki=K_i)

    if enableSteeringControl:
        steeringController = SteeringController(waypoints=waypointSequence, k=K_stanley)

    print(f"IS_PHYSICAL_QCAR: {IS_PHYSICAL_QCAR}")
    qcar = QCar(readMode=0, frequency=controllerUpdateRate)

    if enableSteeringControl:
        ekf = QCarEKF(x_0=initialPose)
        gps = QCarGPS(initialPose=calibrationPose, calibrate=calibrate)
    else:
        gps = memoryview(b"")

    with qcar, gps:
        t0 = time.time()
        t = 0

        while t < tf + startDelay and not KILL_THREAD:
            tp = t
            t = time.time() - t0
            dt = t - tp

            qcar.read()

            if command_queue is not None and not command_queue.empty():
                cmd = command_queue.get()
                print(f"[PID] Received command: {cmd}")
                v_ref = 0 if cmd == "STOP" else 0.5

            if enableSteeringControl:
                if gps.readGPS():
                    y_gps = np.array([gps.position[0], gps.position[1], gps.orientation[2]])
                    ekf.update([qcar.motorTach, 0], dt, y_gps, qcar.gyroscope[2])
                else:
                    ekf.update([qcar.motorTach, 0], dt, None, qcar.gyroscope[2])

                x = ekf.x_hat[0, 0]
                y = ekf.x_hat[1, 0]
                if shared_pose is not None and not KILL_THREAD:
                    shared_pose["x"] = x
                    shared_pose["y"] = y

                th = ekf.x_hat[2, 0]
                p = np.array([x, y]) + np.array([np.cos(th), np.sin(th)]) * 0.2

            v = qcar.motorTach
            u = speedController.update(v, v_ref, dt) if t >= startDelay else 0
            delta = steeringController.update(p, th, v) if enableSteeringControl and t >= startDelay else 0
            qcar.write(u, delta)

        qcar.read_write_std(throttle=0, steering=0)

# ============== External Access to Car Position ==============
def get_qcar_pose():
    return [ekf_pose["x"], ekf_pose["y"]]

# ============== Main Entry Point ==============
if __name__ == "__main__":
    controlLoop()  # Standalone usage
    if not IS_PHYSICAL_QCAR:
        import setup_environment
        setup_environment.terminate()
    input("Experiment complete. Press any key to exit...")
