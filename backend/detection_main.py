from ultralytics import YOLO
import matplotlib.pyplot as plt 
import cv2
import json
import numpy as np
from pathlib import Path
BASE_DIR = Path(__file__).parent

def get_seat_occupation(seat_mask, detections_mask, min_seat_overlap=0.05, min_person_overlap=0.05):
    """
    Determine if a seat is occupied based on the overlap between the seat mask and the detections mask.

    Args:
        seat_mask (np.ndarray): Binary mask of the seat area (1 for seat, 0 for background).
        detections_mask (np.ndarray): Mask with unique segment IDs for detected objects (0 for background).
        min_seat_overlap (float): Minimum required overlap ratio of the seat area covered by the detected segment to consider it as occupying the seat.
        min_person_overlap (float): Minimum required overlap ratio of the detected segment that overlaps with the seat to consider it as occupying
    
    Returns:
        dict or None: Information about the seat occupation if it's occupied, otherwise None.
    """
    
    occupation = detections_mask[seat_mask > 0]  # Get the values of the segments that overlap with the seat
    unique_ids, counts = np.unique(occupation, return_counts=True)
    
    # Filter out the background (ID 0)
    valid_idx = unique_ids > 0
    unique_ids = unique_ids[valid_idx]
    counts = counts[valid_idx]
    
    if len(unique_ids) == 0:
        return None  # No overlapping segment, seat is empty
    
    # Get the segment ID with the maximum overlap
    occupation_id = unique_ids[np.argmax(counts)]
    overlap_area = counts.max()
    
    # Calculate the area of the seat and the overlapping segment
    seat_area = np.sum(seat_mask > 0)
    occupation_area = np.sum(detections_mask == occupation_id)
    
    if seat_area == 0 or occupation_area == 0:
        return None  # Avoid division by zero
    
    # Calculate the overlap ratios
    seat_overlap_ratio = overlap_area / seat_area # how much of the seat is covered by the segmentated object
    occupation_overlap_ratio = overlap_area / occupation_area # how much of the segmentated object overlaps with the seat
    
    if seat_overlap_ratio >= min_seat_overlap or occupation_overlap_ratio >= min_person_overlap:
        return {
            "segment_id": occupation_id,
            "seat_overlap_ratio": seat_overlap_ratio,
            "occupation_overlap_ratio": occupation_overlap_ratio
        }  # Seat is occupied by the segment with this ID

    return None  # Seat is considered empty

def compute_detections_mask_info(result):
    """
    Create a mask where the pixels of each segmented object are filled with an unique ID corresponding to the segment index (starting from 1).
    
    Args:
        result: The result object from the YOLO model prediction containing masks and boxes.
    
    Returns:
        np.ndarray: A mask with unique segment IDs for detected objects (0 for background).
        dict: A dictionary containing information about each detected object.
    """
    detections_mask = np.zeros(result.orig_shape, dtype=np.uint8)  # Initialize an empty mask
    detections_info = {}  # Dictionary to store box, confidence, and class info
    for seg_id, (polygon, box) in enumerate(zip(result.masks.xy, result.boxes)):
        seg_id = seg_id + 1  # Start segment IDs from 1 to reserve 0 for background
        cv2.fillPoly(detections_mask, [polygon.astype(np.int32)], color=seg_id)  # Fill the polygon with a unique ID (starting from 1)
        detections_info[seg_id] = {
            "box": box.xyxy[0].tolist(),         # Box coordinates [xmin, ymin, xmax, ymax]
            "confidence": box.conf.item(),       # Confidence (e.g., 0.85)
            "class": int(box.cls.item())         # Predicted class (e.g., 0 for person)
        }
    return detections_mask, detections_info

def classroom_status(room_id, detection_model, detection_args):
    """
    Compute the status of the classroom by analyzing the occupation of each seat based on the segmentation results.
    Args:
        room_id (str): Identifier for the classroom to analyze.
        detection_model (YOLO): YOLO model instance, preloaded for efficiency.
        detection_args (dict): Arguments for the detection model:
            - conf_threshold (float): Confidence threshold for the detection model.
            - classes (list): List of class IDs to consider for detection.
    Returns:
        json: A JSON object containing the status of each seat in the classroom
    """
    
    
    # Load the image for the specified classroom
    image_path = BASE_DIR / f"data/classroom_{room_id}.jpeg"
    if not image_path.exists():
        # check if the image is in png format
        image_path = BASE_DIR / f"data/classroom_{room_id}.png"
        if not image_path.exists():
            raise FileNotFoundError(f"Image for classroom {room_id} not found.")
    
    # Perform detection and segmentation on the image
    results = detection_model.predict(
        str(image_path), 
        conf=detection_args["conf_threshold"], 
        classes=detection_args["classes"])
    
    result = results[0]
    
    # Compute the detections mask and info
    detections_mask, detections_info = compute_detections_mask_info(result)
    
    # Get classroom seats data from the corresponding JSON file
    try:
        with open(BASE_DIR / f"mask/classroom_{room_id}_seats.json", "r") as f:
            seats_data = json.load(f)
            seats_mask_size = (seats_data['image_size']['height'], seats_data['image_size']['width'])
            if seats_mask_size != result.orig_shape:
                raise ValueError(f"Seat mask dimensions {seats_mask_size} do not match the original image dimensions {result.orig_shape}")
    except FileNotFoundError:
        raise FileNotFoundError(f"Seat information for classroom {room_id} not found.")
    
    
    # Analyze the occupation of each seat
    seats_list = seats_data['seats']
    occupation_results = [] # Dictionary to store occupation info for each seat
    
    for seat in seats_list:
        seat_id = seat['id']
        # Get the bounding box coordinates for the seat
        x_coords = [pt['x'] for pt in seat['points']]
        y_coords = [pt['y'] for pt in seat['points']]
        x_min, x_max = int(min(x_coords)), int(max(x_coords))
        y_min, y_max = int(min(y_coords)), int(max(y_coords))
        
        # Create a binary mask for the current seat (1 for seat area, 0 for background)
        seat_mask = np.zeros(result.orig_shape, dtype=np.uint8)
        cv2.rectangle(seat_mask, (x_min, y_min), (x_max, y_max), 1, thickness=-1)
        
        seat_occupation_info = get_seat_occupation(seat_mask, detections_mask)
        cls_mapping = {0: "person", 63: "laptop", 24: "backpack"}
        
        if seat_occupation_info is not None:
            seat_occupation_result = {
                "seat_id": seat_id,
                "occupied": True,
                "seat_overlap_ratio": seat_occupation_info["seat_overlap_ratio"],
                "occupated_by_segment_id": cls_mapping.get(detections_info[seat_occupation_info["segment_id"]]["class"], "unknown")
            }
        else:
            seat_occupation_result = {
                "seat_id": seat_id,
                "occupied": False,
                "seat_overlap_ratio": 0.0,
                "occupated_by_segment_id": None
            }
        occupation_results.append(seat_occupation_result)
    
    return occupation_results
    
    
    
    
    

    