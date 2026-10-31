import os
import cv2
import mediapipe as mp
import pyautogui
import math
import time
import asyncio
import edge_tts
import pygame
import ctypes

# 1. Прискорення емуляції миші через WinAPI
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.0

SetCursorPos = ctypes.windll.user32.SetCursorPos
mouse_event = ctypes.windll.user32.mouse_event

MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004

SCREEN_WIDTH, SCREEN_HEIGHT = pyautogui.size()

# 2. Налаштування робочої зони та чутливості
FRAME_W, FRAME_H = 640, 480
# Відступи для підвищення чутливості (чим більші значення — тим менше треба рухати рукою)
MARGIN_X = 110  
MARGIN_Y = 90   

# Параметри згладжування
ALPHA = 0.35            # Чутливість згладжування (0.2 - 0.5)
DEADZONE = 2            # Зона нечутливості в пікселях
CLICK_THRESHOLD = 30    # Відстань між пальцями для кліку
CLICK_DEBOUNCE = 0.35   # Пауза між кліками

# 3. Голосовий модуль
VOICE = "uk-UA-OstapNeural"
AUDIO_FILE = "temp_voice.mp3"

async def _play_voice(text: str):
    communicate = edge_tts.Communicate(text, VOICE)
    await communicate.save(AUDIO_FILE)
    pygame.mixer.init()
    pygame.mixer.music.load(AUDIO_FILE)
    pygame.mixer.music.play()
    while pygame.mixer.music.get_busy():
        await asyncio.sleep(0.05)
    pygame.mixer.quit()
    if os.path.exists(AUDIO_FILE):
        try:
            os.remove(AUDIO_FILE)
        except Exception:
            pass

def speak(text: str):
    print(f"🎙️ Tengu: {text}")
    try:
        asyncio.run(_play_voice(text))
    except Exception as e:
        print(f"Помилка звуку: {e}")

# 4. Ініціалізація MediaPipe
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils
hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=1,
    min_detection_confidence=0.6,
    min_tracking_confidence=0.6
)

cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_W)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_H)

# Вимикаємо буферизацію камери для усунення відставання кадру
cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

prev_x, prev_y = SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2
last_click_time = 0

speak("Систему налаштовано на ультра-плавність.")

while cap.isOpened():
    success, frame = cap.read()
    if not success:
        break

    frame = cv2.flip(frame, 1)
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = hands.process(rgb_frame)

    current_time = time.time()

    # Малюємо активну рамку (зелений прямокутник)
    cv2.rectangle(
        frame, 
        (MARGIN_X, MARGIN_Y), 
        (FRAME_W - MARGIN_X, FRAME_H - MARGIN_Y), 
        (0, 255, 120), 
        2
    )

    if results.multi_hand_landmarks:
        hand_landmarks = results.multi_hand_landmarks[0]
        mp_drawing.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)

        lm_4 = hand_landmarks.landmark[4]  # Великий палець
        lm_8 = hand_landmarks.landmark[8]  # Вказівний палець

        # Координати вказівного пальця в пікселях камери
        px_8 = int(lm_8.x * FRAME_W)
        py_8 = int(lm_8.y * FRAME_H)

        # Інтерполяція координат рамки в роздільну здатність екрана
        # Обмежуємо рух у межах рамки (clamp)
        clamped_x = max(MARGIN_X, min(px_8, FRAME_W - MARGIN_X))
        clamped_y = max(MARGIN_Y, min(py_8, FRAME_H - MARGIN_Y))

        norm_x = (clamped_x - MARGIN_X) / (FRAME_W - 2 * MARGIN_X)
        norm_y = (clamped_y - MARGIN_Y) / (FRAME_H - 2 * MARGIN_Y)

        target_x = int(norm_x * SCREEN_WIDTH)
        target_y = int(norm_y * SCREEN_HEIGHT)

        dx = target_x - prev_x
        dy = target_y - prev_y

        # Фільтрація тремору
        if math.hypot(dx, dy) > DEADZONE:
            curr_x = int(prev_x + ALPHA * dx)
            curr_y = int(prev_y + ALPHA * dy)
            SetCursorPos(curr_x, curr_y)
            prev_x, prev_y = curr_x, curr_y

        # Клік через дотик великого і вказівного пальців
        px_4 = int(lm_4.x * FRAME_W)
        py_4 = int(lm_4.y * FRAME_H)
        pinch_dist = math.hypot(px_8 - px_4, py_8 - py_4)

        if pinch_dist < CLICK_THRESHOLD:
            if current_time - last_click_time > CLICK_DEBOUNCE:
                mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                last_click_time = current_time
                cv2.circle(frame, (px_8, py_8), 12, (0, 0, 255), cv2.FILLED)

    cv2.imshow("TENGU Vision Test", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()