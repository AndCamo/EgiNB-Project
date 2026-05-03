from ultralytics import YOLO
import cv2
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

def get_occupied_seat(person_mask, seat_mask, min_seat_overlap=0.15, min_person_overlap=0.05):
    # Trova quali seat ID sono coperti dai pixel segmentati della persona
    overlap_values = seat_mask[person_mask > 0]
    unique_ids, counts = np.unique(overlap_values[overlap_values > 0], return_counts=True)

    if len(unique_ids) == 0:
        return None  # persona non su nessun posto

    # Prendi il posto con più overlap
    best_seat = unique_ids[np.argmax(counts)]
    overlap_area = counts.max()

    seat_area = np.count_nonzero(seat_mask == best_seat)
    person_area = np.count_nonzero(person_mask)

    if seat_area == 0 or person_area == 0:
        return None

    overlap_seat_ratio = overlap_area / seat_area
    overlap_person_ratio = overlap_area / person_area

    # Consideriamo occupato se copre abbastanza il posto oppure rappresenta una parte rilevante della persona
    if overlap_seat_ratio > min_seat_overlap or overlap_person_ratio > min_person_overlap:
        return best_seat

    return None


def plot_seat_occupancy(image_bgr, seat_mask, seat_conf_map, alpha=0.45):
    """
    Visualizza i posti occupati in verde e non occupati in rosso.
    Per i posti occupati mostra anche la confidenza massima associata.
    """
    vis = image_bgr.copy()
    overlay = image_bgr.copy()

    all_seat_ids = np.unique(seat_mask)
    all_seat_ids = all_seat_ids[all_seat_ids > 0]

    occupied_ids = set(seat_conf_map.keys())
    green = (0, 180, 0)
    red = (0, 0, 200)

    for seat_id in all_seat_ids:
        seat_id = int(seat_id)
        curr_mask = (seat_mask == seat_id)
        color = green if seat_id in occupied_ids else red

        overlay[curr_mask] = color

        ys, xs = np.where(curr_mask)
        if len(xs) == 0:
            continue

        cx, cy = int(xs.mean()), int(ys.mean())

        if seat_id in occupied_ids:
            conf = seat_conf_map[seat_id]
            label = f"S{seat_id} {conf:.2f}"
        else:
            label = f"S{seat_id}"

        (tw, th), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.42, 1)
        cv2.rectangle(
            vis,
            (cx - tw // 2 - 4, cy - th - 6),
            (cx + tw // 2 + 4, cy + baseline + 2),
            (0, 0, 0),
            -1,
        )
        cv2.putText(
            vis,
            label,
            (cx - tw // 2, cy),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.42,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )

    vis = cv2.addWeighted(overlay, alpha, vis, 1.0 - alpha, 0)
    return vis


# Inizializzazione e inferenza
BASE_DIR = Path(__file__).resolve().parent
model_name = "yolo26l-seg"  
model = YOLO(str(BASE_DIR / "weights" / f"{model_name}.pt"))
results = model.predict(str(BASE_DIR / "data" / "aula-studio-3.png"), conf=0.05, classes=[0])  # filter only person class
result = results[0]



seat_mask = cv2.imread(str(BASE_DIR / "seat_mask.png"), cv2.IMREAD_GRAYSCALE)
if seat_mask is None:
    raise FileNotFoundError(f"Impossibile caricare la maschera: {BASE_DIR / 'seat_mask.png'}")

if result.masks is None:
    raise ValueError("Il modello non ha restituito maschere di segmentazione.")

mask_polygons = result.masks.xy
boxes = result.boxes

occupied_seats = []
seat_conf_map = {}
for i, polygon in enumerate(mask_polygons):
    cls_id = int(boxes.cls[i].item())
    if cls_id != 0:
        continue

    person_mask = np.zeros_like(seat_mask, dtype=np.uint8)
    polygon_int = np.round(polygon).astype(np.int32)
    cv2.fillPoly(person_mask, [polygon_int], 1)

    seat_id = get_occupied_seat(person_mask, seat_mask)
    if seat_id is not None:
        seat_id = int(seat_id)
        occupied_seats.append(seat_id)
        conf = float(boxes.conf[i].item())
        if seat_id not in seat_conf_map:
            seat_conf_map[seat_id] = conf
        else:
            seat_conf_map[seat_id] = max(seat_conf_map[seat_id], conf)
        print(f"Persona {i} (conf={conf:.2f}) occupa il posto ID: {seat_id}")

occupied_seats = sorted(set(occupied_seats))
print(f"Posti occupati: {occupied_seats}")

source_img = cv2.imread(str(BASE_DIR / "data" / "aula-studio-3.png"))
if source_img is None:
    raise FileNotFoundError(f"Impossibile caricare l'immagine: {BASE_DIR / 'data' / 'aula-studio-3.png'}")

occupancy_vis = plot_seat_occupancy(source_img, seat_mask, seat_conf_map, alpha=0.45)

plt.figure(figsize=(16, 9))
plt.imshow(cv2.cvtColor(occupancy_vis, cv2.COLOR_BGR2RGB))
plt.title("Posti occupati (verde) e non occupati (rosso)")
plt.axis("off")
plt.tight_layout()
plt.show()


