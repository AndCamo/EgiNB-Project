from detection_main import classroom_status, compute_detections_mask_info
from ultralytics import YOLO

import json
from pathlib import Path
import time

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

BASE_DIR = Path(__file__).parent

# initialize FastAPI server
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
# ====== SERVER CONFIGURATION ======
HOST = "0.0.0.0"
PORT = 8080



# load the YOLO model once at startup to avoid reloading it for each request
model_name = "yolo26l-seg.pt"
model_path = BASE_DIR / "weights" / model_name
model = YOLO(str(model_path))

# API endpoint to get the status of a classroom
# ATTENTION: the classroom_id should be passed as a query parameter, e.g., /api/status?classroom_id=1
@app.get("/api/status")
async def get_classroom_status(classroom_id: int):
    # check if the classroom_id is provided and valid
    if classroom_id is None or not isinstance(classroom_id, int) or classroom_id < 0:
        raise HTTPException(status_code=400, detail="Invalid classroom ID")
    
    detection_args = {
        "conf_threshold": 0.1,
        "classes": [0, 63, 24]  # person, chair, backpack
    }
    json_path = BASE_DIR / "output" / f"classroom_{classroom_id}_occupation_results.json"
    
    current_time = time.time()
    file_exists = Path(json_path).exists()
    
    # Check if we need to compute new status (file doesn't exist or is older than 30 seconds)
    needs_update = True
    if file_exists:
        file_creation_time = Path(json_path).stat().st_mtime
        if current_time - file_creation_time <= 30:
            needs_update = False
            
    if needs_update:
        print("Results are missing or older than 30 seconds, computing new status...")
        try:
            occupation_results = classroom_status(classroom_id, model, detection_args)
            # save the new results in the json file
            # Make sure output directory exists
            Path(json_path).parent.mkdir(parents=True, exist_ok=True)
            with open(json_path, 'w') as f:
                json.dump(occupation_results, f, indent=4)
                
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    else:
        print("Results are recent, returning existing status...")
        with open(json_path) as f:
            occupation_results = json.load(f)
            
    return occupation_results
        
        


@app.get("/health")
async def health():
    return {"ok": True}


if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT)
