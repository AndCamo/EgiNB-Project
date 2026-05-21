from ultralytics import YOLO
from pathlib import Path

BASE_DIR = Path(__file__).parent
# Carica il modello sul tuo PC
model_name = "yolo26l-seg.pt"
model_path = BASE_DIR / "weights" / model_name
model = YOLO(str(model_path))

# Esporta in formato ONNX (creerà yolo26x-seg.onnx)
model.export(format="onnx", imgsz=640, half=False)