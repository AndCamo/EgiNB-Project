# 📍P.I.E.N.A.H - Private Image Evaluation Network on Arduino Hardware

<img src="./assets/project-logo.jpg" style="width: 300px; height: auto;" alt="Project Logo">

## 🔍 Overview
P.I.E.N.A.H is an AI-powered system designed to analyze and determine seat occupancy in a classroom environment. It leverages a YOLO-based segmentation model to detect objects (such as people, laptops, and backpacks) and maps these detections to predefined seat masks to determine the availability of each seat. The system includes a FastAPI backend for processing and a Python-based frontend with a Telegram bot integration.

## 📋 Table of Contents
- [Overview](#overview)
- [Project Structure](#project-structure)
- [Backend Logic](#backend-logic)
- [Installation](#installation)

## 📁 Project Structure
```text
.
├── backend/                 # Backend FastAPI server and AI detection logic
│   ├── data/                # Input classroom images
│   ├── mask/                # Predefined seat masks and configurations (JSON)
│   ├── output/              # Generated seat occupancy results
│   ├── weights/             # YOLO model weights
│   ├── detection_main.py    # Core logic for computing detections and seat overlap
│   └── testing-notebook.ipynb # Notebook for testing the YOLO model and segmentation
├── frontend/                # Frontend application components
│   ├── app.py               # Main frontend application
│   ├── seat_mask_editor.html # Tool for creating and editing seat masks
│   ├── telegram_bot.py      # Telegram bot integration
│   └── templates/           # HTML templates and images
├── pyproject.toml           # Project metadata and dependencies (for uv)
├── requirements.txt         # Classic pip dependencies
└── README.md                # This file
```

## ⚙️ Backend Logic

The backend operates as a computer vision pipeline wrapped in a **FastAPI** server, specifically designed to monitor real-time classroom occupancy.

### 1. Object Detection and Segmentation
At its core, the backend uses a pre-trained **YOLO** segmentation model. When a status request is made, the model performs inference on the classroom image to detect specific objects of interest (people, laptops, backpacks). It outputs both bounding boxes and pixel-level segmentation masks for these elements.

### 2. Seat Mapping and Intersections
Rather than compiling a simple crowd count, the system maps the detections to specific physical seats:
- **Seat Configurations:** Each classroom structure is stored in a JSON file (`classroom_{id}_seats.json`) containing exact polygon coordinates for every seat.
- **Overlap Calculation:** The detection engine (inside `detection_main.py`) generates a binary physical mask for each seat and checks the intersection with the YOLO segmentation masks.
- **Occupancy Thresholds:** A seat is marked as `occupied` if the overlap between the detected object and the seat geometry exceeds a defined ratio (`min_seat_overlap` or `min_person_overlap`). The system also identifies *what* is occupying the seat.

### 3. API REST Endpoints
The entire logic is exposed via a seamless REST API:
- `GET /api/status`: Fetches the calculated occupancy data. It checks the timestamps of the generated outputs for freshness and returns a JSON payload detailing the individual status of every seat (free vs. occupied).

## 🚀 Installation

This project requires **Python >= 3.13**. 
The repository has been initializated with `uv` package manager, but it also supports the classic `venv` + `pip` workflow.

- Option 1: Classic method (`venv` + `pip`): 


- Option 2: Fast method (using `uv`)

### Option 1: Classic method (`venv` + `pip`)

1. Create a virtual environment:
   ```bash
   python -m venv .venv
   ```

2. Activate the virtual environment:
   * **Windows:** `.venv\Scripts\activate`
   * **macOS/Linux:** `source .venv/bin/activate`

3. Install the required libraries:
   ```bash
   pip install -r requirements.txt
   ```

### Option 2: Fast method (using `uv`)
If [`uv`](https://docs.astral.sh/uv/) is installed:

1. Sync the environment and install dependencies:
   ```bash
   uv sync
   ```