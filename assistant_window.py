import os
import re
import io
import time
import threading
import ctypes
import tkinter as tk
from tkinter import filedialog
import customtkinter as ctk
from PIL import Image, ImageTk
from dotenv import load_dotenv

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    HAS_MPL = True
except ImportError:
    HAS_MPL = False

try:
    myappid = "tengu.os.assistant.v4"
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
except Exception:
    pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(BASE_DIR, ".env")
if not os.path.exists(env_path):
    alt_env = os.path.join(BASE_DIR, "gemini-key.env")
    if os.path.exists(alt_env):
        env_path = alt_env

load_dotenv(env_path)

try:
    from google import genai
    from google.genai import types
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False

try:
    import speech_recognition as sr
    HAS_SR = True
except ImportError:
    HAS_SR = False

ASSETS_DIR = os.path.join(BASE_DIR, "assets")
ICO_PATH = os.path.join(ASSETS_DIR, "tengu.ico")

TENGU_SYSTEM_PROMPT = (
    "Ти — TENGU, розумний цифровий помічник операційної системи Tengu OS. "
    "Твій стиль: впевнений, лаконічний, сучасний, без штучної бюрократії. "
    "Спілкуйся природною українською мовою. "
    "Пояснюй матеріал зрозуміло звичайній людині, по кроках. "
    "ВАЖЛИВО ЩОДО ФОРМУЛ: Якщо у відповіді є математичні формули, інтеграли або дроби, "
    "виділяй їх окремим рядком у подвійних доларах: $$...$$. "
    "Наприклад: $$I = \\int_{0}^{\\pi/2} \\frac{\\sin^3(x)}{\\sin^3(x) + \\cos^3(x)} dx$$. "
    "Прості вирази пиши звичайним текстом: F = m * a, π/4. "
    "Уникай безглуздих вигуків про запуск протоколів."
)


class TenguVoiceAssistant(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("TENGU // NEURAL MULTIMODAL ASSISTANT")
        self.geometry("680x780")
        self.minsize(500, 600)
        self.resizable(True, True)
        self.configure(fg_color="#080202")

        self._apply_window_icon()

        self.is_processing = False
        self.is_listening = False
        self.attached_file_path = None
        self.last_tengu_reply = ""
        self._rendered_images = []

        self.genai_client = None
        self._init_gemini_client()

        self.build_ui()

    def _apply_window_icon(self):
        if os.path.exists(ICO_PATH):
            try:
                self.after(200, lambda: self.iconbitmap(ICO_PATH))
            except Exception:
                pass

    def _init_gemini_client(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if HAS_GENAI and api_key:
            try:
                self.genai_client = genai.Client(api_key=api_key)
            except Exception as e:
                print(f"[ERR] Gemini Client Error: {e}")
                self.genai_client = None

    def build_ui(self):
        self.hud_frame = ctk.CTkFrame(
            self,
            fg_color="#070101",
            border_color="#FF1A1A",
            border_width=1,
            corner_radius=6
        )
        self.hud_frame.pack(fill="both", expand=True, padx=14, pady=(14, 8))

        self.top_status_bar = ctk.CTkFrame(self.hud_frame, fg_color="transparent", height=32)
        self.top_status_bar.pack(fill="x", padx=12, pady=(10, 4))

        init_status = "[SYSTEM: ONLINE // READY]" if self.genai_client else "[SYSTEM: WARNING // NO API KEY]"
        status_color = "#00FF66" if self.genai_client else "#FF3333"

        self.status_label = ctk.CTkLabel(
            self.top_status_bar,
            text=init_status,
            font=("Consolas", 10, "bold"),
            text_color=status_color
        )
        self.status_label.pack(side="left")

        self.btn_copy = ctk.CTkButton(
            self.top_status_bar,
            text="[ 📋 КОПІЮВАТИ ]",
            width=110,
            height=26,
            fg_color="#180404",
            hover_color="#360808",
            border_color="#FF2222",
            border_width=1,
            font=("Consolas", 9, "bold"),
            text_color="#FFAAAA",
            command=self.copy_last_response
        )
        self.btn_copy.pack(side="right")

        self.chat_display = ctk.CTkTextbox(
            self.hud_frame,
            fg_color="#040000",
            text_color="#E0E0E0",
            font=("Consolas", 11),
            border_width=0,
            corner_radius=4,
            wrap="word",
            activate_scrollbars=True
        )
        self.chat_display.pack(fill="both", expand=True, padx=12, pady=(4, 12))
        self.chat_display.insert("end", "TENGU: Готовий до роботи. Чим можу допомогти?\n")
        self.chat_display.configure(state="disabled")

        self.bottom_container = ctk.CTkFrame(self, fg_color="transparent")
        self.bottom_container.pack(fill="x", side="bottom", padx=14, pady=(0, 14))

        self.attachment_badge = ctk.CTkFrame(
            self.bottom_container,
            fg_color="#180404",
            border_color="#FF3333",
            border_width=1,
            corner_radius=4,
            height=28
        )
        self.lbl_attachment_name = ctk.CTkLabel(
            self.attachment_badge,
            text="",
            font=("Consolas", 10, "bold"),
            text_color="#00FFFF"
        )
        self.lbl_attachment_name.pack(side="left", padx=(8, 4), pady=2)

        self.btn_remove_attachment = ctk.CTkButton(
            self.attachment_badge,
            text="✕",
            width=20,
            height=20,
            fg_color="transparent",
            hover_color="#551111",
            text_color="#FF5555",
            font=("Consolas", 11, "bold"),
            command=self.clear_attachment
        )
        self.btn_remove_attachment.pack(side="left", padx=(0, 4), pady=2)

        self.input_frame = ctk.CTkFrame(
            self.bottom_container,
            fg_color="#0A0202",
            corner_radius=6,
            border_width=1,
            border_color="#771111"
        )
        self.input_frame.pack(fill="x", pady=(4, 0))

        self.attach_btn = ctk.CTkButton(
            self.input_frame,
            text="📎",
            width=38,
            height=38,
            fg_color="#180404",
            hover_color="#360808",
            border_color="#551212",
            border_width=1,
            font=("Segoe UI Emoji", 13),
            command=self.select_file
        )
        self.attach_btn.pack(side="left", padx=(6, 4), pady=6)

        self.query_entry = ctk.CTkEntry(
            self.input_frame,
            placeholder_text="Введіть запит або прикріпіть файл...",
            fg_color="#040000",
            border_color="#551212",
            text_color="#FFFFFF",
            font=("Consolas", 12),
            height=38
        )
        self.query_entry.pack(side="left", fill="x", expand=True, padx=(0, 6), pady=6)
        self.query_entry.bind("<Return>", lambda e: self.send_text_query())

        self._bind_universal_clipboard(self.query_entry)
        self._create_entry_context_menu(self.query_entry)

        self.mic_btn = ctk.CTkButton(
            self.input_frame,
            text="🎙",
            width=38,
            height=38,
            fg_color="#1F0404",
            hover_color="#400808",
            border_color="#FF2222",
            border_width=1,
            font=("Segoe UI Emoji", 13),
            command=self.toggle_voice_input
        )
        self.mic_btn.pack(side="left", padx=(0, 6), pady=6)

        self.send_btn = ctk.CTkButton(
            self.input_frame,
            text="➤",
            width=38,
            height=38,
            fg_color="#2A0505",
            hover_color="#550A0A",
            border_color="#FF3333",
            border_width=1,
            font=("Consolas", 14, "bold"),
            command=self.send_text_query
        )
        self.send_btn.pack(side="left", padx=(0, 6), pady=6)

    def _bind_universal_clipboard(self, widget):
        def handle_key(event):
            if (event.state & 4) and event.keycode == 86:
                try:
                    clip = self.clipboard_get()
                    if clip:
                        widget.insert("insert", clip)
                    return "break"
                except Exception:
                    pass
            elif (event.state & 4) and event.keycode == 65:
                widget.select_range(0, 'end')
                widget.icursor('end')
                return "break"
        widget.bind("<Key>", handle_key, add="+")

    def _create_entry_context_menu(self, widget):
        menu = tk.Menu(self, tearoff=0, bg="#100303", fg="#FFFFFF", activebackground="#440A0A", activeforeground="#00FFFF", font=("Consolas", 9))

        def paste_action():
            try:
                clip = self.clipboard_get()
                if clip:
                    widget.insert("insert", clip)
            except Exception:
                pass

        def copy_action():
            try:
                sel = widget.selection_get()
                if sel:
                    self.clipboard_clear()
                    self.clipboard_append(sel)
            except Exception:
                pass

        def clear_action():
            widget.delete(0, "end")

        menu.add_command(label="Вставити", command=paste_action)
        menu.add_command(label="Копіювати", command=copy_action)
        menu.add_separator()
        menu.add_command(label="Очистити рядок", command=clear_action)

        def show_menu(event):
            menu.tk_popup(event.x_root, event.y_root)

        widget.bind("<Button-3>", show_menu)

    def _render_latex(self, formula_text):
        if not HAS_MPL:
            return None
        try:
            clean = formula_text.strip().replace("$$", "").strip("$").strip()
            fig = plt.figure(figsize=(0.01, 0.01))
            fig.patch.set_facecolor("#040000")

            math_expr = f"${clean}$"
            text_obj = fig.text(0, 0, math_expr, fontsize=13, color="#FFFFFF")

            fig.canvas.draw()
            bbox = text_obj.get_window_extent(fig.canvas.get_renderer())
            w, h = bbox.width / 72.0, bbox.height / 72.0
            fig.set_size_inches(max(w, 0.5), max(h, 0.25))

            buf = io.BytesIO()
            plt.savefig(buf, format="png", dpi=130, facecolor="#040000", bbox_inches="tight", pad_inches=0.04)
            plt.close(fig)
            buf.seek(0)

            img = Image.open(buf)
            tk_img = ImageTk.PhotoImage(img)
            self._rendered_images.append(tk_img)
            return tk_img
        except Exception:
            return None

    def copy_last_response(self):
        if self.last_tengu_reply:
            self.clipboard_clear()
            self.clipboard_append(self.last_tengu_reply)
            self.btn_copy.configure(text="[ ✓ СКОПІЙОВАНО ]", text_color="#00FF66")
            self.after(2000, lambda: self.btn_copy.configure(text="[ 📋 КОПІЮВАТИ ]", text_color="#FFAAAA"))

    def select_file(self):
        filetypes = [
            ("Сумісні файли", "*.png;*.jpg;*.jpeg;*.webp;*.txt;*.py;*.json;*.log;*.md"),
            ("Зображення", "*.png;*.jpg;*.jpeg;*.webp"),
            ("Текстові файли та код", "*.txt;*.py;*.json;*.log;*.md"),
            ("Всі файли", "*.*")
        ]
        path = filedialog.askopenfilename(title="Вибір файлу", filetypes=filetypes)
        if path:
            self.attached_file_path = path
            fname = os.path.basename(path)
            disp_name = fname if len(fname) < 28 else fname[:25] + "..."
            ext = os.path.splitext(fname)[1].upper()[1:] or "FILE"

            self.lbl_attachment_name.configure(text=f"[{ext}] {disp_name}")
            self.attachment_badge.pack(fill="none", side="top", anchor="w", pady=(0, 4))
            self.status_label.configure(text=f"[PAYLOAD MOUNTED: {ext}]", text_color="#00FFFF")

    def clear_attachment(self):
        self.attached_file_path = None
        self.attachment_badge.pack_forget()
        self.status_label.configure(
            text="[SYSTEM: ONLINE // READY]" if self.genai_client else "[SYSTEM: WARNING // NO API KEY]",
            text_color="#00FF66" if self.genai_client else "#FF3333"
        )

    def send_text_query(self):
        text = self.query_entry.get().strip()
        if (not text and not self.attached_file_path) or self.is_processing:
            return

        file_to_send = self.attached_file_path
        self.query_entry.delete(0, "end")
        self.clear_attachment()
        self.process_command(text, file_to_send)

    def toggle_voice_input(self):
        if self.is_listening or self.is_processing:
            return
        threading.Thread(target=self._voice_record_thread, daemon=True).start()

    def _voice_record_thread(self):
        self.is_listening = True
        self.status_label.configure(text="[VOX STREAM ACTIVE // СЛУХАЮ...]", text_color="#00FFFF")
        self.mic_btn.configure(fg_color="#881111")

        recognized_text = ""
        if HAS_SR:
            r = sr.Recognizer()
            r.dynamic_energy_threshold = False
            r.energy_threshold = 220
            r.pause_threshold = 1.3
            r.non_speaking_duration = 0.7

            try:
                with sr.Microphone() as source:
                    r.adjust_for_ambient_noise(source, duration=0.1)
                    audio = r.listen(source, timeout=8, phrase_time_limit=18)

                self.status_label.configure(text="[VOX DECODING // РОЗПІЗНАВАННЯ...]", text_color="#FFAA00")
                recognized_text = r.recognize_google(audio, language="uk-UA")
            except Exception:
                recognized_text = ""
        else:
            time.sleep(0.5)
            recognized_text = ""

        self.is_listening = False
        self.mic_btn.configure(fg_color="#1F0404")

        if recognized_text:
            file_to_send = self.attached_file_path
            self.clear_attachment()
            self.process_command(recognized_text, file_to_send)
        else:
            self.status_label.configure(text="[VOX: TIMEOUT // ГОЛОС НЕ РОЗПІЗНАНО]", text_color="#FF5555")

    def process_command(self, query, file_path=None):
        self.is_processing = True
        self.status_label.configure(text="[STREAMING UPLINK // ВСТАНОВЛЕННЯ ЗВ'ЯЗКУ...]", text_color="#FFAA00")

        user_display = query if query else "[АНАЛІЗ ФАЙЛУ]"
        if file_path:
            user_display += f"  (📎 {os.path.basename(file_path)})"

        self.chat_display.configure(state="normal")
        self.chat_display.insert("end", f"\n\nВИ: {user_display}\n\nTENGU:\n")
        self.chat_display.see("end")
        self.chat_display.configure(state="disabled")

        def _worker():
            if not self.genai_client:
                self._init_gemini_client()

            if not self.genai_client:
                self.after(0, lambda: self._on_stream_complete("ПОМИЛКА: GEMINI_API_KEY не знайдено в .env\n", is_err=True))
                return

            try:
                contents = []
                prompt_text = query if query else "Опиши або розв'яжи задачу з файлу."

                if file_path and os.path.exists(file_path):
                    ext = os.path.splitext(file_path)[1].lower()
                    if ext in [".png", ".jpg", ".jpeg", ".webp"]:
                        pil_img = Image.open(file_path)
                        contents.append(pil_img)
                        contents.append(prompt_text)
                    else:
                        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                            file_body = f.read(12000)
                        file_header = f"[ФАЙЛ: {os.path.basename(file_path)}]\n```\n{file_body}\n```\n\n{prompt_text}"
                        contents.append(file_header)
                else:
                    contents.append(prompt_text)

                fast_models = [
                    "gemini-3.5-flash-lite",
                    "gemini-3.8-flash"
                ]

                stream_started = False
                self.last_tengu_reply = ""
                last_err = None

                for model_name in fast_models:
                    try:
                        self.after(0, lambda m=model_name: self.status_label.configure(
                            text=f"[LIVE STREAM // {m.upper()}]",
                            text_color="#00E5FF"
                        ))

                        response_stream = self.genai_client.models.generate_content_stream(
                            model=model_name,
                            contents=contents,
                            config=types.GenerateContentConfig(
                                system_instruction=TENGU_SYSTEM_PROMPT,
                                temperature=0.5,
                            ),
                        )

                        for chunk in response_stream:
                            if chunk.text:
                                stream_started = True
                                self.last_tengu_reply += chunk.text
                                self.after(0, lambda t=chunk.text: self._append_stream_chunk(t))

                        if stream_started:
                            break
                    except Exception as err:
                        last_err = err
                        if stream_started:
                            break
                        continue

                if stream_started:
                    self.after(0, lambda: self._on_stream_complete(self.last_tengu_reply, is_err=False))
                else:
                    raise last_err if last_err else Exception("Шлюз моделей недоступний.")

            except Exception as e:
                err_msg = f"\nКРИТИЧНА ПОМИЛКА: {str(e)}\n"
                self.after(0, lambda: self._on_stream_complete(err_msg, is_err=True))

        threading.Thread(target=_worker, daemon=True).start()

    def _append_stream_chunk(self, chunk_text):
        self.chat_display.configure(state="normal")
        self.chat_display.insert("end", chunk_text)
        self.chat_display.see("end")
        self.chat_display.configure(state="disabled")

    def _on_stream_complete(self, full_text, is_err=False):
        self.is_processing = False

        if not is_err and HAS_MPL and "$$" in full_text:
            self._render_rich_formulas(full_text)

        self.chat_display.configure(state="normal")
        self.chat_display.insert("end", "\n")
        self.chat_display.see("end")
        self.chat_display.configure(state="disabled")

        status_text = "[NEURAL UPLINK // ВІДПОВІДЬ ЗАВЕРШЕНО]" if not is_err else "[NEURAL UPLINK // ЗБІЙ ОПЕРАЦІЇ]"
        status_color = "#00FF66" if not is_err else "#FF2222"
        self.status_label.configure(text=status_text, text_color=status_color)

    def _render_rich_formulas(self, full_text):
        raw_text_widget = self.chat_display._textbox
        self.chat_display.configure(state="normal")

        parts = re.split(r'(\$\$.*?\$\$)', full_text, flags=re.DOTALL)
        idx = self.chat_display.get("1.0", "end").rfind("TENGU:\n")
        if idx != -1:
            start_pos = f"1.0 + {idx + 7} chars"
            self.chat_display.delete(start_pos, "end")

            for p in parts:
                if p.startswith("$$") and p.endswith("$$"):
                    img = self._render_latex(p)
                    if img:
                        raw_text_widget.insert("end", "\n")
                        raw_text_widget.image_create("end", image=img)
                        raw_text_widget.insert("end", "\n")
                    else:
                        raw_text_widget.insert("end", p)
                else:
                    raw_text_widget.insert("end", p)

        self.chat_display.configure(state="disabled")