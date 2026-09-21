import os
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
import numpy as np
from PIL import Image, ImageFilter, ImageOps

model_path = os.path.join(os.path.dirname(__file__), "pose_landmarker.task")
base_options = python.BaseOptions(model_asset_path=model_path)
options = vision.PoseLandmarkerOptions(
    base_options=base_options,
    output_segmentation_masks=True,
)
detector = vision.PoseLandmarker.create_from_options(options)

# Load user image and cutout
user_img_path = "static/tryon/tryon_1789899914_a8bd56c5.jpg"
jeans_cutout_path = "static/images/cutouts/jeans_denim_3d.png"

user_img = Image.open(user_img_path).convert("RGBA")
jeans_img = Image.open(jeans_cutout_path).convert("RGBA")

w_user, h_user = user_img.size
mp_image = mp.Image.create_from_file(user_img_path)
detection_result = detector.detect(mp_image)

if detection_result.pose_landmarks:
    lm = detection_result.pose_landmarks[0]
    
    # Hips (23 left, 24 right)
    hip_lx, hip_ly = lm[23].x * w_user, lm[23].y * h_user
    hip_rx, hip_ry = lm[24].x * w_user, lm[24].y * h_user
    hip_cx = (hip_lx + hip_rx) / 2.0
    hip_cy = (hip_ly + hip_ry) / 2.0
    hip_w = abs(hip_lx - hip_rx)
    
    # Ankles (27 left, 28 right)
    ank_lx, ank_ly = lm[27].x * w_user, lm[27].y * h_user
    ank_rx, ank_ry = lm[28].x * w_user, lm[28].y * h_user
    ank_cy = max(ank_ly, ank_ry)
    
    print(f"User size: {w_user}x{h_user}")
    print(f"Hips: center=({hip_cx:.1f}, {hip_cy:.1f}), width={hip_w:.1f}")
    print(f"Ankles Y: {ank_cy:.1f}")
    
    # Calculate target dimensions for jeans
    # Jeans should start slightly above hip_cy (waist line) and go down to ankles
    waist_y = hip_cy - (ank_cy - hip_cy) * 0.16 # waist sits above hip line
    legs_h = ank_cy - waist_y
    
    # Target width proportional to hip width with realistic fit padding
    target_w = int(max(hip_w * 2.1, w_user * 0.38))
    target_h = int(legs_h * 1.02)
    
    pos_x = int(hip_cx - target_w / 2.0)
    pos_y = int(waist_y)
    
    print(f"Target jeans size: {target_w}x{target_h} at ({pos_x}, {pos_y})")
    
    jeans_resized = jeans_img.resize((target_w, target_h), Image.Resampling.LANCZOS)
    
    # Create contact shadow
    alpha = jeans_resized.split()[3]
    shadow_mask = alpha.filter(ImageFilter.GaussianBlur(radius=int(target_w * 0.02) + 3))
    shadow_layer = Image.new("RGBA", (target_w, target_h), (10, 15, 25, 110))
    shadow = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
    shadow.paste(shadow_layer, (0, 0), shadow_mask)
    
    canvas = user_img.copy()
    # Composite shadow slightly offset
    canvas.alpha_composite(shadow, (pos_x + 1, pos_y + 4))
    # Composite jeans
    canvas.alpha_composite(jeans_resized, (pos_x, pos_y))
    
    output_path = "static/tryon/jeans_test_pose.jpg"
    canvas.convert("RGB").save(output_path, "JPEG", quality=95)
    print(f"Saved test output to {output_path}!")
else:
    print("No pose detected.")
