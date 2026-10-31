import cv2
import numpy as np

# ================= НАЛАШТУВАННЯ (ULTRA DETAIL + SLOW-MO) =================
INPUT_VIDEO = "video_1.mp4"
OUTPUT_VIDEO = "tengu_matrix_output.mp4"

CHAR_SIZE = 2                         # 2 px = пікова чіткість (очі, пір'я, кімоно)
TARGET_FPS = 5                        # Повільний кіберпанк-темп відтворення
FRAME_STEP = 1                        # Обробка кожного вхідного кадру (максимальне сповільнення)

BRIGHTNESS_BOOST = 1.85               # Висока світлосила для читабельності деталей
CONTRAST_THRESHOLD = 18               # Поріг відсікання темного фону
# =========================================================================

def process_matrix_video():
    cap = cv2.VideoCapture(INPUT_VIDEO)
    if not cap.isOpened():
        print(f"[ERR] Не вдалося відкрити {INPUT_VIDEO}")
        return

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    orig_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    cols = width // CHAR_SIZE
    rows = height // CHAR_SIZE
    out_w = cols * CHAR_SIZE
    out_h = rows * CHAR_SIZE

    print(f"[INFO] Сітка: {cols}x{rows} символів ({cols * rows} гліфів/кадр)")
    print(f"[INFO] Вхідний FPS: {orig_fps:.1f} -> Швидкість рендеру: {TARGET_FPS} FPS (Slow-Mo)")

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(OUTPUT_VIDEO, fourcc, TARGET_FPS, (out_w, out_h))

    current_in_frame = 0
    saved_frames = 0

    while True:
        ret, frame = cap.read()
        if not ret or frame is None:
            break

        current_in_frame += 1
        if current_in_frame % FRAME_STEP != 0:
            continue

        # Підсилення експозиції для проявлення форми
        boosted = cv2.convertScaleAbs(frame, alpha=BRIGHTNESS_BOOST, beta=20)
        small_bgr = cv2.resize(boosted, (cols, rows), interpolation=cv2.INTER_AREA)
        small_gray = cv2.cvtColor(small_bgr, cv2.COLOR_BGR2GRAY)

        b = small_bgr[:, :, 0].astype(np.float32)
        g = small_bgr[:, :, 1].astype(np.float32)
        r = small_bgr[:, :, 2].astype(np.float32)
        lum = small_gray.astype(np.float32)

        # Детекція кольорових акцентів
        is_red = (r > b + 12) & (r > g + 12)
        is_highlight = lum > 175

        out_r = np.zeros((rows, cols), dtype=np.uint8)
        out_g = np.zeros((rows, cols), dtype=np.uint8)
        out_b = np.zeros((rows, cols), dtype=np.uint8)

        # 1. Неоново-червоний колір маски Тенгу
        mask_red = is_red & (lum >= CONTRAST_THRESHOLD)
        out_r[mask_red] = np.clip(lum[mask_red] * 1.6 + 65, 0, 255).astype(np.uint8)
        out_g[mask_red] = np.clip(lum[mask_red] * 0.15, 0, 255).astype(np.uint8)
        out_b[mask_red] = np.clip(lum[mask_red] * 0.15, 0, 255).astype(np.uint8)

        # 2. Світлі відблиски та контури пір'я
        mask_hi = (~is_red) & is_highlight & (lum >= CONTRAST_THRESHOLD)
        out_r[mask_hi] = 255
        out_g[mask_hi] = np.clip(lum[mask_hi] * 0.85, 0, 255).astype(np.uint8)
        out_b[mask_hi] = np.clip(lum[mask_hi] * 0.85, 0, 255).astype(np.uint8)

        # 3. Тіні та складки одягу
        mask_mid = (~is_red) & (~is_highlight) & (lum >= CONTRAST_THRESHOLD)
        out_r[mask_mid] = np.clip(lum[mask_mid] * 1.3 + 30, 0, 255).astype(np.uint8)
        out_g[mask_mid] = 20
        out_b[mask_mid] = 20

        color_stack = np.stack([out_b, out_g, out_r], axis=2)
        zoomed = cv2.resize(color_stack, (out_w, out_h), interpolation=cv2.INTER_NEAREST)

        # Бінарне чергування 0 та 1
        random_pattern = np.random.choice([0, 1], size=(rows, cols)).astype(np.uint8)
        pattern_zoomed = cv2.resize(random_pattern, (out_w, out_h), interpolation=cv2.INTER_NEAREST)

        grid_mask = np.ones((out_h, out_w), dtype=np.uint8)
        grid_mask[::CHAR_SIZE, ::CHAR_SIZE] = pattern_zoomed[::CHAR_SIZE, ::CHAR_SIZE]

        zoomed[:, :, 0] = cv2.bitwise_and(zoomed[:, :, 0], zoomed[:, :, 0], mask=grid_mask)
        zoomed[:, :, 1] = cv2.bitwise_and(zoomed[:, :, 1], zoomed[:, :, 1], mask=grid_mask)
        zoomed[:, :, 2] = cv2.bitwise_and(zoomed[:, :, 2], zoomed[:, :, 2], mask=grid_mask)

        out.write(zoomed)
        saved_frames += 1

        if current_in_frame % 20 == 0:
            print(f"[STATUS] Обробка: {current_in_frame}/{total_frames} кадрів...")

    cap.release()
    out.release()
    print(f"\n[DONE] Сповільнене відео згенеровано: {OUTPUT_VIDEO} ({saved_frames} кадрів @ {TARGET_FPS} FPS)")

if __name__ == "__main__":
    process_matrix_video()