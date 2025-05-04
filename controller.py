# === controller.py ===
import multiprocessing
import time

# Threshold
RED_LIGHT_MIN_WIDTH = 38

# Helper functions
def any_detected_objects(results):
    return isinstance(results, list) and len(results) > 0

def get_cls(results):
    return results[0]["class"] if results and "class" in results[0] else None

def get_width(results):
    return results[0]["width"] if results and "width" in results[0] else 0

def main(perception_queue: multiprocessing.Queue, command_queue: multiprocessing.Queue,
         v2x_queue: multiprocessing.Queue):
    is_stopped = False
    cached_v2x_status = "UNKNOWN"

    try:
        while True:
            # Read V2X latest status if available
            if not v2x_queue.empty():
                cached_v2x_status = v2x_queue.get()

            if not perception_queue.empty():
                results = perception_queue.get()

                if any_detected_objects(results):
                    cls = get_cls(results)
                    width = get_width(results)

                    if cls == "Red" and cached_v2x_status == "RED" and width > RED_LIGHT_MIN_WIDTH and not is_stopped:
                        command_queue.put("STOP")
                        print("[Controller] STOPPING: Red light detected, V2X confirmed RED")
                        is_stopped = True

                    elif cls == "Green" and cached_v2x_status == "GREEN" and is_stopped:
                        command_queue.put("GO")
                        print("[Controller] RESUMING: Green light detected, V2X confirmed GREEN")
                        is_stopped = False

            time.sleep(0.05)

    except KeyboardInterrupt:
        print("[Controller] Shutdown requested.")
