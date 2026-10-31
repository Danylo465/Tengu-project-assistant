import os
import sys
import ctypes
from PIL import Image, ImageDraw
import win32com.client

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
PNG_ICON = os.path.join(ASSETS_DIR, "app_icon.png")
ICO_PATH = os.path.join(ASSETS_DIR, "tengu.ico")

if not os.path.exists(PNG_ICON):
    print(f"[ERROR] Не знайдено: {PNG_ICON}")
    sys.exit(1)

# Квадратний кроп по центру
img = Image.open(PNG_ICON).convert("RGBA")
w, h = img.size
min_dim = min(w, h)
left = (w - min_dim) // 2
top = (h - min_dim) // 2
img = img.crop((left, top, left + min_dim, top + min_dim))
size = (256, 256)
img = img.resize(size, Image.Resampling.LANCZOS)

# Заокруглення кутів (радіус 48px на 256x256)
radius = 48
mask = Image.new("L", size, 0)
draw = ImageDraw.Draw(mask)
draw.rounded_rectangle([(0, 0), size], radius=radius, fill=255)

rounded_img = Image.new("RGBA", size, (0, 0, 0, 0))
rounded_img.paste(img, (0, 0), mask=mask)

rounded_img.save(
    ICO_PATH,
    format="ICO",
    sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
)
print("[OK] tengu.ico створено із закругленими кутами.")

# Оновлення ярлика
shell = win32com.client.Dispatch("WScript.Shell")
desktop = shell.SpecialFolders("Desktop")
shortcut_path = os.path.join(desktop, "Tengu Assistant.lnk")

shortcut = shell.CreateShortCut(shortcut_path)
pythonw_exe = sys.executable.replace("python.exe", "pythonw.exe")
shortcut.Targetpath = pythonw_exe
shortcut.Arguments = f'"{os.path.join(BASE_DIR, "gui_app.py")}"'
shortcut.WorkingDirectory = BASE_DIR
shortcut.IconLocation = f"{ICO_PATH},0"
shortcut.save()

# Оновлення кешу
try:
    ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x0000, None, None)
except Exception:
    pass