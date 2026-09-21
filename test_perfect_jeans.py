import os
import cv2
import numpy as np
from PIL import Image, ImageFilter
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

# 1. Clean bottom hem of jeans cutout if any white line exists
jeans_path = "static/images/cutouts/jeans_denim_3d.png"
j_img = cv2.imread(jeans_path, cv2.IMREAD_UNCHANGED)
# Crop 4 pixels from bottom to eliminate any hem edge line from studio photo
j_img = j_img[:-4, :]
# Clean any residual edge fringing
alpha = j_img[:, :, 3]
alpha = cv2.GaussianBlur(alpha, (5, 5), 0)
j_img[:, :, 3] = alpha
cv2.imwrite(jeans_path, j_img)

# 2. Pose & Mask detection
detector = vision.PoseLandmarker.create_from_options(
    vision.PoseLandmarkerOptions(
        base_options=python.BaseOptions(model_asset_path='pose_landmarker.task'),
        output_segmentation_masks=True,
    )
)

user_img_path = 'static/tryon/tryon_1789899914_a8bd56c5.jpg'
image_mp = mp.Image.create_from_file(user_img_path)
res = detector.detect(image_mp)

user_pil = Image.open(user_img_path).convert("RGBA")
w_u, h_u = user_pil.size

lm = res.pose_landmarks[0]
mask_np = res.segmentation_masks[0].numpy_view()[:, :, 0] # float32 (1024, 768)

# Find waist Y: between shoulders and hips
sh_y = (lm[11].y + lm[12].y) / 2.0 * h_u
hip_y = (lm[23].y + lm[24].y) / 2.0 * h_u
hip_x = (lm[23].x + lm[24].x) / 2.0 * w_u
ank_y = max(lm[27].y, lm[28].y) * h_u

# Belt / waistline is approximately at 65-70% of the torso distance below shoulders
waist_y = sh_y + (hip_y - sh_y) * 0.72

# Measure hip width from segmentation mask around hip_y
sample_y = int(hip_y)
xs = np.where(mask_np[sample_y, :] > 0.4)[0]
if len(xs) > 0:
    measured_hip_w = xs[-1] - xs[0]
    center_x = (xs[0] + xs[-1]) / 2.0
else:
    measured_hip_w = abs(lm[23].x - lm[24].x) * w_u * 1.8
    center_x = hip_x

print(f"Torso: shoulders={sh_y:.1f}, waist={waist_y:.1f}, hips={hip_y:.1f}, ankles={ank_y:.1f}")
print(f"Measured hip width: {measured_hip_w:.1f} at center {center_x:.1f}")

# Target jeans dimensions
target_w = int(measured_hip_w * 1.06)
target_h = int((ank_y - waist_y) * 1.02)
pos_x = int(center_x - target_w / 2.0)
pos_y = int(waist_y)

print(f"Target jeans: {target_w}x{target_h} at ({pos_x}, {pos_y})")

jeans_pil = Image.open(jeans_path).convert("RGBA")
jeans_fitted = jeans_pil.resize((target_w, target_h), Image.Resampling.LANCZOS)

# Create soft drop shadow
shadow = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
j_alpha = jeans_fitted.split()[3]
s_mask = j_alpha.filter(ImageFilter.GaussianBlur(radius=int(target_w * 0.02) + 2))
s_layer = Image.new("RGBA", (target_w, target_h), (15, 18, 25, 95))
shadow.paste(s_layer, (0, 0), s_mask)

canvas = user_pil.copy()
# Paste shadow
canvas.alpha_composite(shadow, (pos_x, pos_y + 3))
# Paste jeans
canvas.alpha_composite(jeans_fitted, (pos_x, pos_y))

canvas.convert("RGB").save("static/tryon/perfect_jeans_fit.jpg", "JPEG", quality=95)
print("Saved static/tryon/perfect_jeans_fit.jpg!")
