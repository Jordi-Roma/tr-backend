import numpy as np
from PIL import Image, ImageFilter

def aplicar_preservacion_facial(orig_pil: Image.Image, neural_pil: Image.Image, landmarks, h_u: int) -> Image.Image:
    """Restaura la cabeza, rostro y cabello original para garantizar cero deformación."""
    if not landmarks:
        return neural_pil

    # Línea de hombros (landmarks 11 y 12)
    sh_min_y = min(landmarks[11].y, landmarks[12].y) * h_u
    # Corte suave en la base del cuello
    cut_y = int(sh_min_y + 15)
    blend_height = 30
    start_y = max(0, cut_y - blend_height)

    # Crear máscara de blend vertical suave
    w, h = orig_pil.size
    mask = np.zeros((h, w), dtype=np.float32)
    # Por encima de start_y es 100% rostro original
    mask[:start_y, :] = 1.0
    # Transición suave
    for y in range(start_y, min(cut_y, h)):
        factor = 1.0 - ((y - start_y) / float(blend_height))
        mask[y, :] = factor

    orig_arr = np.array(orig_pil.convert("RGB")).astype(np.float32)
    neur_arr = np.array(neural_pil.convert("RGB")).astype(np.float32)

    # Broadcast mask
    m3 = np.expand_dims(mask, 2)
    blended = (orig_arr * m3 + neur_arr * (1.0 - m3)).clip(0, 255).astype(np.uint8)
    return Image.fromarray(blended)

print("Función de preservación facial definida correctamente.")
