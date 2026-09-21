import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from PIL import Image

# 1. Detect user pose
detector = vision.PoseLandmarker.create_from_options(
    vision.PoseLandmarkerOptions(
        base_options=python.BaseOptions(model_asset_path='static/models/pose_landmarker.task'),
        output_segmentation_masks=True,
    )
)

user_img_path = 'static/tryon/tryon_1789899914_a8bd56c5.jpg'
image_mp = mp.Image.create_from_file(user_img_path)
res = detector.detect(image_mp)

user_bgr = cv2.imread(user_img_path)
h_u, w_u = user_bgr.shape[:2]

lm = res.pose_landmarks[0]
mask_np = res.segmentation_masks[0].numpy_view()[:, :, 0]

# User landmarks
sh_lx, sh_ly = lm[11].x * w_u, lm[11].y * h_u
sh_rx, sh_ry = lm[12].x * w_u, lm[12].y * h_u
hip_lx, hip_ly = lm[23].x * w_u, lm[23].y * h_u
hip_rx, hip_ry = lm[24].x * w_u, lm[24].y * h_u
knee_lx, knee_ly = lm[25].x * w_u, lm[25].y * h_u
knee_rx, knee_ry = lm[26].x * w_u, lm[26].y * h_u
ank_lx, ank_ly = lm[27].x * w_u, lm[27].y * h_u
ank_rx, ank_ry = lm[28].x * w_u, lm[28].y * h_u

# Natural waistline
sh_y = (sh_ly + sh_ry) / 2.0
hip_y = (hip_ly + hip_ry) / 2.0
waist_y = sh_y + (hip_y - sh_y) * 0.40

# Pelvis width
xs_waist = np.where(mask_np[int(waist_y), :] > 0.3)[0]
waist_lx = xs_waist[-1] if len(xs_waist) > 0 else hip_lx * 1.05
waist_rx = xs_waist[0] if len(xs_waist) > 0 else hip_rx * 0.95
waist_cx = (waist_lx + waist_rx) / 2.0

# Load jeans cutout
jeans_rgba = cv2.imread('static/images/cutouts/jeans_denim_3d.png', cv2.IMREAD_UNCHANGED)
h_j, w_j = jeans_rgba.shape[:2]

# Define canonical control points on the jeans cutout image
# Source control points (in normalized jeans image coordinates):
# Waist top left, center, right
# Hip left, right, crotch
# Knee left, right
# Ankle left, right
src_pts = np.array([
    [0.10 * w_j, 0.05 * h_j],  # top left waist
    [0.50 * w_j, 0.05 * h_j],  # top center waist
    [0.90 * w_j, 0.05 * h_j],  # top right waist
    [0.05 * w_j, 0.25 * h_j],  # left hip
    [0.50 * w_j, 0.28 * h_j],  # crotch
    [0.95 * w_j, 0.25 * h_j],  # right hip
    [0.22 * w_j, 0.65 * h_j],  # left knee
    [0.78 * w_j, 0.65 * h_j],  # right knee
    [0.20 * w_j, 0.96 * h_j],  # left ankle
    [0.80 * w_j, 0.96 * h_j],  # right ankle
], dtype=np.float32)

# Destination control points on user image:
# Note: MediaPipe Left is user's left (viewer's right)
# On image: viewer left is x smaller, viewer right is x larger
dst_waist_left = min(waist_lx, waist_rx) - 15
dst_waist_right = max(waist_lx, waist_rx) + 15
dst_waist_center = waist_cx

dst_hip_left = min(hip_lx, hip_rx) - 20
dst_hip_right = max(hip_lx, hip_rx) + 20
dst_crotch_x = (hip_lx + hip_rx) / 2.0
dst_crotch_y = hip_y + 15

dst_knee_left = min(knee_lx, knee_rx)
dst_knee_right = max(knee_lx, knee_rx)
dst_ank_left = min(ank_lx, ank_rx)
dst_ank_right = max(ank_lx, ank_rx)

dst_pts = np.array([
    [dst_waist_left, waist_y],
    [dst_waist_center, waist_y - 5],
    [dst_waist_right, waist_y],
    [dst_hip_left, hip_y],
    [dst_crotch_x, dst_crotch_y],
    [dst_hip_right, hip_y],
    [dst_knee_left, (knee_ly + knee_ry) / 2.0],
    [dst_knee_right, (knee_ly + knee_ry) / 2.0],
    [dst_ank_left, max(ank_ly, ank_ry)],
    [dst_ank_right, max(ank_ly, ank_ry)],
], dtype=np.float32)

# Build Thin Plate Spline transformer
tps = cv2.createThinPlateSplineShapeTransformer()
# Reshape to (1, N, 2)
matches = [cv2.DMatch(i, i, 0) for i in range(len(src_pts))]
tps.estimateTransformation(dst_pts.reshape(1, -1, 2), src_pts.reshape(1, -1, 2), matches)

# Warp jeans to user body shape!
warped_jeans = tps.warpImage(jeans_rgba)

# Crop / pad to match user_bgr dimensions
warped_jeans = cv2.resize(warped_jeans, (w_u, h_u))

# Composite onto user
canvas = user_bgr.copy()
b, g, r, a = cv2.split(warped_jeans)
alpha_f = (a.astype(np.float32) / 255.0)[:, :, np.newaxis]

# Add subtle drop shadow
shadow_mask = cv2.GaussianBlur(a, (15, 15), 0)
shadow_f = (shadow_mask.astype(np.float32) / 255.0 * 0.45)[:, :, np.newaxis]
canvas = (canvas.astype(np.float32) * (1.0 - shadow_f) + np.array([15, 20, 30]) * shadow_f).astype(np.uint8)

# Composite warped jeans
fg = cv2.merge([b, g, r]).astype(np.float32)
bg = canvas.astype(np.float32)
blended = (fg * alpha_f + bg * (1.0 - alpha_f)).astype(np.uint8)

cv2.imwrite('static/tryon/tps_jeans_warped.jpg', blended)
print('TPS warped jeans generated successfully!')
