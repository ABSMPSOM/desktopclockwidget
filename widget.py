import customtkinter as ctk
import tkinter.filedialog as fd
from datetime import datetime
import json
import os
import shutil
import threading
import ctypes
import winreg
import sys

from PIL import Image, ImageDraw
import pystray

# =========================================================
# APPEARANCE
# =========================================================
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# =========================================================
# CONFIG PATHS & ERROR LOGGING
# =========================================================
CONFIG_DIR = os.path.join(os.environ.get("APPDATA"), "DesktopClockWidget")
os.makedirs(CONFIG_DIR, exist_ok=True)

SETTINGS_FILE = os.path.join(CONFIG_DIR, "widget_settings.json")
LOG_FILE = os.path.join(CONFIG_DIR, "error.log")
TRANSPARENT_COLOR = "#000001"

def log_error(error):
    """Silently logs errors to AppData for debugging."""
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now()} : {str(error)}\n")
    except:
        pass

# =========================================================
# SINGLE INSTANCE LOCK (CRASH-PROOF MUTEX)
# =========================================================
# This prevents the user from opening multiple widgets at once.
# If the app crashes, Windows automatically releases the lock.
mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "Global\\DesktopClockWidget_Mutex")
if ctypes.windll.kernel32.GetLastError() == 183: # ERROR_ALREADY_EXISTS
    sys.exit()

# =========================================================
# DEFAULT SETTINGS
# =========================================================
DEFAULT_SETTINGS = {
    "position_preset": "center",
    "manual_x": 100,
    "manual_y": 100,
    "custom_font_path": "",
    "font_day": "Century Gothic",
    "font_date": "Courier New",
    "font_time": "Courier New",
    "size_day": 45,
    "size_date": 20,
    "size_time": 18,
    "style_day": "bold",
    "style_date": "bold",
    "style_time": "normal",
    "color_day": "#1E293B",
    "color_date": "#64748B",
    "color_time": "#3B82F6",
    "pad_top": 30,
    "pad_day_date": 5,
    "pad_date_time": 5,
    "let_space_day": 1,
    "let_space_date": 0,
    "let_space_time": 0,
    "auto_start": False
}

# =========================================================
# SETTINGS WINDOW
# =========================================================
class SettingsWindow(ctk.CTkToplevel):
    def __init__(self, parent, current_settings, on_save_callback):
        super().__init__(parent)

        self.title("Widget Configuration")
        self.geometry("500x760")
        self.attributes("-topmost", True)
        self.resizable(False, False)

        self.current_settings = current_settings
        self.on_save_callback = on_save_callback
        self.font_comboboxes = []

        self.available_fonts = ["Century Gothic", "Courier New", "Arial", "Consolas", "Helvetica", "Impact"]
        for line in ["day", "date", "time"]:
            saved_font = self.current_settings.get(f"font_{line}")
            if saved_font and saved_font not in self.available_fonts:
                self.available_fonts.append(saved_font)

        self.tabview = ctk.CTkTabview(self, width=470, height=680)
        self.tabview.pack(padx=10, pady=10, fill="both", expand=True)

        self.tab_pos = self.tabview.add("Position & System")
        self.tab_vis = self.tabview.add("Visuals & Fonts")
        self.tab_space = self.tabview.add("Spacing")

        self._build_position_tab()
        self._build_visuals_tab()
        self._build_spacing_tab()

        self.save_btn = ctk.CTkButton(
            self, text="Apply & Save", command=self._save_settings,
            fg_color="#10b981", hover_color="#059669"
        )
        self.save_btn.pack(pady=(0, 10))

    def _build_position_tab(self):
        self.var_startup = ctk.BooleanVar(value=self.current_settings.get("auto_start", False))
        ctk.CTkSwitch(self.tab_pos, text="Run on Windows Startup", variable=self.var_startup).pack(pady=10, anchor="w", padx=20)
        ctk.CTkLabel(self.tab_pos, text="Screen Position", font=("Arial", 16, "bold")).pack(pady=(20, 5), anchor="w", padx=20)

        self.var_pos = ctk.StringVar(value=self.current_settings.get("position_preset", "center"))
        grid_frame = ctk.CTkFrame(self.tab_pos, fg_color="transparent")
        grid_frame.pack(pady=10)

        positions = [
            [("Top Left", "top_left"), ("Top Middle", "top_mid"), ("Top Right", "top_right")],
            [("Mid Left", "mid_left"), ("Center", "center"), ("Mid Right", "mid_right")],
            [("Bot Left", "bot_left"), ("Bot Middle", "bot_mid"), ("Bot Right", "bot_right")],
            [("Manual (Drag)", "manual"), ("", ""), ("", "")]
        ]

        for r, row in enumerate(positions):
            for c, (text, val) in enumerate(row):
                if text:
                    ctk.CTkRadioButton(grid_frame, text=text, variable=self.var_pos, value=val).grid(row=r, column=c, padx=10, pady=10, sticky="w")

    def _build_visuals_tab(self):
        self.scroll = ctk.CTkScrollableFrame(self.tab_vis, width=430, height=600, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True)

        ctk.CTkLabel(self.scroll, text="Custom Font (.ttf / .otf)", font=("Arial", 14, "bold")).pack(pady=(5, 0), anchor="w")
        font_frame = ctk.CTkFrame(self.scroll, fg_color="transparent")
        font_frame.pack(fill="x", pady=5)

        self.var_custom_font = ctk.StringVar(value=self.current_settings.get("custom_font_path", ""))
        ctk.CTkEntry(font_frame, textvariable=self.var_custom_font, width=300).pack(side="left", padx=(0, 5))
        ctk.CTkButton(font_frame, text="Browse", width=80, command=self._browse_font).pack(side="left")
        ctk.CTkLabel(self.scroll, text="Fonts are copied safely into app config folder", text_color="gray").pack(anchor="w", pady=(0, 10))

        self.font_vars = {}
        for line in ["day", "date", "time"]:
            ctk.CTkLabel(self.scroll, text=f"{line.capitalize()} Styling", font=("Arial", 14, "bold")).pack(pady=(10, 2), anchor="w")
            f = ctk.CTkFrame(self.scroll)
            f.pack(fill="x", pady=2)

            v_font = ctk.StringVar(value=self.current_settings.get(f"font_{line}", self.available_fonts[0]))
            cb = ctk.CTkComboBox(f, values=self.available_fonts, variable=v_font, width=140)
            cb.grid(row=0, column=0, padx=5, pady=5)
            self.font_comboboxes.append(cb)

            v_size = ctk.IntVar(value=self.current_settings.get(f"size_{line}", 20))
            ctk.CTkEntry(f, textvariable=v_size, width=60).grid(row=0, column=1, padx=5, pady=5)

            v_style = ctk.StringVar(value=self.current_settings.get(f"style_{line}", "normal"))
            ctk.CTkOptionMenu(f, values=["normal", "bold", "italic"], variable=v_style, width=100).grid(row=0, column=2, padx=5, pady=5)

            v_color = ctk.StringVar(value=self.current_settings.get(f"color_{line}", "#FFFFFF"))
            ctk.CTkEntry(f, textvariable=v_color, width=100).grid(row=0, column=3, padx=5, pady=5)

            self.font_vars[line] = {"font": v_font, "size": v_size, "style": v_style, "color": v_color}

    def _build_spacing_tab(self):
        s_frame = ctk.CTkScrollableFrame(self.tab_space, width=430, height=600, fg_color="transparent")
        s_frame.pack(fill="both", expand=True)

        ctk.CTkLabel(s_frame, text="Vertical Padding", font=("Arial", 16, "bold")).pack(pady=(10, 10), anchor="w")
        
        self.var_pad_top = ctk.IntVar(value=self.current_settings.get("pad_top", 30))
        ctk.CTkLabel(s_frame, text="Top Screen Buffer").pack(anchor="w")
        ctk.CTkSlider(s_frame, from_=0, to=150, variable=self.var_pad_top).pack(fill="x", pady=(0, 15))

        self.var_pad_dd = ctk.IntVar(value=self.current_settings.get("pad_day_date", 5))
        ctk.CTkLabel(s_frame, text="Space between Day & Date").pack(anchor="w")
        ctk.CTkSlider(s_frame, from_=0, to=100, variable=self.var_pad_dd).pack(fill="x", pady=(0, 15))

        self.var_pad_dt = ctk.IntVar(value=self.current_settings.get("pad_date_time", 5))
        ctk.CTkLabel(s_frame, text="Space between Date & Time").pack(anchor="w")
        ctk.CTkSlider(s_frame, from_=0, to=100, variable=self.var_pad_dt).pack(fill="x", pady=(0, 20))

        ctk.CTkLabel(s_frame, text="Letter Spacing", font=("Arial", 16, "bold")).pack(pady=(10, 10), anchor="w")
        
        self.var_let_day = ctk.IntVar(value=self.current_settings.get("let_space_day", 1))
        ctk.CTkLabel(s_frame, text="Day Letter Spacing").pack(anchor="w")
        ctk.CTkSlider(s_frame, from_=0, to=10, number_of_steps=10, variable=self.var_let_day).pack(fill="x", pady=(0, 15))

        self.var_let_date = ctk.IntVar(value=self.current_settings.get("let_space_date", 0))
        ctk.CTkLabel(s_frame, text="Date Letter Spacing").pack(anchor="w")
        ctk.CTkSlider(s_frame, from_=0, to=10, number_of_steps=10, variable=self.var_let_date).pack(fill="x", pady=(0, 15))

        self.var_let_time = ctk.IntVar(value=self.current_settings.get("let_space_time", 0))
        ctk.CTkLabel(s_frame, text="Time Letter Spacing").pack(anchor="w")
        ctk.CTkSlider(s_frame, from_=0, to=10, number_of_steps=10, variable=self.var_let_time).pack(fill="x", pady=(0, 20))

    def _browse_font(self):
        filepath = fd.askopenfilename(filetypes=[("Font Files", "*.ttf *.otf")])
        if filepath:
            filename = os.path.basename(filepath)
            safe_dest_path = os.path.join(CONFIG_DIR, filename)

            try:
                if os.path.abspath(filepath) != os.path.abspath(safe_dest_path):
                    shutil.copy2(filepath, safe_dest_path)
                self.var_custom_font.set(safe_dest_path)
            except Exception as e:
                log_error(e)

            base_name = os.path.splitext(filename)[0]
            clean_name = base_name.replace("-Regular", "").replace("-Bold", "").replace("_", " ")

            if clean_name not in self.available_fonts:
                self.available_fonts.append(clean_name)
                for cb in self.font_comboboxes:
                    cb.configure(values=self.available_fonts)

            self.font_vars["day"]["font"].set(clean_name)

    def _save_settings(self):
        new_settings = {
            "position_preset": self.var_pos.get(),
            "manual_x": self.current_settings.get("manual_x", 100),
            "manual_y": self.current_settings.get("manual_y", 100),
            "custom_font_path": self.var_custom_font.get(),
            "auto_start": self.var_startup.get(),
            "pad_top": int(self.var_pad_top.get()),
            "pad_day_date": int(self.var_pad_dd.get()),
            "pad_date_time": int(self.var_pad_dt.get()),
            "let_space_day": int(self.var_let_day.get()),
            "let_space_date": int(self.var_let_date.get()),
            "let_space_time": int(self.var_let_time.get())
        }

        for line in ["day", "date", "time"]:
            new_settings[f"font_{line}"] = self.font_vars[line]["font"].get()
            new_settings[f"size_{line}"] = int(self.font_vars[line]["size"].get())
            new_settings[f"style_{line}"] = self.font_vars[line]["style"].get()
            new_settings[f"color_{line}"] = self.font_vars[line]["color"].get()

        self.on_save_callback(new_settings)
        self.current_settings = new_settings

        self.save_btn.configure(text="Saved!", fg_color="#3b82f6")
        self.after(1500, lambda: self.save_btn.configure(text="Apply & Save", fg_color="#10b981"))

# =========================================================
# MAIN WIDGET
# =========================================================
class DesktopWidget(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.settings = self._load_settings()
        self.settings_window = None
        self.UPDATE_INTERVAL = 500

        self.open_settings_flag = False
        self.quit_flag = False

        self._handle_custom_font()
        self._setup_window()
        self._setup_ui()
        self._setup_bindings()
        self._apply_position()
        self._update_clock()
        self._setup_system_tray()
        self._poll_signals()

    def _toggle_startup(self, enable):
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_name = "DesktopClockWidget"

        # PyInstaller vs Script Check for correct registry formatting
        if getattr(sys, 'frozen', False):
            cmd = f'"{sys.executable}"'
        else:
            cmd = f'pythonw "{os.path.abspath(__file__)}"'

        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS)
            if enable:
                winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, cmd)
            else:
                try:
                    winreg.DeleteValue(key, app_name)
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
        except Exception as e:
            log_error(e)

    def _load_settings(self):
        settings = DEFAULT_SETTINGS.copy()
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    settings.update(json.load(f))
            except Exception as e:
                log_error(e)
        return settings

    def _save_settings_to_disk(self):
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=4)
            self._toggle_startup(self.settings.get("auto_start", False))
        except Exception as e:
            log_error(e)

    def _handle_custom_font(self):
        font_path = self.settings.get("custom_font_path", "")
        if font_path and os.path.exists(font_path):
            try:
                FR_PRIVATE = 0x10
                ctypes.windll.gdi32.AddFontResourceExW(font_path, FR_PRIVATE, 0)
            except Exception as e:
                log_error(e)

    def _setup_window(self):
        self.configure(fg_color=TRANSPARENT_COLOR)
        self.wm_attributes("-transparentcolor", TRANSPARENT_COLOR)
        self.overrideredirect(True)
        self.geometry("800x400")
        self.attributes("-topmost", False)
        self.after(100, self.lower)

    def _setup_ui(self):
        self.day_label = ctk.CTkLabel(self, fg_color="transparent")
        self.day_label.pack()
        self.date_label = ctk.CTkLabel(self, fg_color="transparent")
        self.date_label.pack()
        self.time_label = ctk.CTkLabel(self, fg_color="transparent")
        self.time_label.pack()
        self._apply_visuals()

    def _apply_visuals(self):
        self.day_label.pack_configure(pady=(self.settings.get("pad_top", 30), self.settings.get("pad_day_date", 5)))
        self.date_label.pack_configure(pady=(0, self.settings.get("pad_date_time", 5)))
        self.time_label.pack_configure(pady=0)

        def get_font_tuple(line):
            family = self.settings.get(f"font_{line}", "Courier New")
            size = self.settings.get(f"size_{line}", 20)
            style = self.settings.get(f"style_{line}", "normal")
            return (family, size, style)

        self.day_label.configure(font=get_font_tuple("day"), text_color=self.settings.get("color_day", "#FFFFFF"))
        self.date_label.configure(font=get_font_tuple("date"), text_color=self.settings.get("color_date", "#FFFFFF"))
        self.time_label.configure(font=get_font_tuple("time"), text_color=self.settings.get("color_time", "#FFFFFF"))

    def _apply_position(self):
        self.update_idletasks()
        w = 800
        h = 400
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        pos = self.settings.get("position_preset", "center")

        if pos == "manual":
            self.geometry(f"+{self.settings.get('manual_x', 100)}+{self.settings.get('manual_y', 100)}")
            return

        x, y = 0, 0
        if "top" in pos: y = 20
        elif "mid" in pos or pos == "center": y = (sh // 2) - (h // 2)
        elif "bot" in pos: y = sh - h - 60

        if "left" in pos: x = 20
        elif "mid" in pos or pos == "center": x = (sw // 2) - (w // 2)
        elif "right" in pos: x = sw - w - 20

        self.geometry(f"+{x}+{y}")

    def _setup_bindings(self):
        self._drag_start_x = 0
        self._drag_start_y = 0
        self.bind("<ButtonPress-1>", self._start_move)
        self.bind("<B1-Motion>", self._do_move)
        self.bind("<ButtonRelease-1>", self._stop_move)

    def _start_move(self, event):
        if self.settings.get("position_preset") != "manual": return
        self._drag_start_x = event.x
        self._drag_start_y = event.y

    def _do_move(self, event):
        if self.settings.get("position_preset") != "manual": return
        x = self.winfo_x() + (event.x - self._drag_start_x)
        y = self.winfo_y() + (event.y - self._drag_start_y)
        self.geometry(f"+{x}+{y}")

    def _stop_move(self, event):
        if self.settings.get("position_preset") != "manual": return
        self.settings["manual_x"] = self.winfo_x()
        self.settings["manual_y"] = self.winfo_y()
        self._save_settings_to_disk()

    def _setup_system_tray(self):
        try:
            icon_img = Image.new('RGB', (64, 64), color=(30, 41, 59))
            draw = ImageDraw.Draw(icon_img)
            draw.rectangle([16, 16, 48, 48], fill=(59, 130, 246))

            menu = pystray.Menu(
                pystray.MenuItem("Settings", self._tray_open_settings),
                pystray.MenuItem("Quit", self._tray_quit)
            )
            self.tray_icon = pystray.Icon("DesktopWidget", icon_img, "Desktop Clock", menu)
            threading.Thread(target=self.tray_icon.run, daemon=True).start()
        except Exception as e:
            log_error(e)

    def _tray_open_settings(self, icon, item):
        self.open_settings_flag = True

    def _tray_quit(self, icon, item):
        self.quit_flag = True

    def _poll_signals(self):
        if self.quit_flag:
            try:
                self.tray_icon.stop()
            except:
                pass
            self.destroy()
            return

        if self.open_settings_flag:
            self.open_settings_flag = False
            if self.settings_window is None or not self.settings_window.winfo_exists():
                self.settings_window = SettingsWindow(self, self.settings, self._on_settings_saved)

        self.after(200, self._poll_signals)

    def _on_settings_saved(self, new_settings):
        self.settings.update(new_settings)
        self._save_settings_to_disk()
        self._handle_custom_font()
        self._apply_visuals()
        self._apply_position()

    def _update_clock(self):
        now = datetime.now()

        space_day = " " * self.settings.get("let_space_day", 1)
        space_date = " " * self.settings.get("let_space_date", 0)
        space_time = " " * self.settings.get("let_space_time", 0)

        day_str = space_day.join(list(now.strftime("%A").upper()))
        
        raw_date = now.strftime("%B %d, %Y").upper()
        date_str = space_date.join(list(raw_date)) if self.settings.get("let_space_date", 0) > 0 else raw_date

        raw_time = now.strftime("- %I:%M:%S %p -")
        time_str = space_time.join(list(raw_time)) if self.settings.get("let_space_time", 0) > 0 else raw_time

        self.day_label.configure(text=day_str)
        self.date_label.configure(text=date_str)
        self.time_label.configure(text=time_str)

        self.after(self.UPDATE_INTERVAL, self._update_clock)

# =========================================================
# START APP
# =========================================================
if __name__ == "__main__":
    app = DesktopWidget()
    app.mainloop()