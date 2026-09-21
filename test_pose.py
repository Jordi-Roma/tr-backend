import os
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
import numpy as np
from PIL import Image

model_path = os.path.join(os.path.dirname(__file__), "pose_landmarker.task")
base_options = python.BaseOptions(model_asset_path=model_path)
options = vision.PoseLandmarkerOptions(
    base_options=base_options,
    output_segmentation_masks=True,
)
detector = vision.PoseLandmarker.create_from_options(options)

test_img_path = "static/tryon/tryon_1789899914_a8bd56c5.jpg"
if os.path.exists(test_img_path):
    image = mp.Image.create_from_file(test_img_path)
    detection_result = detector.detect(image)
    if detection_result.pose_landmarks:
        print("Pose detected! Number of poses:", len(detection_result.pose_landmarks))
        landmarks = detection_result.pose_landmarks[0]
        # Landmarks:
        # 0: nose, 11: left shoulder, 12: right shoulder, 23: left hip, 24: right hip,
        # 25: left knee, 26: right knee, 27: left ankle, 28: right ankle
        print("Nose:", landmarks[0].x, landmarks[0].y)
        print("Left Shoulder:", landmarks[11].x, landmarks[11].y)
        print("Right Shoulder:", landmarks[12].x, landmarks[12].y)
        print("Left Hip:", landmarks[23].x, landmarks[23].y)
        print("Right Hip:", landmarks[24].x, landmarks[24].y)
        print("Left Knee:", landmarks[25].x, landmarks[25].y)
        print("Right Knee:", landmarks[26].x, landmarks[26].y)
        print("Left Ankle:", landmarks[27].x, landmarks[27].y)
        print("Right Ankle:", landmarks[28].x, landmarks[28].y)
        if detection_result.segmentation_masks:
            print("Segmentation mask detected!")
    else:
        print("No pose detected.")
else:
    print("Test image does not exist.")
