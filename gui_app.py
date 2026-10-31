import os
import time
import math
import random
import ctypes
from ctypes import wintypes
import threading
import tkinter as tk
import customtkinter as ctk
from PIL import Image, ImageTk
from assistant_window import TenguVoiceAssistant
import cv2
import pyautogui

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

pyautogui.FAILSAFE = False

try:
    import mediapipe as mp
    mp_hands = mp.solutions.hands
    HAS_MEDIAPIPE = True
except ImportError:
    HAS_MEDIAPIPE = False

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
SPLASH_IMG_PATH = os.path.join(ASSETS_DIR, "splash_mask.png")
ICO_PATH = os.path.join(ASSETS_DIR, "tengu.ico")

MATRIX_VID_PATH = os.path.join(BASE_DIR, "tengu_matrix_output.mp4")
if not os.path.exists(MATRIX_VID_PATH):
    MATRIX_VID_PATH = os.path.join(BASE_DIR, "video_1.mp4")

BASE_WIDTH = 1024
EXPANDED_WIDTH = 1600
WINDOW_HEIGHT = 620

MOUSEEVENTF_WHEEL = 0x0800

# Структури Win32 для магнітного пошуку кнопок
class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


user32 = ctypes.windll.user32
user32.WindowFromPoint.argtypes = [POINT]
user32.WindowFromPoint.restype = wintypes.HWND
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(RECT)]


class GestureMiniWidget(tk.Toplevel):
    def __init__(self, parent, on_restore_callback):
        super().__init__(parent)
        self.parent = parent
        self.on_restore_callback = on_restore_callback

        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(bg="#020000")

        w_size = 84
        self.geometry(f"{w_size}x{w_size}+25+25")

        self.canvas = tk.Canvas(
            self, width=w_size, height=w_size,
            bg="#050101", highlightthickness=1, highlightbackground="#FF1111"
        )
        self.canvas.pack(fill="both", expand=True)

        self.img_tk = None
        if os.path.exists(SPLASH_IMG_PATH):
            raw = Image.open(SPLASH_IMG_PATH).resize((60, 44), Image.Resampling.LANCZOS)
            self.img_tk = ImageTk.PhotoImage(raw)
            self.canvas.create_image(w_size // 2, 32, image=self.img_tk)

        self.canvas.create_text(
            w_size // 2, 68, text="TENGU_LINK",
            font=("Consolas", 8, "bold"), fill="#00FF66"
        )

        self.canvas.bind("<Button-1>", lambda e: self.restore())
        self.canvas.bind("<Double-Button-1>", lambda e: self.restore())

    def restore(self):
        self.destroy()
        self.on_restore_callback()


class BinaryScanSplash(tk.Toplevel):
    def __init__(self, parent, on_close_callback):
        super().__init__(parent)
        self.on_close_callback = on_close_callback
        self.parent = parent
        self.parent.withdraw()

        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(bg="#000000")

        self.splash_w = 850
        self.splash_h = 480
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        pos_x = (screen_w - self.splash_w) // 2
        pos_y = (screen_h - self.splash_h) // 2
        self.geometry(f"{self.splash_w}x{self.splash_h}+{pos_x}+{pos_y}")

        self.canvas = tk.Canvas(
            self, width=self.splash_w, height=self.splash_h,
            bg="#000000", highlightthickness=0, bd=0
        )
        self.canvas.pack(fill="both", expand=True)

        if os.path.exists(SPLASH_IMG_PATH):
            raw = Image.open(SPLASH_IMG_PATH).resize((self.splash_w, self.splash_h), Image.Resampling.LANCZOS)
            self.full_img = ImageTk.PhotoImage(raw)
            self.canvas.create_image(0, 0, image=self.full_img, anchor="nw")

        self.curtain = self.canvas.create_rectangle(
            0, 0, self.splash_w, self.splash_h, fill="#000000", outline=""
        )
        self.scan_line = self.canvas.create_line(
            0, 0, self.splash_w, 0, fill="#FF2222", width=2
        )
        self.scan_text = self.canvas.create_text(
            self.splash_w // 2, 0, text="", fill="#FF6666", font=("Consolas", 10, "bold")
        )

        self.current_y = 0
        self.step_size = 6
        self.total_steps = self.splash_h // self.step_size
        self.delay = 3000 // self.total_steps

        self.after(200, self.scan_step)

    def scan_step(self):
        self.current_y += self.step_size
        self.canvas.coords(self.curtain, 0, self.current_y, self.splash_w, self.splash_h)

        glitch_bits = "".join(random.choice(["0", "1", " "]) for _ in range(32))
        self.canvas.coords(self.scan_line, 0, self.current_y, self.splash_w, self.current_y)
        self.canvas.coords(self.scan_text, self.splash_w // 2, max(12, self.current_y - 10))
        self.canvas.itemconfig(self.scan_text, text=f"[DECODING_ROW: {self.current_y:03d}] {glitch_bits}")

        if self.current_y < self.splash_h:
            self.after(self.delay, self.scan_step)
        else:
            self.canvas.delete(self.scan_line)
            self.canvas.delete(self.scan_text)
            self.canvas.delete(self.curtain)
            self.after(500, self.finish)

    def finish(self):
        self.destroy()
        self.on_close_callback()


class TenguApp(ctk.CTk):
    def open_voice_assistant(self):
        if not hasattr(self, "assistant_win") or self.assistant_win is None or not self.assistant_win.winfo_exists():
            self.assistant_win = TenguVoiceAssistant(self)
        self.assistant_win.deiconify()
        self.assistant_win.lift()
        self.assistant_win.focus_force()

    def __init__(self):
        super().__init__()
        
    def __init__(self):
        super().__init__()
        self.withdraw()
        self.title("TENGU // NEURAL MAINFRAME OS")

        if os.path.exists(ICO_PATH):
            self.iconbitmap(ICO_PATH)

        self.screen_w = self.winfo_screenwidth()
        self.screen_h = self.winfo_screenheight()
        self.win_x = max(10, (self.screen_w - EXPANDED_WIDTH) // 2)
        self.win_y = (self.screen_h - WINDOW_HEIGHT) // 2
        self.geometry(f"{BASE_WIDTH}x{WINDOW_HEIGHT}+{self.win_x}+{self.win_y}")
        self.resizable(False, False)
        self.configure(fg_color="#040202")

        # Налаштування 1-100%
        self.val_speed_pct = 40.0
        self.val_smooth_pct = 75.0
        self.val_scroll_pct = 45.0
        self.val_box_pct = 60.0
        self.cfg_hand_priority = "AUTO"

        # Гарантована ініціалізація стану курсора
        self.filtered_x = float(self.screen_w // 2)
        self.filtered_y = float(self.screen_h // 2)
        self.prev_raw_target_x = float(self.screen_w // 2)
        self.prev_raw_target_y = float(self.screen_h // 2)
        self.click_anchor_time = 0.0
        self.last_click_timestamp = 0.0
        self.click_cooldown = 0.28
        self.trigger_click_ready = True
        self.scroll_remainder = 0.0

        self.magnet_locked = False

        self.is_gesture_dock_open = False
        self.mask_holo_tk = None
        self.anim_tick = 0
        self.mini_widget = None

        self.matrix_video_cap = None
        self.holo_vid_img_tk = None

        # Телеметрія
        self.cpu_history = [10.0] * 32
        self.current_cpu_val = 12.0
        self.last_net_bytes = (0, 0)
        self.last_net_time = time.time()
        if HAS_PSUTIL:
            net = psutil.net_io_counters()
            self.last_net_bytes = (net.bytes_recv, net.bytes_sent)

        self.typewriter_text = (
            "WELCOME TO TENGU OS // NEURAL SUB-FRAME ONLINE.\n"
            "CAPABILITIES: CV GESTURE TRACKING, REAL-TIME TELEMETRY, VOICE PROTOCOLS.\n"
            "DIRECTIVE: READY TO OVERRIDE MANUAL PERIPHERALS."
        )
        self.typewriter_index = 0
        self.typewriter_complete_time = None
        self.metrics_state_index = 0
        self.last_metrics_switch = time.time()

        # Асинхронний CV
        self.cap = None
        self.hands_detector = None
        self.cv_thread_running = False
        self.cv_lock = threading.Lock()
        self.latest_landmarks = None
        self.latest_handedness = None
        self.latest_hud_status = "STANDBY"
        self.latest_status_color = "#FF5555"
        self.latest_coords_text = "X: ---  Y: ---"

        BinaryScanSplash(self, self.show_main_app)

    def show_main_app(self):
        self.deiconify()
        self.main_container = tk.Frame(self, bg="#050101")
        self.main_container.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(
            self.main_container, width=BASE_WIDTH, height=WINDOW_HEIGHT,
            bd=0, highlightthickness=0, bg="#050101"
        )
        self.canvas.place(x=0, y=0, width=BASE_WIDTH, height=WINDOW_HEIGHT)

        self.build_matrix_terminal()
        self.build_gesture_dock()
        self.run_terminal_loops()

    def build_matrix_terminal(self):
        self.canvas.delete("all")
        line_col = "#771111"
        accent_red = "#FF1A1A"

        self.canvas.create_line(15, 15, 65, 15, fill=line_col, width=2)
        self.canvas.create_line(15, 15, 15, 65, fill=line_col, width=2)
        self.canvas.create_line(BASE_WIDTH - 15, 15, BASE_WIDTH - 65, 15, fill=line_col, width=2)
        self.canvas.create_line(BASE_WIDTH - 15, 15, BASE_WIDTH - 15, 65, fill=line_col, width=2)
        self.canvas.create_line(15, WINDOW_HEIGHT - 15, 65, WINDOW_HEIGHT - 15, fill=line_col, width=2)
        self.canvas.create_line(15, WINDOW_HEIGHT - 15, 15, WINDOW_HEIGHT - 65, fill=line_col, width=2)
        self.canvas.create_line(BASE_WIDTH - 15, WINDOW_HEIGHT - 15, BASE_WIDTH - 65, WINDOW_HEIGHT - 15, fill=line_col, width=2)
        self.canvas.create_line(BASE_WIDTH - 15, WINDOW_HEIGHT - 15, BASE_WIDTH - 15, WINDOW_HEIGHT - 65, fill=line_col, width=2)

        self.canvas.create_rectangle(75, 18, BASE_WIDTH - 75, 100, outline=accent_red, width=1, fill="#0F0202")
        self.canvas.create_text(
            90, 32, text="[SYS_NODE // DAEMON_CORE // v3.8 MAGNET-STABILIZED]",
            font=("Consolas", 10, "bold"), fill="#FF6666", anchor="w"
        )
        self.header_text = self.canvas.create_text(
            90, 64, text="",
            font=("Consolas", 10, "bold"), fill="#FFFFFF", anchor="w", justify="left"
        )
        self.canvas.create_text(
            BASE_WIDTH - 90, 32, text="SEC_LEVEL: 0x05",
            font=("Consolas", 9), fill="#882222", anchor="e"
        )

        self.typewriter_index = 0
        self.typewriter_complete_time = None
        self.update_typewriter_text()

        self.canvas.create_rectangle(25, 115, 275, 475, outline="#551111", width=1, fill="#070101")
        self.canvas.create_text(40, 130, text="TELEMETRY_LOG", font=("Consolas", 10, "bold"), fill=accent_red, anchor="w")
        self.telemetry_cpu = self.canvas.create_text(40, 152, text="CPU_USAGE : 12.4%", font=("Consolas", 9), fill="#AA4444", anchor="w")
        self.telemetry_ram = self.canvas.create_text(40, 172, text="RAM_ALLOC : 428 MB", font=("Consolas", 9), fill="#AA4444", anchor="w")
        self.telemetry_ping = self.canvas.create_text(40, 192, text="NET_PING  : 18 ms", font=("Consolas", 9), fill="#AA4444", anchor="w")

        self.canvas.create_line(40, 210, 260, 210, fill="#330808", width=1)
        self.canvas.create_text(40, 226, text="LIVE MATRIX DUMP [RAW BYTES]:", font=("Consolas", 9, "bold"), fill="#882222", anchor="w")
        self.chunk_text = self.canvas.create_text(
            40, 245, text="", font=("Consolas", 8), fill="#661818", anchor="nw"
        )

        holo_x, holo_y, holo_w, holo_h = 512, 270, 380, 265
        self.canvas.create_rectangle(holo_x - holo_w // 2, holo_y - holo_h // 2, holo_x + holo_w // 2, holo_y + holo_h // 2, outline="#441010", width=1, fill="#020000")

        if os.path.exists(SPLASH_IMG_PATH):
            raw = Image.open(SPLASH_IMG_PATH).resize((holo_w - 20, holo_h - 20), Image.Resampling.LANCZOS)
            self.mask_holo_tk = ImageTk.PhotoImage(raw)
            self.canvas.create_image(holo_x, holo_y, image=self.mask_holo_tk)

        self.canvas.create_rectangle(BASE_WIDTH - 275, 115, BASE_WIDTH - 25, 475, outline="#551111", width=1, fill="#070101")
        self.canvas.create_text(BASE_WIDTH - 255, 130, text="SUBSYSTEMS", font=("Consolas", 10, "bold"), fill=accent_red, anchor="w")
        self.canvas.create_text(BASE_WIDTH - 255, 155, text="[OK] VOX_ENGINE\n[OK] ASYNC_CV_WORKER\n[OK] BUTTON_MAGNET_LOCK\n[OK] DUAL_1EURO_SMOOTH\n[OK] INERTIAL_SCROLL", font=("Consolas", 8), fill="#44AA55", anchor="nw")

        self.canvas.create_line(BASE_WIDTH - 255, 240, BASE_WIDTH - 45, 240, fill="#330808", width=1)
        self.canvas.create_text(BASE_WIDTH - 255, 255, text="AI STATE: STANDBY", font=("Consolas", 9, "bold"), fill="#FF5555", anchor="w")
        self.hex_id = self.canvas.create_text(BASE_WIDTH - 255, 275, text="HEX: 0x7E01A4B9", font=("Consolas", 8), fill="#772222", anchor="w")

        self.canvas.create_line(BASE_WIDTH - 255, 295, BASE_WIDTH - 45, 295, fill="#330808", width=1)
        self.canvas.create_text(BASE_WIDTH - 255, 310, text="NET TRAFFIC / IO STREAM", font=("Consolas", 9, "bold"), fill=accent_red, anchor="w")
        self.net_down_lbl = self.canvas.create_text(BASE_WIDTH - 255, 335, text="DL : 0.0 KB/s", font=("Consolas", 9), fill="#00FF66", anchor="w")
        self.net_up_lbl = self.canvas.create_text(BASE_WIDTH - 255, 355, text="UP : 0.0 KB/s", font=("Consolas", 9), fill="#00E5FF", anchor="w")
        self.net_total_lbl = self.canvas.create_text(BASE_WIDTH - 255, 380, text="TOTAL RX: ---", font=("Consolas", 8), fill="#AA4444", anchor="w")
        self.net_status_flag = self.canvas.create_text(BASE_WIDTH - 255, 400, text="LINK: FULL DUPLEX 1Gbps", font=("Consolas", 8), fill="#551818", anchor="w")

        self.graph_x = 325
        self.graph_y = 420
        self.graph_w = 375
        self.graph_h = 42

        self.canvas.create_rectangle(
            self.graph_x, self.graph_y,
            self.graph_x + self.graph_w, self.graph_y + self.graph_h,
            outline="#441111", fill="#070202", width=1
        )
        self.cpu_graph_label = self.canvas.create_text(
            self.graph_x + 8, self.graph_y + 10, text="CPU_LOAD_GRAPH: 0.0%",
            font=("Consolas", 8, "bold"), fill="#FF5555", anchor="w"
        )

        self.status_ticker = self.canvas.create_text(
            512, 490, text="SYSTEM STATUS: ULTRA-SMOOTH KINEMATICS ONLINE // MAGNET ACTIVE",
            font=("Consolas", 9), fill="#FF8888"
        )

        btn_y = 550
        btn_w, btn_h = 260, 44

        b1 = ctk.CTkButton(
            self, text="[ ГОЛОСОВЕ КЕРУВАННЯ ]", width=btn_w, height=btn_h,
            fg_color="#180404", hover_color="#360808", border_color=accent_red,
            border_width=1, corner_radius=2, font=("Consolas", 12, "bold"),
            text_color="#FFAAAA", command=lambda: self.on_btn_click("VOICE INPUT TRIGGERED")
        )
        self.canvas.create_window(200, btn_y, window=b1)

        self.btn_gesture_toggle = ctk.CTkButton(
            self, text="[ РОЗГОРНУТИ ЖЕСТИ > ]", width=btn_w, height=btn_h,
            fg_color="#180404", hover_color="#360808", border_color=accent_red,
            border_width=1, corner_radius=2, font=("Consolas", 12, "bold"),
            text_color="#FFAAAA", command=self.toggle_gesture_dock
        )
        self.canvas.create_window(512, btn_y, window=self.btn_gesture_toggle)

        b3 = ctk.CTkButton(
    self, text="[ ГОЛОСОВИЙ АСИСТЕНТ ]", width=btn_w, height=btn_h,
    fg_color="#2B0505", hover_color="#550A0A", border_color="#FF3333",
    border_width=1, corner_radius=2, font=("Consolas", 12, "bold"),
    text_color="#FFCCCC", command=self.open_voice_assistant
)
        self.canvas.create_window(824, btn_y, window=b3)

    def build_gesture_dock(self):
        self.dock_canvas = tk.Canvas(
            self.main_container, width=EXPANDED_WIDTH - BASE_WIDTH, height=WINDOW_HEIGHT,
            bd=0, highlightthickness=0, bg="#040101"
        )
        accent_red = "#FF1A1A"

        self.dock_canvas.create_line(0, 15, 0, WINDOW_HEIGHT - 15, fill=accent_red, width=2)

        self.dock_canvas.create_rectangle(15, 18, 560, 65, outline=accent_red, width=1, fill="#0F0202")
        self.dock_canvas.create_text(
            30, 41, text="[ TENGU // BUTTON MAGNET & BUTTER-SMOOTH REACH ]",
            font=("Consolas", 11, "bold"), fill="#FF6666", anchor="w"
        )

        min_btn = ctk.CTkButton(
            self, text="[ - HUD ]", width=75, height=30,
            fg_color="#1C0404", hover_color="#3A0808", border_color="#FF4444",
            border_width=1, corner_radius=2, font=("Consolas", 9, "bold"),
            text_color="#FFAAAA", command=self.minimize_to_mini_hud
        )
        self.dock_canvas.create_window(440, 41, window=min_btn)

        close_dock_btn = ctk.CTkButton(
            self, text="[ Х ЗГОРНУТИ ]", width=95, height=30,
            fg_color="#240505", hover_color="#450909", border_color=accent_red,
            border_width=1, corner_radius=2, font=("Consolas", 9, "bold"),
            text_color="#FFAAAA", command=self.toggle_gesture_dock
        )
        self.dock_canvas.create_window(520, 41, window=close_dock_btn)

        self.skel_w, self.skel_h = 320, 240
        self.skel_x, self.skel_y = 15, 80
        self.dock_canvas.create_rectangle(
            self.skel_x, self.skel_y, self.skel_x + self.skel_w, self.skel_y + self.skel_h,
            outline=accent_red, width=2, fill="#000000"
        )
        self.skel_tag = "cyber_hand_skel"

        self.hud_hand_state = self.dock_canvas.create_text(
            self.skel_x + 335, 96, text="TRACKING: OFF",
            font=("Consolas", 10, "bold"), fill="#FF5555", anchor="w"
        )
        self.hud_coords = self.dock_canvas.create_text(
            self.skel_x + 335, 114, text="X: ---  Y: ---",
            font=("Consolas", 9), fill="#AA4444", anchor="w"
        )

        self.dock_canvas.create_text(self.skel_x + 335, 136, text="DOMINANT HAND:", font=("Consolas", 8, "bold"), fill="#FF9999", anchor="w")
        self.hand_selector = ctk.CTkSegmentedButton(
            self, values=["AUTO", "RIGHT", "LEFT"], width=210, height=22,
            selected_color="#AA1111", selected_hover_color="#DD2222",
            unselected_color="#180404", unselected_hover_color="#330808",
            font=("Consolas", 8, "bold"), command=self.set_hand_priority
        )
        self.hand_selector.set(self.cfg_hand_priority)
        self.dock_canvas.create_window(self.skel_x + 440, 155, window=self.hand_selector)

        self.vid_w, self.vid_h = 210, 120
        self.vid_x = self.skel_x + 335
        self.vid_y = 178

        self.dock_canvas.create_rectangle(
            self.vid_x, self.vid_y, self.vid_x + self.vid_w, self.vid_y + self.vid_h,
            outline="#771111", width=1, fill="#020000"
        )
        self.dock_canvas.create_text(
            self.vid_x + 8, self.vid_y + 10, text="[HOLO_FEED // TENGU_CORE]",
            font=("Consolas", 7, "bold"), fill="#FF5555", anchor="w"
        )
        self.holo_vid_canvas_id = self.dock_canvas.create_image(
            self.vid_x + self.vid_w // 2, self.vid_y + self.vid_h // 2 + 5
        )

        sliders_y = 340
        spacing = 65

        self.lbl_speed_val = self.dock_canvas.create_text(15, sliders_y, text=f"CURSOR SENSITIVITY: [{int(self.val_speed_pct):02d}%]", font=("Consolas", 9, "bold"), fill="#FF9999", anchor="w")
        s1 = ctk.CTkSlider(self, from_=1.0, to=100.0, width=540, command=self.on_speed_slider)
        s1.set(self.val_speed_pct)
        self.dock_canvas.create_window(285, sliders_y + 20, window=s1)

        self.lbl_smooth_val = self.dock_canvas.create_text(15, sliders_y + spacing, text=f"STABILIZATION FILTER: [{int(self.val_smooth_pct):02d}%]", font=("Consolas", 9, "bold"), fill="#FF9999", anchor="w")
        s2 = ctk.CTkSlider(self, from_=1.0, to=100.0, width=540, command=self.on_smooth_slider)
        s2.set(self.val_smooth_pct)
        self.dock_canvas.create_window(285, sliders_y + spacing + 20, window=s2)

        self.lbl_scroll_val = self.dock_canvas.create_text(15, sliders_y + spacing * 2, text=f"SCROLL SPEED: [{int(self.val_scroll_pct):02d}%]", font=("Consolas", 9, "bold"), fill="#FF9999", anchor="w")
        s3 = ctk.CTkSlider(self, from_=1.0, to=100.0, width=540, command=self.on_scroll_slider)
        s3.set(self.val_scroll_pct)
        self.dock_canvas.create_window(285, sliders_y + spacing * 2 + 20, window=s3)

        self.lbl_box_val = self.dock_canvas.create_text(15, sliders_y + spacing * 3, text=f"REACH COMPRESSION: [{int(self.val_box_pct):02d}%]", font=("Consolas", 9, "bold"), fill="#FF9999", anchor="w")
        s4 = ctk.CTkSlider(self, from_=1.0, to=100.0, width=540, command=self.on_box_slider)
        s4.set(self.val_box_pct)
        self.dock_canvas.create_window(285, sliders_y + spacing * 3 + 20, window=s4)

    def on_speed_slider(self, val):
        self.val_speed_pct = float(val)
        self.dock_canvas.itemconfig(self.lbl_speed_val, text=f"CURSOR SENSITIVITY: [{int(self.val_speed_pct):02d}%]")

    def on_smooth_slider(self, val):
        self.val_smooth_pct = float(val)
        self.dock_canvas.itemconfig(self.lbl_smooth_val, text=f"STABILIZATION FILTER: [{int(self.val_smooth_pct):02d}%]")

    def on_scroll_slider(self, val):
        self.val_scroll_pct = float(val)
        self.dock_canvas.itemconfig(self.lbl_scroll_val, text=f"SCROLL SPEED: [{int(self.val_scroll_pct):02d}%]")

    def on_box_slider(self, val):
        self.val_box_pct = float(val)
        self.dock_canvas.itemconfig(self.lbl_box_val, text=f"REACH COMPRESSION: [{int(self.val_box_pct):02d}%]")

    def toggle_gesture_dock(self):
        if not self.is_gesture_dock_open:
            self.is_gesture_dock_open = True
            self.geometry(f"{EXPANDED_WIDTH}x{WINDOW_HEIGHT}+{self.win_x}+{self.win_y}")
            self.dock_canvas.place(x=BASE_WIDTH, y=0, width=EXPANDED_WIDTH - BASE_WIDTH, height=WINDOW_HEIGHT)
            self.btn_gesture_toggle.configure(text="[ < СХОВАТИ ЖЕСТИ ]")

            if os.path.exists(MATRIX_VID_PATH):
                self.matrix_video_cap = cv2.VideoCapture(MATRIX_VID_PATH)

            self.start_cv_worker_thread()
        else:
            self.is_gesture_dock_open = False
            self.stop_cv_worker_thread()
            if self.matrix_video_cap:
                try:
                    self.matrix_video_cap.release()
                except Exception:
                    pass
                self.matrix_video_cap = None

            self.dock_canvas.place_forget()
            self.geometry(f"{BASE_WIDTH}x{WINDOW_HEIGHT}+{self.win_x}+{self.win_y}")
            self.btn_gesture_toggle.configure(text="[ РОЗГОРНУТИ ЖЕСТИ > ]")

    def set_hand_priority(self, val):
        self.cfg_hand_priority = "RIGHT ONLY" if val == "RIGHT" else ("LEFT ONLY" if val == "LEFT" else "AUTO")

    def minimize_to_mini_hud(self):
        self.withdraw()
        self.mini_widget = GestureMiniWidget(self, self.restore_from_mini_hud)

    def restore_from_mini_hud(self):
        self.deiconify()
        self.lift()
        self.focus_force()

    def start_cv_worker_thread(self):
        if self.cv_thread_running:
            return
        self.cv_thread_running = True
        threading.Thread(target=self._cv_async_worker_loop, daemon=True).start()

    def stop_cv_worker_thread(self):
        self.cv_thread_running = False
        if self.cap:
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None

    def _cv_async_worker_loop(self):
        if HAS_MEDIAPIPE and not self.hands_detector:
            self.hands_detector = mp_hands.Hands(
                max_num_hands=2,
                min_detection_confidence=0.75,
                min_tracking_confidence=0.75
            )

        self.cap = cv2.VideoCapture(0)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        while self.cv_thread_running and self.cap and self.cap.isOpened():
            success, frame = self.cap.read()
            if not success or frame is None:
                time.sleep(0.005)
                continue

            frame = cv2.flip(frame, 1)
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            results = self.hands_detector.process(rgb_frame)

            with self.cv_lock:
                if results and results.multi_hand_landmarks:
                    self.latest_landmarks = results.multi_hand_landmarks
                    self.latest_handedness = results.multi_handedness
                else:
                    self.latest_landmarks = None
                    self.latest_handedness = None

            self._process_hand_kinematics()
            time.sleep(0.002)

    def _get_button_magnet_offset(self, cx, cy):
        try:
            pt = POINT(int(cx), int(cy))
            hwnd = user32.WindowFromPoint(pt)
            if hwnd:
                rect = RECT()
                user32.GetWindowRect(hwnd, ctypes.byref(rect))
                w = rect.right - rect.left
                h = rect.bottom - rect.top
                if 16 <= w <= 280 and 16 <= h <= 100:
                    mid_x = (rect.left + rect.right) // 2
                    mid_y = (rect.top + rect.bottom) // 2
                    dist_to_center = math.hypot(cx - mid_x, cy - mid_y)
                    if dist_to_center < max(w, h) * 0.65:
                        return True, mid_x, mid_y
        except Exception:
            pass
        return False, cx, cy

    def _process_hand_kinematics(self):
        with self.cv_lock:
            landmarks_list = self.latest_landmarks
            handedness_list = self.latest_handedness

        if not landmarks_list or not handedness_list:
            self.latest_hud_status = "STATUS: NO HAND"
            self.latest_status_color = "#FF5555"
            self.latest_coords_text = "X: ---  Y: ---"
            return

        chosen_hand_idx = None
        for idx_h, h_info in enumerate(handedness_list):
            detected_hand = h_info.classification[0].label
            if self.cfg_hand_priority == "RIGHT ONLY" and detected_hand != "Right":
                continue
            if self.cfg_hand_priority == "LEFT ONLY" and detected_hand != "Left":
                continue
            chosen_hand_idx = idx_h
            break

        if chosen_hand_idx is None:
            return

        lm = landmarks_list[chosen_hand_idx].landmark
        hand_label = handedness_list[chosen_hand_idx].classification[0].label

        if lm[0].y < 0.20:
            self.latest_hud_status = f"STATUS: {hand_label.upper()} SAFETY LOCK"
            self.latest_status_color = "#FFAA00"
            return

        v1 = (lm[5].x - lm[0].x, lm[5].y - lm[0].y)
        v2 = (lm[17].x - lm[0].x, lm[17].y - lm[0].y)
        cross_z = v1[0] * v2[1] - v1[1] * v2[0]

        is_backhand = False
        if hand_label == "Right":
            if cross_z < 0.002:
                is_backhand = True
        else:
            if cross_z > -0.002:
                is_backhand = True

        if is_backhand:
            self.latest_hud_status = f"STATUS: {hand_label.upper()} BACKHAND (IGNORED)"
            self.latest_status_color = "#884444"
            return

        thumb_out = lm[4].x < lm[3].x if lm[17].x > lm[5].x else lm[4].x > lm[3].x
        idx_extended = lm[8].y < lm[6].y
        mid_extended = lm[12].y < lm[10].y
        ring_extended = lm[16].y < lm[14].y
        pinky_extended = lm[20].y < lm[18].y

        idx_claw = (lm[8].y > lm[6].y) and (lm[8].y < lm[5].y + 0.07)
        mid_claw = (lm[12].y > lm[10].y) and (lm[12].y < lm[9].y + 0.07)
        ring_claw = (lm[16].y > lm[14].y) and (lm[16].y < lm[13].y + 0.07)

        total_extended = sum([thumb_out, idx_extended, mid_extended, ring_extended, pinky_extended])
        is_claw = idx_claw and mid_claw and ring_claw

        self.latest_coords_text = f"[{hand_label.upper()}] X:{int(lm[8].x*1000):03d} Y:{int(lm[8].y*1000):03d}"

        # 1. КУЛАК (Пауза)
        if total_extended <= 1 and not idx_extended and not is_claw:
            self.latest_hud_status = f"STATUS: {hand_label.upper()} FIST [LOCKED]"
            self.latest_status_color = "#FFAA00"
            self.scroll_remainder = 0.0

        # 2. СКРОЛ ВГОРУ (ДОЛОНЯ)
        elif total_extended >= 4:
            self.latest_hud_status = f"STATUS: {hand_label.upper()} SILKY SCROLL [UP]"
            self.latest_status_color = "#00FFFF"

            target_amount = 14.0 + (self.val_scroll_pct / 100.0) * 48.0
            self.scroll_remainder += target_amount
            if self.scroll_remainder >= 10.0:
                step = int(self.scroll_remainder)
                ctypes.windll.user32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, step, 0)
                self.scroll_remainder -= step
            time.sleep(0.016)

        # 3. СКРОЛ ВНИЗ (ПАЗУРІ)
        elif is_claw:
            self.latest_hud_status = f"STATUS: {hand_label.upper()} SILKY SCROLL [DOWN]"
            self.latest_status_color = "#00E5FF"

            target_amount = 14.0 + (self.val_scroll_pct / 100.0) * 48.0
            self.scroll_remainder += target_amount
            if self.scroll_remainder >= 10.0:
                step = int(self.scroll_remainder)
                ctypes.windll.user32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, -step, 0)
                self.scroll_remainder -= step
            time.sleep(0.016)

        # 4. РУХ КУРСОРА ТА КЛІК
        else:
            self.scroll_remainder = 0.0

            reach_ratio = 0.85 - (self.val_box_pct / 100.0) * 0.52
            half_box = reach_ratio / 2.0
            box_x_min, box_x_max = 0.5 - half_box, 0.5 + half_box
            box_y_min, box_y_max = 0.5 - half_box, 0.5 + half_box

            norm_x = (lm[8].x - box_x_min) / max(0.01, (box_x_max - box_x_min))
            norm_y = (lm[8].y - box_y_min) / max(0.01, (box_y_max - box_y_min))
            norm_x = max(0.0, min(1.0, norm_x))
            norm_y = max(0.0, min(1.0, norm_y))

            raw_target_x = norm_x * self.screen_w
            raw_target_y = norm_y * self.screen_h

            raw_speed = math.hypot(raw_target_x - self.prev_raw_target_x, raw_target_y - self.prev_raw_target_y)
            self.prev_raw_target_x, self.prev_raw_target_y = raw_target_x, raw_target_y

            filter_weight = 0.08 + (self.val_smooth_pct / 100.0) * 0.22

            if raw_speed < 3.5:
                alpha = filter_weight * 0.18
            elif raw_speed < 20.0:
                alpha = filter_weight * 0.65
            else:
                alpha = min(0.70, filter_weight * 1.85)

            self.filtered_x += (raw_target_x - self.filtered_x) * alpha
            self.filtered_y += (raw_target_y - self.filtered_y) * alpha

            has_magnet, mag_x, mag_y = self._get_button_magnet_offset(self.filtered_x, self.filtered_y)

            final_x = self.filtered_x
            final_y = self.filtered_y

            if has_magnet:
                final_x = self.filtered_x * 0.15 + mag_x * 0.85
                final_y = self.filtered_y * 0.15 + mag_y * 0.85
                self.magnet_locked = True
            else:
                self.magnet_locked = False

            palm_len = math.hypot(lm[5].x - lm[0].x, lm[5].y - lm[0].y)
            dist_thumb_tip_to_pip = math.hypot(lm[4].x - lm[6].x, lm[4].y - lm[6].y)
            dist_thumb_tip_to_mcp = math.hypot(lm[4].x - lm[5].x, lm[4].y - lm[5].y)
            min_thumb_dist = min(dist_thumb_tip_to_pip, dist_thumb_tip_to_mcp)

            trigger_ratio = min_thumb_dist / max(0.04, palm_len)
            is_triggering = idx_extended and (trigger_ratio < 0.46)

            now_ts = time.time()
            if is_triggering:
                self.click_anchor_time = now_ts

            is_anchored = (now_ts - self.click_anchor_time) < 0.22

            if not is_anchored:
                px = int(max(0, min(self.screen_w - 1, final_x)))
                py = int(max(0, min(self.screen_h - 1, final_y)))
                ctypes.windll.user32.SetCursorPos(px, py)

            if is_triggering:
                mag_tag = " [MAGNET LOCKED]" if self.magnet_locked else ""
                self.latest_hud_status = f"STATUS: {hand_label.upper()} TRIGGER [CLICK]{mag_tag}"
                self.latest_status_color = "#FF2222"
                if self.trigger_click_ready and (now_ts - self.last_click_timestamp > self.click_cooldown):
                    pyautogui.click()
                    self.last_click_timestamp = now_ts
                    self.trigger_click_ready = False
            else:
                mag_tag = " [MAGNET ON BUTTON]" if self.magnet_locked else ""
                self.latest_hud_status = f"STATUS: {hand_label.upper()} SMOOTH TRACK{mag_tag}"
                self.latest_status_color = "#00FF66"
                if trigger_ratio > 0.54:
                    self.trigger_click_ready = True

    def on_btn_click(self, log_msg):
        self.canvas.itemconfig(self.status_ticker, text=f"EVENT: {log_msg} // {time.strftime('%H:%M:%S')}")

    def update_typewriter_text(self):
        if self.typewriter_index < len(self.typewriter_text):
            self.typewriter_index += 1
            current_str = self.typewriter_text[:self.typewriter_index] + "█"
            self.canvas.itemconfig(self.header_text, text=current_str)
            self.after(25, self.update_typewriter_text)
        else:
            self.canvas.itemconfig(self.header_text, text=self.typewriter_text)
            if self.typewriter_complete_time is None:
                self.typewriter_complete_time = time.time()

    def run_terminal_loops(self):
        self.anim_tick += 1

        if self.is_gesture_dock_open:
            self.dock_canvas.delete(self.skel_tag)
            self.dock_canvas.itemconfig(self.hud_hand_state, text=self.latest_hud_status, fill=self.latest_status_color)
            self.dock_canvas.itemconfig(self.hud_coords, text=self.latest_coords_text)

            reach_ratio = 0.85 - (self.val_box_pct / 100.0) * 0.52
            half_box = reach_ratio / 2.0
            bx1 = self.skel_x + int((0.5 - half_box) * self.skel_w)
            by1 = self.skel_y + int((0.5 - half_box) * self.skel_h)
            bx2 = self.skel_x + int((0.5 + half_box) * self.skel_w)
            by2 = self.skel_y + int((0.5 + half_box) * self.skel_h)

            self.dock_canvas.create_rectangle(
                bx1, by1, bx2, by2,
                outline="#00E5FF", width=1, dash=(4, 4), tags=self.skel_tag
            )
            self.dock_canvas.create_text(
                bx1 + 5, by1 + 8, text="ACTIVE_ZONE",
                font=("Consolas", 7, "bold"), fill="#00E5FF", anchor="w", tags=self.skel_tag
            )

            with self.cv_lock:
                landmarks_list = self.latest_landmarks

            if landmarks_list:
                for hand_lms in landmarks_list:
                    lm = hand_lms.landmark
                    connections = [
                        (0, 1), (1, 2), (2, 3), (3, 4),
                        (0, 5), (5, 6), (6, 7), (7, 8),
                        (5, 9), (9, 10), (10, 11), (11, 12),
                        (9, 13), (13, 14), (14, 15), (15, 16),
                        (13, 17), (17, 18), (18, 19), (19, 20),
                        (0, 17)
                    ]

                    for p1, p2 in connections:
                        x1 = self.skel_x + int(lm[p1].x * self.skel_w)
                        y1 = self.skel_y + int(lm[p1].y * self.skel_h)
                        x2 = self.skel_x + int(lm[p2].x * self.skel_w)
                        y2 = self.skel_y + int(lm[p2].y * self.skel_h)
                        self.dock_canvas.create_line(x1, y1, x2, y2, fill="#00FF66", width=2, tags=self.skel_tag)

                    for pt in lm:
                        px = self.skel_x + int(pt.x * self.skel_w)
                        py = self.skel_y + int(pt.y * self.skel_h)
                        self.dock_canvas.create_oval(px - 2, py - 2, px + 2, py + 2, fill="#FF1A1A", outline="", tags=self.skel_tag)

            if self.matrix_video_cap and self.matrix_video_cap.isOpened():
                ret_v, v_frame = self.matrix_video_cap.read()
                if not ret_v or v_frame is None:
                    self.matrix_video_cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    ret_v, v_frame = self.matrix_video_cap.read()

                if ret_v and v_frame is not None:
                    frame_scaled = cv2.resize(v_frame, (self.vid_w - 4, self.vid_h - 22))
                    rgb_v = cv2.cvtColor(frame_scaled, cv2.COLOR_BGR2RGB)
                    pil_v = Image.fromarray(rgb_v)
                    self.holo_vid_img_tk = ImageTk.PhotoImage(image=pil_v)
                    self.dock_canvas.itemconfig(self.holo_vid_canvas_id, image=self.holo_vid_img_tk)

        if self.typewriter_complete_time and (time.time() - self.typewriter_complete_time > 10):
            now = time.time()
            if now - self.last_metrics_switch > 3.0:
                self.metrics_state_index = (self.metrics_state_index + 1) % 4
                self.last_metrics_switch = now

            if HAS_PSUTIL:
                ram = psutil.virtual_memory()
                ram_text = f"{int(ram.used / (1024*1024))}MB / {int(ram.total / (1024*1024))}MB ({ram.percent}%)"
                cpu_freq = psutil.cpu_freq().current if psutil.cpu_freq() else 2400
                threads_count = psutil.cpu_count(logical=True)
            else:
                ram_text = "512MB / 16384MB (32%)"
                cpu_freq = 3200
                threads_count = 12

            metrics_presets = [
                f"[LIVE METRIC 1/4] CPU CLOCK FREQ : {cpu_freq:.0f} MHz // THREADS: {threads_count}\nPIPELINE: NORMAL // ZERO CRITICAL OVERHEAD\nACTIVE DAEMONS: ASYNC_CV_CORE, VOX_STREAM, WIN32_PIPE",
                f"[LIVE METRIC 2/4] SYSTEM MEMORY ALLOC : {ram_text}\nVIRTUAL CACHE: SYNCHRONIZED // BUFFER: 100% OK\nPAGE_FILE: OPTIMAL FLOW",
                f"[LIVE METRIC 3/4] NETWORK METRICS // PING: {random.randint(14, 22)} ms\nPACKET LOSS: 0.00% // TCP_WINDOW: OPTIMAL\nINTERFACE: ETHERNET_0 [GIGABIT STREAM]",
                f"[LIVE METRIC 4/4] OPTICAL FRAME BUFFER // TARGET: 60 FPS\nLATENCY: 0.1ms // ASYNC CV THREAD: ONLINE\nNEURAL SKELETON: HARDWARE ACCELERATED"
            ]
            self.canvas.itemconfig(self.header_text, text=metrics_presets[self.metrics_state_index])

        if self.anim_tick % 6 == 0:
            if HAS_PSUTIL:
                try:
                    cpu_p = psutil.cpu_percent()
                except Exception:
                    cpu_p = round(random.uniform(8.0, 22.0), 1)
            else:
                cpu_p = round(12.0 + math.sin(self.anim_tick * 0.1) * 8.0 + random.uniform(-2.0, 3.0), 1)

            self.current_cpu_val = cpu_p
            self.cpu_history.pop(0)
            self.cpu_history.append(cpu_p)

            self.canvas.delete("cpu_line")
            step_w = self.graph_w / (len(self.cpu_history) - 1)
            points = []
            for idx, val in enumerate(self.cpu_history):
                px = self.graph_x + idx * step_w
                val_clamped = min(100.0, max(0.0, val))
                py = (self.graph_y + self.graph_h) - (val_clamped / 100.0 * (self.graph_h - 10)) - 2
                points.extend([px, py])

            if len(points) >= 4:
                self.canvas.create_line(points, fill="#FF2222", width=2, smooth=True, tags="cpu_line")

            self.canvas.itemconfig(
                self.cpu_graph_label,
                text=f"CPU_CORE_WAVEFORM: {self.current_cpu_val:4.1f}% // LOAD_MAP"
            )

        if self.anim_tick % 10 == 0:
            ping_val = random.randint(14, 25)
            now_t = time.time()
            dt = max(0.1, now_t - self.last_net_time)

            if HAS_PSUTIL:
                ram = psutil.virtual_memory()
                ram_mb = int(ram.used / (1024 * 1024))
                net = psutil.net_io_counters()

                rx_sec = (net.bytes_recv - self.last_net_bytes[0]) / dt
                tx_sec = (net.bytes_sent - self.last_net_bytes[1]) / dt
                self.last_net_bytes = (net.bytes_recv, net.bytes_sent)
                self.last_net_time = now_t

                dl_str = f"{rx_sec / 1024:.1f} KB/s" if rx_sec < 1048576 else f"{rx_sec / 1048576:.2f} MB/s"
                up_str = f"{tx_sec / 1024:.1f} KB/s" if tx_sec < 1048576 else f"{tx_sec / 1048576:.2f} MB/s"
                total_rx_mb = net.bytes_recv / (1024 * 1024)
                tot_str = f"TOTAL RX: {total_rx_mb:.1f} MB"
            else:
                ram_mb = 428 + random.randint(-5, 12)
                dl_str = f"{random.uniform(120.0, 850.0):.1f} KB/s"
                up_str = f"{random.uniform(15.0, 95.0):.1f} KB/s"
                tot_str = "TOTAL RX: 1420.5 MB"

            self.canvas.itemconfig(self.telemetry_cpu, text=f"CPU_USAGE : {self.current_cpu_val}%")
            self.canvas.itemconfig(self.telemetry_ram, text=f"RAM_ALLOC : {ram_mb} MB")
            self.canvas.itemconfig(self.telemetry_ping, text=f"NET_PING  : {ping_val} ms")

            self.canvas.itemconfig(self.net_down_lbl, text=f"DL : {dl_str}")
            self.canvas.itemconfig(self.net_up_lbl, text=f"UP : {up_str}")
            self.canvas.itemconfig(self.net_total_lbl, text=tot_str)

            matrix_lines = [
                f"{random.randint(0, 255):08b} {random.randint(0, 255):08b} {random.randint(0, 255):08b}"
                for _ in range(14)
            ]
            self.canvas.itemconfig(self.chunk_text, text="\n".join(matrix_lines))
            self.canvas.itemconfig(self.hex_id, text=f"HEX: 0x{random.randint(0x10000000, 0xFFFFFFFF):X}")

        self.after(30, self.run_terminal_loops)


if __name__ == "__main__":
    app = TenguApp()
    app.mainloop()