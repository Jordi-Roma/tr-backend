import os
import cv2
import numpy as np
from PIL import Image, ImageFilter
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

jeans_path = "static/images/cutouts/jeans_denim_3d.png"

# Remove any bottom/side white trim
j_img = cv2.imread(jeans_path, cv2.IMREAD_UNCHANGED)
# Trim 8 pixels from bottom and 2 pixels from sides
j_img = j_img[:-8, 2:-2]
# Threshold out any pixels that are light/white (R,G,B > 210)
rgb = j_img[:, :, :3]
white_pixels = (rgb[:, :, 0] > 200) & (rgb[:, :, 1] > 200) & (rgb[:, :, 2] > 200)
j_img[white_pixels, 3] = 0
cv2.imwrite(jeans_path, j_img)

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
mask_np = res.segmentation_masks[0].numpy_view()[:, :, 0]

sh_y = (lm[11].y + lm[12].y) / 2.0 * h_u
hip_y = (lm[23].y + lm[24].y) / 2.0 * h_u
ank_y = max(lm[27].y, lm[28].y) * h_u

# Belt / waist level is typically at 45% between shoulders and hip landmarks
waist_y = sh_y + (hip_y - sh_y) * 0.42

# Width across hips/pelvis: find maximum body width between waist_y and hip_y
widths = []
centers = []
for y in range(int(waist_y), int(hip_y + (ank_y - hip_y) * 0.15), 5):
    xs = np.where(mask_np[y, :] > 0.35)[0]
    if len(xs) > 10:
        widths.append(xs[-1] - xs[0])
        centers.append((xs[0] + xs[-1]) / 2.0)

max_pelvis_w = max(widths) if widths else w_u * 0.45
avg_center_x = float(np.mean(centers)) if centers else w_u * 0.5

# Target jeans dimensions: generous width to wrap around hips/shorts with natural ease
target_w = int(max_pelvis_w * 1.14)
target_h = int((ank_y - waist_y) * 1.03)
pos_x = int(avg_center_x - target_w / 2.0)
pos_y = int(waist_y)

print(f"Waist Y: {waist_y:.1f}, Ankle Y: {ank_y:.1f}")
print(f"Max pelvis width: {max_pelvis_w:.1f}, Target jeans: {target_w}x{target_h} at ({pos_x}, {pos_y})")

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

canvas.convert("RGB").save("static/tryon/perfect_jeans_fit_v2.jpg", "JPEG", quality=95)
print("Saved static/tryon/perfect_jeans_fit_v2.jpg!")
