import multiprocessing
import cv2
import time
import torch
from pathlib import Path
from ultralytics import YOLO
from qvl.qcar import QLabsQCar
from qvl.qlabs import QuanserInteractiveLabs

# === Configuration ===
MODEL_PATH = Path("model/best.pt")
CAMERA = QLabsQCar.CAMERA_RGB


def connect_to_existing_qcar():
    print("Connecting to existing QCar in QLabs...")
    qlabs = QuanserInteractiveLabs()
    try:
        qlabs.open("localhost")
        print("Connected to QLabs.")
    except Exception as e:
        print("QLabs connection failed:", e)
        quit()

    qcar = QLabsQCar(qlabs)
    qcar.spawn_id(
        actorNumber=0,
        location=[0, 0, 0],
        rotation=[0, 0, 0],
        waitForConfirmation=False
    )
    return qcar


def main(perception_queue: multiprocessing.Queue, image_queue: multiprocessing.Queue, shutdown_event: multiprocessing.Event):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[Perception] Using device: {device}")

    car = connect_to_existing_qcar()

    # ✅ Load model
    model = YOLO(MODEL_PATH).to(device)
    print("YOLOv8 Model Loaded")
    print("Starting Detection Loop...")

    while not shutdown_event.is_set():
        if not perception_queue.empty():
            command = perception_queue.get()
            if command == "TERMINATE":
                print("[Perception] Shutdown signal received.")
                shutdown_event.set()
                break


        ok, image = car.get_image(CAMERA)
        if not ok or image is None or image.size == 0:
            print("Failed to capture image from QCar camera.")
            continue

        # Run YOLOv8 detection
        results = model(image, verbose=False)[0]

        if results.boxes.cls.numel() > 0:
            detection_info = []
            for i, cls_id in enumerate(results.boxes.cls.tolist()):
                class_name = model.names[int(cls_id)]
                box = results.boxes.xyxy[i].tolist()
                x1, y1, x2, y2 = box
                width = x2 - x1
                height = y2 - y1

                detection_info.append({
                    "class": class_name,
                    "width": width,
                    "height": height
                })

            print("Detected:", [d["class"] for d in detection_info])
            perception_queue.put(detection_info)
        else:
            perception_queue.put([])

        # Annotate and display
        annotated = results.plot(
            img=image,
            conf=True,
            boxes=True,
            labels=True,
            line_width=2,
            font_size=None,
            pil=False,
        )

        annotated_bgr = cv2.cvtColor(annotated, cv2.COLOR_RGB2BGR)
        image_queue.put(annotated_bgr.copy())  # Send for display

        time.sleep(0.07)


def display_images(image_queue: multiprocessing.Queue):
    try:
        while True:
            img = image_queue.get()
            cv2.imshow("YOLOv8 Real-Time Detection", img)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                print("'q' pressed. Closing viewer.")
                break
    except KeyboardInterrupt:
        print("Display interrupted by user.")
    finally:
        cv2.destroyAllWindows()


if __name__ == "__main__":
    multiprocessing.set_start_method("spawn", force=True)

    perception_queue = multiprocessing.Queue()
    image_queue = multiprocessing.Queue()

    p = multiprocessing.Process(target=main, args=(perception_queue, image_queue))
    p.start()

    display_images(image_queue)
    p.join()
