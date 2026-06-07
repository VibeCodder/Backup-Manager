"""
BackupFlow - Backup Manager
Application for managing backups across multiple external drives
"""

import os
import sys
import shutil
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import subprocess
import platform
from pathlib import Path
import time
from datetime import datetime
import json

# ── Try to import tkinterdnd2 (real DnD from Explorer) ──────────────────────
# Auto-install if missing so user doesn't need to do anything manually.
DND_AVAILABLE = False
try:
    import tkinterdnd2 as _dnd_mod
    DND_AVAILABLE = True
except ImportError:
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "tkinterdnd2", "--quiet"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        import tkinterdnd2 as _dnd_mod
        DND_AVAILABLE = True
    except Exception:
        _dnd_mod = None

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".backup_manager_config.json")

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"drives": ["", "", "", ""], "source_path": str(Path.home()), "window_positions": {}}

def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

# ─────────────────────────────────────────────
# COLORS & STYLE
# ─────────────────────────────────────────────
BG          = "#0f1117"
BG2         = "#181c27"
BG3         = "#1e2333"
ACCENT      = "#3b82f6"
ACCENT2     = "#60a5fa"
GREEN       = "#22c55e"
RED         = "#ef4444"
ORANGE      = "#f59e0b"
TEXT        = "#e2e8f0"
TEXT_DIM    = "#64748b"
BORDER      = "#2d3748"
FONT_MAIN   = ("Segoe UI", 10)
FONT_BOLD   = ("Segoe UI", 10, "bold")
FONT_TITLE  = ("Segoe UI", 13, "bold")
FONT_SMALL  = ("Segoe UI", 8)
FONT_MONO   = ("Consolas", 9)


# ─────────────────────────────────────────────
# DARK TITLE BAR (Windows 10/11 only)
# ─────────────────────────────────────────────
def apply_dark_titlebar(window):
    """Apply dark title bar on Windows 10/11 via DWM API."""
    if platform.system() != "Windows":
        return
    try:
        import ctypes
        HWND = ctypes.windll.user32.GetParent(window.winfo_id())
        if not HWND:
            HWND = window.winfo_id()
        # DWMWA_USE_IMMERSIVE_DARK_MODE = 20 (Win11) or 19 (Win10 older builds)
        for attr in (20, 19):
            try:
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    HWND, attr,
                    ctypes.byref(ctypes.c_int(1)),
                    ctypes.sizeof(ctypes.c_int)
                )
            except Exception:
                pass
    except Exception:
        pass


# ─────────────────────────────────────────────
# UTILITIES
# ─────────────────────────────────────────────
def format_size(size_bytes):
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"

def get_drive_info(path):
    try:
        total, used, free = shutil.disk_usage(path)
        return total, used, free
    except:
        return None, None, None

def open_path_in_explorer(path):
    if os.path.exists(path):
        if platform.system() == "Windows":
            os.startfile(path)
        elif platform.system() == "Darwin":
            subprocess.run(["open", path])
        else:
            subprocess.run(["xdg-open", path])

def get_item_icon(path):
    if os.path.isdir(path):
        return "📁"
    ext = Path(path).suffix.lower()
    icons = {
        ".exe": "⚙️", ".msi": "📦", ".zip": "🗜️", ".rar": "🗜️", ".7z": "🗜️",
        ".pdf": "📄", ".doc": "📝", ".docx": "📝", ".xls": "📊", ".xlsx": "📊",
        ".jpg": "🖼️", ".jpeg": "🖼️", ".png": "🖼️", ".gif": "🖼️", ".bmp": "🖼️",
        ".mp3": "🎵", ".wav": "🎵", ".flac": "🎵", ".mp4": "🎬", ".avi": "🎬",
        ".mkv": "🎬", ".py": "🐍", ".js": "📜", ".html": "🌐", ".css": "🎨",
        ".txt": "📃", ".log": "📃", ".iso": "💿", ".img": "💿",
        ".bat": "⚡", ".sh": "⚡", ".ps1": "⚡",
    }
    return icons.get(ext, "📄")


# ─────────────────────────────────────────────
# STYLED WIDGET HELPERS
# ─────────────────────────────────────────────
def styled_frame(parent, **kwargs):
    kw = dict(bg=BG2, bd=0, highlightthickness=1,
               highlightbackground=BORDER, highlightcolor=ACCENT)
    kw.update(kwargs)
    return tk.Frame(parent, **kw)

def styled_label(parent, text="", font=FONT_MAIN, fg=TEXT, bg=BG2, **kwargs):
    return tk.Label(parent, text=text, font=font, fg=fg, bg=bg, **kwargs)

def styled_button(parent, text, command, color=ACCENT, width=None):
    btn = tk.Button(
        parent, text=text, command=command,
        bg=color, fg=TEXT, font=FONT_BOLD,
        relief="flat", bd=0, padx=12, pady=6,
        activebackground=ACCENT2, activeforeground=TEXT,
        cursor="hand2"
    )
    if width:
        btn.config(width=width)
    return btn


# ─────────────────────────────────────────────
# FILE TREE WIDGET (reused in multiple panels)
# ─────────────────────────────────────────────
class FileTree(tk.Frame):
    def __init__(self, parent, root_path="", on_select=None, readonly=False, **kwargs):
        super().__init__(parent, bg=BG2, **kwargs)
        self.root_path = root_path
        self.on_select_cb = on_select
        self.readonly = readonly
        self._build()
        if root_path and os.path.exists(root_path):
            self.load(root_path)

    def _build(self):
        # Toolbar
        toolbar = tk.Frame(self, bg=BG3, pady=4)
        toolbar.pack(fill="x", side="top")

        # Back button = go up one folder level
        self.btn_back = tk.Button(toolbar, text="◀", command=self.go_up,
                  bg=BG3, fg=TEXT_DIM, font=FONT_BOLD, relief="flat", bd=0,
                  padx=7, cursor="hand2")
        self.btn_back.pack(side="left", padx=(4, 2))

        self.path_var = tk.StringVar()
        path_entry = tk.Entry(toolbar, textvariable=self.path_var, font=FONT_MONO,
                              bg=BG, fg=TEXT_DIM, insertbackground=TEXT,
                              relief="flat", bd=4)
        path_entry.pack(side="left", fill="x", expand=True, padx=(6, 4))
        path_entry.bind("<Return>", lambda e: self.load(self.path_var.get()))

        tk.Button(toolbar, text="▶", command=lambda: self.load(self.path_var.get()),
                  bg=ACCENT, fg=TEXT, font=FONT_BOLD, relief="flat", bd=0,
                  padx=8, cursor="hand2").pack(side="left", padx=(0, 4))
        tk.Button(toolbar, text="⬆", command=self.go_up,
                  bg=BG3, fg=TEXT_DIM, font=FONT_BOLD, relief="flat", bd=0,
                  padx=8, cursor="hand2").pack(side="left", padx=(0, 4))
        tk.Button(toolbar, text="🔄", command=self.refresh,
                  bg=BG3, fg=TEXT_DIM, font=FONT_BOLD, relief="flat", bd=0,
                  padx=8, cursor="hand2").pack(side="left", padx=(0, 6))

        # Treeview
        cols = ("size", "modified")
        self.tree = ttk.Treeview(self, columns=cols, show="tree headings",
                                  selectmode="extended")
        self.tree.heading("#0", text="Name", anchor="w")
        self.tree.heading("size", text="Size", anchor="e")
        self.tree.heading("modified", text="Modified", anchor="w")
        self.tree.column("#0", width=260, minwidth=120)
        self.tree.column("size", width=80, minwidth=60, anchor="e")
        self.tree.column("modified", width=130, minwidth=100)

        self._style_tree()

        vsb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self.tree.bind("<Double-1>", self._on_double_click)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        # Mouse back/forward buttons — Back = go up one folder level
        for widget in (self.tree, self):
            try:
                widget.bind("<XButton1>", lambda e: self.go_up())
                widget.bind("<XButton2>", lambda e: self.go_up())
            except Exception:
                pass

        # Drag & drop support (Windows)
        self._setup_dnd()

    def _style_tree(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview",
                         background=BG2, foreground=TEXT,
                         fieldbackground=BG2, rowheight=22,
                         font=FONT_MAIN, borderwidth=0)
        style.configure("Treeview.Heading",
                         background=BG3, foreground=TEXT_DIM,
                         font=FONT_BOLD, relief="flat", padding=(4, 4))
        style.map("Treeview",
                   background=[("selected", ACCENT)],
                   foreground=[("selected", TEXT)])
        SCROLL_BG = "#3a3f4b"   # gray thumb
        SCROLL_TR  = "#1e2333"   # dark trough
        SCROLL_ARR = "#64748b"   # dim arrow
        style.configure("Vertical.TScrollbar",
                         background=SCROLL_BG, troughcolor=SCROLL_TR,
                         arrowcolor=SCROLL_ARR, bordercolor=SCROLL_TR,
                         lightcolor=SCROLL_BG, darkcolor=SCROLL_BG,
                         relief="flat", arrowsize=12)
        style.configure("Horizontal.TScrollbar",
                         background=SCROLL_BG, troughcolor=SCROLL_TR,
                         arrowcolor=SCROLL_ARR, bordercolor=SCROLL_TR,
                         lightcolor=SCROLL_BG, darkcolor=SCROLL_BG,
                         relief="flat", arrowsize=12)
        style.configure("TScrollbar",
                         background=SCROLL_BG, troughcolor=SCROLL_TR,
                         arrowcolor=SCROLL_ARR, bordercolor=SCROLL_TR,
                         lightcolor=SCROLL_BG, darkcolor=SCROLL_BG,
                         relief="flat", arrowsize=12)
        style.map("TScrollbar",
                   background=[("active", "#4f5668"), ("pressed", "#5a6275")])
        style.map("Vertical.TScrollbar",
                   background=[("active", "#4f5668"), ("pressed", "#5a6275")])
        style.map("Horizontal.TScrollbar",
                   background=[("active", "#4f5668"), ("pressed", "#5a6275")])
        style.configure("Horizontal.TProgressbar",
                         troughcolor=BG3, background=ACCENT2,
                         bordercolor=BG3, lightcolor=ACCENT2, darkcolor=ACCENT2)
        style.configure("TProgressbar",
                         troughcolor=BG3, background=ACCENT2,
                         bordercolor=BG3, lightcolor=ACCENT2, darkcolor=ACCENT2)
        style.configure("TEntry",
                         fieldbackground=BG, foreground=TEXT,
                         insertcolor=TEXT, bordercolor=BORDER,
                         lightcolor=BG, darkcolor=BG)

    def _setup_dnd(self):
        """Enable drag and drop via tkinterdnd2 if available, fallback gracefully."""
        self.tree.bind("<ButtonPress-1>", self._drag_start)
        self.tree.bind("<B1-Motion>", self._drag_motion)
        self.tree.bind("<ButtonRelease-1>", self._drag_end)
        self._drag_data = {"item": None, "x": 0, "y": 0, "dragging": False}

    def _drag_start(self, event):
        item = self.tree.identify_row(event.y)
        self._drag_data["item"] = item
        self._drag_data["x"] = event.x
        self._drag_data["y"] = event.y
        self._drag_data["dragging"] = False

    def _drag_motion(self, event):
        dx = abs(event.x - self._drag_data["x"])
        dy = abs(event.y - self._drag_data["y"])
        if dx > 5 or dy > 5:
            self._drag_data["dragging"] = True

    def _drag_end(self, event):
        self._drag_data["dragging"] = False

    def load(self, path, _from_history=False):
        if not path or not os.path.exists(path):
            return
        self.root_path = path
        self.path_var.set(path)
        self.tree.delete(*self.tree.get_children())
        try:
            items = sorted(os.scandir(path), key=lambda e: (not e.is_dir(), e.name.lower()))
        except PermissionError:
            return
        for entry in items:
            icon = get_item_icon(entry.path)
            try:
                stat = entry.stat()
                size = format_size(stat.st_size) if entry.is_file() else ""
                mtime = datetime.fromtimestamp(stat.st_mtime).strftime("%d.%m.%y %H:%M")
            except:
                size, mtime = "", ""
            iid = self.tree.insert("", "end", text=f"  {icon}  {entry.name}",
                                    values=(size, mtime),
                                    tags=("dir" if entry.is_dir() else "file",))
            self.tree._item_paths = getattr(self.tree, "_item_paths", {})
            self.tree._item_paths[iid] = entry.path

    def go_up(self):
        parent = str(Path(self.root_path).parent)
        if parent != self.root_path:
            self.load(parent)

    def refresh(self):
        self.load(self.root_path)

    def _on_double_click(self, event):
        item = self.tree.focus()
        path = getattr(self.tree, "_item_paths", {}).get(item)
        if path and os.path.isdir(path):
            self.load(path)

    def _on_select(self, event):
        if self.on_select_cb:
            items = self.tree.selection()
            paths = [getattr(self.tree, "_item_paths", {}).get(i) for i in items]
            self.on_select_cb([p for p in paths if p])

    def get_selected_paths(self):
        items = self.tree.selection()
        return [getattr(self.tree, "_item_paths", {}).get(i) for i in items
                if getattr(self.tree, "_item_paths", {}).get(i)]


# ─────────────────────────────────────────────
# DRIVE PANEL (one of 4 external drives)
# ─────────────────────────────────────────────
class DrivePanel(tk.Frame):
    def __init__(self, parent, drive_index, config, **kwargs):
        super().__init__(parent, bg=BG, **kwargs)
        self.drive_index = drive_index
        self.config = config
        self.drive_path = config["drives"][drive_index] if config["drives"][drive_index] else ""
        # root = the base path configured for this drive (e.g. E:\Kopie zapasowe)
        # relative_subpath = subfolder navigated into, relative to root (e.g. Dokumenty\Inne)
        self.relative_subpath = ""
        self._build()

    def _build(self):
        # Header
        header = tk.Frame(self, bg=BG3, pady=6)
        header.pack(fill="x")

        dot_color = GREEN if (self.drive_path and os.path.exists(self.drive_path)) else RED
        tk.Label(header, text="●", font=("Segoe UI", 14), fg=dot_color,
                 bg=BG3).pack(side="left", padx=(8, 4))

        self.title_var = tk.StringVar(value=f"Drive {self.drive_index + 1}")
        title_lbl = tk.Label(header, textvariable=self.title_var,
                              font=FONT_TITLE, fg=TEXT, bg=BG3)
        title_lbl.pack(side="left")

        tk.Button(header, text="📂 Select", command=self.choose_drive,
                  bg=ACCENT, fg=TEXT, font=FONT_SMALL, relief="flat",
                  padx=6, pady=2, cursor="hand2").pack(side="right", padx=8)

        # Drive info bar
        self.info_frame = tk.Frame(self, bg=BG2, pady=4)
        self.info_frame.pack(fill="x", padx=4, pady=(2, 0))
        self.info_label = tk.Label(self.info_frame, text="— no drive —",
                                    font=FONT_SMALL, fg=TEXT_DIM, bg=BG2)
        self.info_label.pack(side="left", padx=6)

        self.progress = ttk.Progressbar(self.info_frame, length=100, mode="determinate",
                                         style="Drive.Horizontal.TProgressbar")
        self.progress.pack(side="right", padx=(0, 6))
        style = ttk.Style()
        style.configure("Drive.Horizontal.TProgressbar",
                         troughcolor=BG3, background=ACCENT2, thickness=8)

        # File tree
        self.file_tree = FileTree(self, root_path=self.drive_path, readonly=True)
        self.file_tree.pack(fill="both", expand=True, padx=4, pady=4)

        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        self.status_bar = tk.Label(self, textvariable=self.status_var,
                                    font=FONT_SMALL, fg=TEXT_DIM, bg=BG3,
                                    anchor="w", padx=6)
        self.status_bar.pack(fill="x", side="bottom")

        self._update_info()

    def choose_drive(self):
        path = filedialog.askdirectory(title=f"Select root folder for Drive {self.drive_index + 1}")
        if path:
            self.set_drive(path)

    def set_drive(self, path):
        self.drive_path = path
        self.relative_subpath = ""
        self.config["drives"][self.drive_index] = path
        save_config(self.config)
        self.file_tree.load(path)
        self._update_info()

    def navigate_to_relative(self, rel_subpath):
        """Navigate this panel to drive_root / rel_subpath. Called by ControlPanel."""
        if not self.drive_path or not os.path.exists(self.drive_path):
            return
        self.relative_subpath = rel_subpath
        if rel_subpath:
            target = os.path.join(self.drive_path, rel_subpath)
        else:
            target = self.drive_path
        if os.path.exists(target):
            self.file_tree.load(target)
            self.set_status(f"📂 {rel_subpath or '(root)'}", ACCENT2)
        else:
            self.set_status(f"✘ missing: {rel_subpath}", RED)

    def _update_info(self):
        if self.drive_path and os.path.exists(self.drive_path):
            total, used, free = get_drive_info(self.drive_path)
            if total:
                pct = (used / total) * 100
                self.progress["value"] = pct
                self.info_label.config(
                    text=f"Free: {format_size(free)}  |  Used: {format_size(used)}  |  Total: {format_size(total)}",
                    fg=TEXT
                )
                short = os.path.splitdrive(self.drive_path)[0] or self.drive_path[:20]
                self.title_var.set(f"Drive {self.drive_index + 1}  ({short})")
        else:
            self.info_label.config(text="— no drive —", fg=TEXT_DIM)
            self.progress["value"] = 0

    def refresh(self):
        self._update_info()
        self.file_tree.refresh()

    def set_status(self, msg, color=TEXT_DIM):
        self.status_var.set(msg)
        self.status_bar.config(fg=color)


# ─────────────────────────────────────────────
# COPY LOG WIDGET
# ─────────────────────────────────────────────
class CopyLog(tk.Frame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=BG2, **kwargs)
        self._build()

    def _build(self):
        tk.Label(self, text="OPERATION LOG", font=FONT_BOLD, fg=TEXT_DIM,
                 bg=BG2, padx=8).pack(anchor="w", pady=(6, 2))
        self.text = tk.Text(self, bg=BG, fg=TEXT, font=FONT_MONO,
                             relief="flat", bd=4, state="disabled", height=8,
                             wrap="none")
        vsb = ttk.Scrollbar(self, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=vsb.set)
        self.text.pack(side="left", fill="both", expand=True, padx=(6, 0), pady=4)
        vsb.pack(side="right", fill="y", pady=4)
        self.text.tag_config("ok", foreground=GREEN)
        self.text.tag_config("err", foreground=RED)
        self.text.tag_config("info", foreground=ACCENT2)
        self.text.tag_config("warn", foreground=ORANGE)

    def log(self, msg, tag="info"):
        self.text.config(state="normal")
        ts = datetime.now().strftime("%H:%M:%S")
        self.text.insert("end", f"[{ts}] {msg}\n", tag)
        self.text.see("end")
        self.text.config(state="disabled")

    def clear(self):
        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        self.text.config(state="disabled")


# ─────────────────────────────────────────────
# CONTROL PANEL WINDOW
# ─────────────────────────────────────────────
class ControlPanel(tk.Toplevel):
    def __init__(self, parent, config, drive_panels, **kwargs):
        super().__init__(parent, **kwargs)
        self.config = config
        self.drive_panels = drive_panels
        self.title("BackupFlow – Control Panel")
        self.configure(bg=BG)
        self.geometry("960x760")
        self.minsize(760, 500)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.update_idletasks()
        apply_dark_titlebar(self)
        self._copying = False
        # Favorites: list of {"name": str, "path": str}
        if "favorites" not in self.config:
            self.config["favorites"] = []
        self._selected_paths = []
        self._build()
        self._load_source()

    # ══════════════════════════════════════════
    # BUILD
    # ══════════════════════════════════════════
    def _build(self):
        # ── Top bar ──────────────────────────
        top = tk.Frame(self, bg=BG3, pady=8, padx=12)
        top.pack(fill="x")
        tk.Label(top, text="⌨  CONTROL PANEL", font=FONT_TITLE,
                 fg=ACCENT2, bg=BG3).pack(side="left")
        tk.Button(top, text="🔄 Refresh Drives", command=self._refresh_drives,
                  bg=BG2, fg=TEXT_DIM, font=FONT_SMALL, relief="flat",
                  padx=8, pady=4, cursor="hand2").pack(side="right", padx=4)
        tk.Button(top, text="⏏  Safely Eject All", command=self._eject_all_drives,
                  bg="#7c3aed", fg=TEXT, font=FONT_SMALL, relief="flat",
                  padx=10, pady=4, cursor="hand2").pack(side="right", padx=(4, 8))

        # ── Source selector bar ───────────────
        src_frame = tk.Frame(self, bg=BG2, pady=5, padx=8)
        src_frame.pack(fill="x", padx=6, pady=(6, 0))

        tk.Label(src_frame, text="SOURCE:", font=FONT_BOLD, fg=TEXT_DIM,
                 bg=BG2).pack(side="left", padx=(0, 6))

        # Radio: Custom path  |  Drive 1..4
        self.src_mode = tk.StringVar(value="custom")
        rb_custom = tk.Radiobutton(src_frame, text="Custom path",
                                    variable=self.src_mode, value="custom",
                                    command=self._on_src_mode_change,
                                    bg=BG2, fg=TEXT, selectcolor=BG2,
                                    activebackground=BG2, activeforeground=TEXT,
                                    font=FONT_SMALL, cursor="hand2",
                                    relief="flat", bd=0)
        rb_custom.pack(side="left", padx=(0, 4))

        self.drive_rbs = []
        for i in range(4):
            drv = self.config["drives"][i]
            lbl = os.path.splitdrive(drv)[0] if drv else f"Drive {i+1}"
            rb = tk.Radiobutton(src_frame, text=lbl,
                                 variable=self.src_mode, value=f"drive{i}",
                                 command=self._on_src_mode_change,
                                 bg=BG2, fg=TEXT_DIM, selectcolor=BG2,
                                 activebackground=BG2, activeforeground=TEXT,
                                 font=FONT_SMALL, cursor="hand2",
                                 relief="flat", bd=0)
            rb.pack(side="left", padx=2)
            self.drive_rbs.append(rb)

        # Custom path entry row
        path_row = tk.Frame(self, bg=BG2, pady=3, padx=8)
        path_row.pack(fill="x", padx=6)
        self.src_var = tk.StringVar(value=self.config.get("source_path", str(Path.home())))
        self.src_entry = tk.Entry(path_row, textvariable=self.src_var, font=FONT_MONO,
                                   bg=BG, fg=TEXT, insertbackground=TEXT,
                                   relief="flat", bd=4)
        self.src_entry.pack(side="left", fill="x", expand=True)
        tk.Button(path_row, text="📂", command=self._choose_source,
                  bg=ACCENT, fg=TEXT, font=FONT_BOLD, relief="flat", padx=6,
                  cursor="hand2").pack(side="left", padx=4)
        tk.Button(path_row, text="▶", command=self._go_source,
                  bg=BG3, fg=TEXT_DIM, font=FONT_BOLD, relief="flat", padx=6,
                  cursor="hand2").pack(side="left")

        # ── Relative path / sync indicator ───
        rel_frame = tk.Frame(self, bg=BG, pady=2, padx=8)
        rel_frame.pack(fill="x", padx=6)
        tk.Label(rel_frame, text="Subfolder:", font=FONT_SMALL,
                 fg=TEXT_DIM, bg=BG).pack(side="left")
        self.rel_path_var = tk.StringVar(value="(root folder)")
        tk.Label(rel_frame, textvariable=self.rel_path_var,
                  font=FONT_MONO, fg=ACCENT2, bg=BG).pack(side="left", padx=6)
        tk.Label(rel_frame, text="← drives follow this folder",
                  font=FONT_SMALL, fg=TEXT_DIM, bg=BG).pack(side="left")
        tk.Button(rel_frame, text="⬆ to root", command=self._go_to_root,
                  bg=BG2, fg=TEXT_DIM, font=FONT_SMALL, relief="flat",
                  padx=6, cursor="hand2").pack(side="right")

        # ── Main body: favorites sidebar + file tree ──
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=6, pady=4)

        # LEFT: favorites panel
        self._build_favorites(body)

        # RIGHT: file tree
        right = tk.Frame(body, bg=BG)
        right.pack(side="left", fill="both", expand=True)

        tree_frame = styled_frame(right)
        tree_frame.pack(fill="both", expand=True)
        self.source_tree = FileTree(tree_frame,
                                     root_path=self.src_var.get(),
                                     on_select=self._on_source_select)
        self.source_tree.tree.bind("<Double-1>", self._on_source_navigate, add="+")
        self._orig_go_up = self.source_tree.go_up
        self.source_tree.go_up = self._go_up_synced
        self._patch_source_tree_toolbar()
        self.source_tree.pack(fill="both", expand=True)

        # Drop queue panel (replaces old tiny drop bar)
        self._build_drop_queue(right)

        # ── Destination checkboxes ────────────
        dest_frame = tk.Frame(self, bg=BG2, pady=5, padx=12)
        dest_frame.pack(fill="x", padx=6, pady=(2, 0))
        tk.Label(dest_frame, text="COPY TO:", font=FONT_BOLD, fg=TEXT_DIM,
                 bg=BG2).pack(side="left", padx=(0, 10))
        self.dest_vars = []
        self.dest_cbs  = []
        for i in range(4):
            var = tk.BooleanVar(value=True)
            self.dest_vars.append(var)
            drv = self.config["drives"][i]
            label = os.path.splitdrive(drv)[0] if drv else f"Drive {i+1}"
            cb = tk.Checkbutton(dest_frame, text=label, variable=var,
                                 bg=BG2, fg=TEXT, selectcolor=BG2,
                                 activebackground=BG2, activeforeground=TEXT,
                                 font=FONT_MAIN, cursor="hand2",
                                 relief="flat", bd=0)
            cb.pack(side="left", padx=6)
            self.dest_cbs.append(cb)

        # ── Action buttons ────────────────────
        btn_frame = tk.Frame(self, bg=BG, pady=5)
        btn_frame.pack(fill="x", padx=6)
        self.copy_btn = styled_button(btn_frame, "📋  COPY SELECTED",
                                       self._copy_selected, GREEN)
        self.copy_btn.pack(side="left", padx=(0, 6))
        styled_button(btn_frame, "🗑  DELETE from drives",
                      self._delete_selected, RED).pack(side="left", padx=(0, 6))
        styled_button(btn_frame, "🔄 SYNC folder",
                      self._sync_all, ORANGE).pack(side="left", padx=(0, 6))
        self.progress_var = tk.DoubleVar()
        self.prog_bar = ttk.Progressbar(btn_frame, variable=self.progress_var,
                                         maximum=100, length=150, mode="determinate")
        self.prog_bar.pack(side="right", padx=6)

        # ── Log ──────────────────────────────
        self.log = CopyLog(self)
        self.log.pack(fill="x", padx=6, pady=(0, 4))
        self.log.log("Control panel started. Navigate folders – drives will follow.", "info")

    # ══════════════════════════════════════════
    # FAVORITES PANEL
    # ══════════════════════════════════════════
    def _build_favorites(self, parent):
        fav_frame = tk.Frame(parent, bg=BG2, width=190)
        fav_frame.pack(side="left", fill="y", padx=(0, 6))
        fav_frame.pack_propagate(False)

        # Header
        hdr = tk.Frame(fav_frame, bg=BG3, pady=5)
        hdr.pack(fill="x")
        tk.Label(hdr, text="★  FAVORITES", font=FONT_BOLD,
                 fg=ORANGE, bg=BG3).pack(side="left", padx=8)
        tk.Button(hdr, text="+", command=self._fav_add_current,
                  bg=ORANGE, fg=BG, font=FONT_BOLD, relief="flat",
                  padx=6, cursor="hand2").pack(side="right", padx=4)

        # List
        list_frame = tk.Frame(fav_frame, bg=BG2)
        list_frame.pack(fill="both", expand=True)

        vsb = ttk.Scrollbar(list_frame, orient="vertical")
        self.fav_listbox = tk.Listbox(
            list_frame, bg=BG2, fg=TEXT, font=FONT_SMALL,
            selectbackground=ACCENT, selectforeground=TEXT,
            relief="flat", bd=0, highlightthickness=0,
            yscrollcommand=vsb.set, activestyle="none"
        )
        vsb.config(command=self.fav_listbox.yview)
        self.fav_listbox.pack(side="left", fill="both", expand=True, padx=(4, 0))
        vsb.pack(side="right", fill="y")

        self.fav_listbox.bind("<Double-1>", self._fav_open)
        self.fav_listbox.bind("<Button-3>", self._fav_context_menu)

        # Bottom buttons
        btn_row = tk.Frame(fav_frame, bg=BG2, pady=3)
        btn_row.pack(fill="x")
        tk.Button(btn_row, text="★ Add current", command=self._fav_add_current,
                  bg=BG3, fg=ORANGE, font=FONT_SMALL, relief="flat",
                  cursor="hand2", padx=4).pack(fill="x", padx=4, pady=1)
        tk.Button(btn_row, text="✎ Rename", command=self._fav_rename,
                  bg=BG3, fg=TEXT_DIM, font=FONT_SMALL, relief="flat",
                  cursor="hand2", padx=4).pack(fill="x", padx=4, pady=1)
        tk.Button(btn_row, text="✕ Remove selected", command=self._fav_remove,
                  bg=BG3, fg=RED, font=FONT_SMALL, relief="flat",
                  cursor="hand2", padx=4).pack(fill="x", padx=4, pady=1)

        self._refresh_fav_list()

    def _refresh_fav_list(self):
        self.fav_listbox.delete(0, "end")
        for fav in self.config["favorites"]:
            exists = os.path.exists(fav["path"])
            icon = "📁" if exists else "✘"
            self.fav_listbox.insert("end", f" {icon}  {fav['name']}")
            self.fav_listbox.itemconfig("end", fg=TEXT if exists else RED)

    def _fav_add_current(self):
        path = self.source_tree.root_path
        if not path or not os.path.exists(path):
            messagebox.showwarning("Favorites", "No active folder to add.")
            return
        for fav in self.config["favorites"]:
            if fav["path"] == path:
                messagebox.showinfo("Favorites", f"This folder is already in favorites:\n{fav['name']}")
                return
        name = self._ask_name("Favorite name", os.path.basename(path) or path)
        if name is None:
            return
        self.config["favorites"].append({
            "name": name,
            "path": path,
            "src_mode": self.src_mode.get()   # remember which drive/mode was active
        })
        save_config(self.config)
        self._refresh_fav_list()
        self.log.log(f"★ Added to favorites: {name}", "info")

    def _fav_open(self, event=None):
        sel = self.fav_listbox.curselection()
        if not sel:
            return
        fav = self.config["favorites"][sel[0]]
        if not os.path.exists(fav["path"]):
            messagebox.showerror("Favorites", f"Folder does not exist:\n{fav['path']}")
            return

        fav_path = fav["path"]
        fav_path_norm = os.path.normcase(fav_path)

        # ── Auto-detect which drive this path belongs to ──────────────────
        # Even if src_mode was not saved (old favorites), we detect it
        # by checking if the path starts with any of the 4 drive roots.
        detected_mode = fav.get("src_mode", None)
        detected_drive_root = None

        if detected_mode is None or detected_mode == "custom":
            # Try to match against configured drives
            for i, drv in enumerate(self.config["drives"]):
                if drv and os.path.exists(drv):
                    drv_norm = os.path.normcase(drv)
                    if fav_path_norm.startswith(drv_norm):
                        detected_mode = f"drive{i}"
                        detected_drive_root = drv
                        # Update saved mode so next time it's correct
                        fav["src_mode"] = detected_mode
                        save_config(self.config)
                        break
            else:
                detected_mode = "custom"

        # ── Apply the detected/saved mode ─────────────────────────────────
        self.src_mode.set(detected_mode)

        if detected_mode == "custom":
            self.src_entry.config(state="normal", fg=TEXT)
            self.src_var.set(fav_path)
            self.source_tree.load(fav_path)
        else:
            idx = int(detected_mode.replace("drive", ""))
            drive_root = detected_drive_root or self.config["drives"][idx]
            if not drive_root or not os.path.exists(drive_root):
                # Drive gone — fall back to custom
                self.src_mode.set("custom")
                self.src_entry.config(state="normal", fg=TEXT)
                self.src_var.set(fav_path)
                self.source_tree.load(fav_path)
            else:
                self.src_entry.config(state="normal")
                self.src_var.set(drive_root)
                self.src_entry.config(state="readonly", fg=TEXT_DIM)
                # Navigate tree into the subfolder
                self.source_tree.load(fav_path)

        # Compute correct relative path and sync all drive panels
        src_root = self.src_var.get()
        if os.path.normcase(os.path.normpath(fav_path)) == \
           os.path.normcase(os.path.normpath(src_root)):
            rel = ""
        else:
            try:
                rel = os.path.relpath(fav_path, src_root)
            except ValueError:
                rel = ""
            if rel == ".":
                rel = ""

        self.rel_path_var.set(rel if rel else "(root folder)")
        self._sync_drive_panels(rel)
        self.log.log(f"★ Favorite: {fav['name']}  [{detected_mode}]  →  {fav_path}", "info")

    def _fav_rename(self):
        sel = self.fav_listbox.curselection()
        if not sel:
            messagebox.showinfo("Favorites", "Select an entry to rename.")
            return
        fav = self.config["favorites"][sel[0]]
        name = self._ask_name("New name", fav["name"])
        if name:
            fav["name"] = name
            save_config(self.config)
            self._refresh_fav_list()

    def _fav_remove(self):
        sel = self.fav_listbox.curselection()
        if not sel:
            messagebox.showinfo("Favorites", "Select an entry to remove.")
            return
        fav = self.config["favorites"][sel[0]]
        if messagebox.askyesno("Favorites", f"Remove '{fav['name']}' from favorites?"):
            self.config["favorites"].pop(sel[0])
            save_config(self.config)
            self._refresh_fav_list()

    def _fav_context_menu(self, event):
        sel = self.fav_listbox.nearest(event.y)
        if sel < 0:
            return
        self.fav_listbox.selection_clear(0, "end")
        self.fav_listbox.selection_set(sel)
        menu = tk.Menu(self, tearoff=0, bg=BG2, fg=TEXT,
                        activebackground=ACCENT, activeforeground=TEXT,
                        relief="flat", bd=0)
        menu.add_command(label="📂  Open", command=self._fav_open)
        menu.add_command(label="✎  Rename", command=self._fav_rename)
        menu.add_separator()
        menu.add_command(label="✕  Remove", command=self._fav_remove)
        menu.tk_popup(event.x_root, event.y_root)

    def _ask_name(self, title, default=""):
        """Simple inline dialog to ask for a text value."""
        dialog = tk.Toplevel(self)
        dialog.title(title)
        dialog.configure(bg=BG2)
        dialog.resizable(False, False)
        dialog.grab_set()
        result = [None]

        tk.Label(dialog, text=title + ":", font=FONT_BOLD, fg=TEXT,
                 bg=BG2).pack(padx=16, pady=(12, 4))
        entry = tk.Entry(dialog, font=FONT_MAIN, bg=BG, fg=TEXT,
                          insertbackground=TEXT, relief="flat", bd=4, width=32)
        entry.insert(0, default)
        entry.pack(padx=16, pady=4)
        entry.select_range(0, "end")
        entry.focus_set()

        def ok(e=None):
            result[0] = entry.get().strip() or None
            dialog.destroy()

        def cancel():
            dialog.destroy()

        btn_row = tk.Frame(dialog, bg=BG2)
        btn_row.pack(pady=10)
        tk.Button(btn_row, text="OK", command=ok, bg=ACCENT, fg=TEXT,
                  font=FONT_BOLD, relief="flat", padx=12, cursor="hand2").pack(side="left", padx=6)
        tk.Button(btn_row, text="Cancel", command=cancel, bg=BG3, fg=TEXT_DIM,
                  font=FONT_BOLD, relief="flat", padx=12, cursor="hand2").pack(side="left")
        entry.bind("<Return>", ok)
        entry.bind("<Escape>", lambda e: cancel())

        dialog.wait_window()
        return result[0]

    # ══════════════════════════════════════════
    # SOURCE MODE (custom / one of 4 drives)
    # ══════════════════════════════════════════
    def _on_src_mode_change(self):
        mode = self.src_mode.get()
        if mode == "custom":
            self.src_entry.config(state="normal", fg=TEXT)
            return
        idx = int(mode.replace("drive", ""))
        drv_path = self.config["drives"][idx]
        if not drv_path or not os.path.exists(drv_path):
            messagebox.showwarning("No drive",
                                    f"Drive {idx+1} is not configured or unavailable.")
            self.src_mode.set("custom")
            return
        self.src_entry.config(state="normal")
        self.src_var.set(drv_path)
        self.src_entry.config(state="readonly", fg=TEXT_DIM)
        self.source_tree.load(drv_path)
        self._sync_drive_panels("")
        self.rel_path_var.set("(root folder)")
        self.log.log(f"Source: Drive {idx+1}  ({drv_path})", "info")

    def _update_drive_rb_labels(self):
        for i, rb in enumerate(self.drive_rbs):
            drv = self.config["drives"][i]
            lbl = os.path.splitdrive(drv)[0] if drv else f"Drive {i+1}"
            rb.config(text=lbl)
        for i, cb in enumerate(self.dest_cbs):
            drv = self.config["drives"][i]
            lbl = os.path.splitdrive(drv)[0] if drv else f"Drive {i+1}"
            cb.config(text=lbl)

    # ══════════════════════════════════════════
    # NAVIGATION SYNC
    # ══════════════════════════════════════════
    def _patch_source_tree_toolbar(self):
        original_load = self.source_tree.load
        ctrl = self
        def patched_load(path, **kwargs):
            original_load(path, **kwargs)
            ctrl._after_source_navigate()
        self.source_tree.load = patched_load

    def _on_source_navigate(self, event):
        self.after(50, self._after_source_navigate)

    def _go_up_synced(self):
        self._orig_go_up()
        self.after(50, self._after_source_navigate)

    def _after_source_navigate(self):
        src_root = self.src_var.get()
        current  = self.source_tree.root_path
        # If they're the same, we're at root — no relative subpath
        if os.path.normcase(os.path.normpath(current)) == \
           os.path.normcase(os.path.normpath(src_root)):
            rel = ""
        else:
            try:
                rel = os.path.relpath(current, src_root)
            except ValueError:
                rel = ""
            if rel == ".":
                rel = ""
        self.rel_path_var.set(rel if rel else "(root folder)")
        self._sync_drive_panels(rel)

    def _sync_drive_panels(self, rel_subpath):
        for panel in self.drive_panels:
            panel.navigate_to_relative(rel_subpath)

    def _go_to_root(self):
        self.source_tree.load(self.src_var.get())

    # ══════════════════════════════════════════
    # DROP QUEUE PANEL
    # ══════════════════════════════════════════
    def _build_drop_queue(self, parent):
        """
        A visible queue panel below the file tree.
        - Shows items ready to copy (from drag-and-drop OR from tree selection)
        - Drag & drop from Explorer works when tkinterdnd2 is available
        - Highlighted in blue when something is dragged over it
        """
        outer = tk.Frame(parent, bg=BG3, pady=0)
        outer.pack(fill="x", pady=(3, 0))

        # ── Header row ──
        hdr = tk.Frame(outer, bg=BG3, pady=3)
        hdr.pack(fill="x")

        self.drop_zone_title = tk.Label(
            hdr,
            text="⬇  DROP ZONE  — drag files/folders here from Explorer",
            font=FONT_BOLD, fg=TEXT_DIM, bg=BG3, padx=8
        )
        self.drop_zone_title.pack(side="left")

        tk.Button(hdr, text="+ Add files", command=self._queue_pick_files,
                  bg=BG2, fg=ACCENT2, font=FONT_SMALL, relief="flat",
                  padx=6, cursor="hand2").pack(side="right", padx=2)
        tk.Button(hdr, text="+ Add folders", command=self._queue_pick_folder,
                  bg=BG2, fg=ACCENT2, font=FONT_SMALL, relief="flat",
                  padx=6, cursor="hand2").pack(side="right", padx=2)
        tk.Button(hdr, text="✕ Clear", command=self._queue_clear,
                  bg=BG2, fg=RED, font=FONT_SMALL, relief="flat",
                  padx=6, cursor="hand2").pack(side="right", padx=(2, 6))

        # ── Drop surface + list ──
        # This frame is the actual drop target
        self.drop_surface = tk.Frame(outer, bg=BG2, height=110,
                                      highlightthickness=2,
                                      highlightbackground=BORDER,
                                      highlightcolor=ACCENT)
        self.drop_surface.pack(fill="x", padx=6, pady=(0, 4))
        self.drop_surface.pack_propagate(False)

        # Placeholder label (shown when queue is empty)
        self.drop_placeholder = tk.Label(
            self.drop_surface,
            text="⬇   Drag files and folders from Explorer here",
            font=FONT_MAIN, fg=TEXT_DIM, bg=BG2
        )
        self.drop_placeholder.place(relx=0.5, rely=0.5, anchor="center")

        # Listbox showing queued items
        list_container = tk.Frame(self.drop_surface, bg=BG2)
        list_container.pack(fill="both", expand=True, padx=4, pady=4)

        vsb = ttk.Scrollbar(list_container, orient="vertical")
        self.queue_listbox = tk.Listbox(
            list_container,
            bg=BG2, fg=TEXT, font=FONT_SMALL,
            selectbackground=ACCENT, selectforeground=TEXT,
            relief="flat", bd=0, highlightthickness=0,
            yscrollcommand=vsb.set, activestyle="none"
        )
        vsb.config(command=self.queue_listbox.yview)
        self.queue_listbox.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # Right-click to remove item
        self.queue_listbox.bind("<Button-3>", self._queue_item_context)
        self.queue_listbox.bind("<Delete>", lambda e: self._queue_remove_selected())

        # Status badge
        self.queue_badge = tk.Label(hdr, text="0 items",
                                     font=FONT_SMALL, fg=BG, bg=TEXT_DIM,
                                     padx=6, pady=1)
        self.queue_badge.pack(side="right", padx=4)

        # ── Register as DnD target ──────────────────────────────────────────
        if DND_AVAILABLE:
            for widget in (self.drop_surface, self.drop_placeholder,
                           self.queue_listbox, list_container, outer, hdr):
                try:
                    widget.drop_target_register(_dnd_mod.DND_FILES)
                    widget.dnd_bind("<<Drop>>",        self._on_dnd_drop)
                    widget.dnd_bind("<<DragEnter>>",   self._on_dnd_enter)
                    widget.dnd_bind("<<DragLeave>>",   self._on_dnd_leave)
                    widget.dnd_bind("<<DragOver>>",    self._on_dnd_over)
                except Exception:
                    pass
            self.drop_zone_title.config(
                text="⬇  DROP ZONE  — drag files/folders here from Explorer",
                fg=ACCENT2
            )
        else:
            self.drop_zone_title.config(
                text="⬇  COPY QUEUE  (use + buttons to add files)",
                fg=TEXT_DIM
            )

        self._queue_items = []   # list of absolute paths
        self._queue_refresh()

    # ── DnD callbacks ────────────────────────────────────────────────────────

    def _on_dnd_enter(self, event):
        self.drop_surface.config(highlightbackground=ACCENT, highlightcolor=ACCENT,
                                  bg="#1a2540")
        self.drop_placeholder.config(
            text="⬇   Drop now!", fg=ACCENT2, bg="#1a2540"
        )
        self.queue_listbox.config(bg="#1a2540")
        self.drop_surface.config(height=120)

    def _on_dnd_over(self, event):
        pass  # keep highlight

    def _on_dnd_leave(self, event):
        self._queue_reset_surface()

    def _on_dnd_drop(self, event):
        self._queue_reset_surface()
        # tkinterdnd2 gives paths as a Tcl list string
        try:
            raw_paths = self.tk.splitlist(event.data)
        except Exception:
            raw_paths = [event.data]
        added = 0
        for p in raw_paths:
            p = p.strip().strip('"').strip("'")
            if p and p not in self._queue_items:
                self._queue_items.append(p)
                added += 1
        self._queue_refresh()
        self.log.log(f"⬇ Drag & Drop: added {added} item(s) to queue", "info")

    def _queue_reset_surface(self):
        self.drop_surface.config(highlightbackground=BORDER, bg=BG2, height=110)
        self.drop_placeholder.config(
            text="⬇   Drag files and folders from Explorer here",
            fg=TEXT_DIM, bg=BG2
        )
        self.queue_listbox.config(bg=BG2)

    # ── Queue management ─────────────────────────────────────────────────────

    def _queue_pick_files(self):
        paths = filedialog.askopenfilenames(title="Select files to add to queue")
        added = 0
        for p in paths:
            if p and p not in self._queue_items:
                self._queue_items.append(p)
                added += 1
        if added:
            self._queue_refresh()
            self.log.log(f"+ Added {added} file(s) to queue", "info")

    def _queue_pick_folder(self):
        path = filedialog.askdirectory(title="Select folder to add to queue")
        if path and path not in self._queue_items:
            self._queue_items.append(path)
            self._queue_refresh()
            self.log.log(f"+ Added folder to queue: {os.path.basename(path)}", "info")

    def _queue_clear(self):
        if self._queue_items and messagebox.askyesno(
                "Clear queue", f"Remove all {len(self._queue_items)} items from the queue?"):
            self._queue_items.clear()
            self._queue_refresh()
            self._selected_paths = []

    def _queue_remove_selected(self):
        sel = list(self.queue_listbox.curselection())
        for i in sorted(sel, reverse=True):
            self._queue_items.pop(i)
        self._queue_refresh()
        self._selected_paths = list(self._queue_items)

    def _queue_item_context(self, event):
        idx = self.queue_listbox.nearest(event.y)
        if idx < 0:
            return
        self.queue_listbox.selection_clear(0, "end")
        self.queue_listbox.selection_set(idx)
        menu = tk.Menu(self, tearoff=0, bg=BG2, fg=TEXT,
                        activebackground=ACCENT, activeforeground=TEXT,
                        relief="flat", bd=0)
        menu.add_command(label="✕  Remove from queue",
                          command=self._queue_remove_selected)
        menu.add_separator()
        menu.add_command(label="✕  Clear entire queue",
                          command=self._queue_clear)
        menu.tk_popup(event.x_root, event.y_root)

    def _queue_refresh(self):
        """Rebuild the listbox display and update _selected_paths."""
        self.queue_listbox.delete(0, "end")
        for p in self._queue_items:
            icon = "📁" if os.path.isdir(p) else get_item_icon(p)
            exists = os.path.exists(p)
            self.queue_listbox.insert("end", f"  {icon}  {p}")
            self.queue_listbox.itemconfig("end",
                fg=TEXT if exists else RED)

        count = len(self._queue_items)
        # Show/hide placeholder
        if count == 0:
            self.drop_placeholder.place(relx=0.5, rely=0.5, anchor="center")
        else:
            self.drop_placeholder.place_forget()

        # Badge
        badge_color = GREEN if count > 0 else TEXT_DIM
        badge_text = f"{count} items" if count != 1 else "1 item"
        self.queue_badge.config(text=badge_text, bg=badge_color)

        # Keep _selected_paths in sync so KOPIUJ always uses queue
        self._selected_paths = list(self._queue_items)

    # ══════════════════════════════════════════
    # DROP ZONE (old method kept as no-op for safety)
    # ══════════════════════════════════════════
    def _setup_drop_zone(self, frame):
        pass  # replaced by _build_drop_queue

    def _on_drop(self, event):
        pass  # handled by _on_dnd_drop

    def _pick_files_manually(self):
        self._queue_pick_files()



    # ══════════════════════════════════════════
    # SOURCE SELECTION
    # ══════════════════════════════════════════
    def _on_source_select(self, paths):
        """Tree selection — updates _selected_paths only when queue is empty."""
        if not hasattr(self, '_queue_items') or not self._queue_items:
            self._selected_paths = paths

    def _choose_source(self):
        path = filedialog.askdirectory(title="Select source folder")
        if path:
            self.src_mode.set("custom")
            self.src_entry.config(state="normal", fg=TEXT)
            self.src_var.set(path)
            self.config["source_path"] = path
            save_config(self.config)
            self.source_tree.load(path)
            self.rel_path_var.set("(root folder)")
            self._sync_drive_panels("")

    def _go_source(self):
        self.source_tree.load(self.src_var.get())
        self.rel_path_var.set("(root folder)")
        self._sync_drive_panels("")

    def _load_source(self):
        src = self.src_var.get()
        if os.path.exists(src):
            self.source_tree.load(src)

    # ══════════════════════════════════════════
    # DRIVES
    # ══════════════════════════════════════════
    def _refresh_drives(self):
        for panel in self.drive_panels:
            panel.refresh()
        self._update_drive_rb_labels()
        self._refresh_fav_list()

    def _get_active_drives(self):
        active = []
        for i, var in enumerate(self.dest_vars):
            if var.get():
                path = self.config["drives"][i]
                if path and os.path.exists(path):
                    active.append((i, path))
        return active

    # ══════════════════════════════════════════
    # COPY / DELETE / SYNC
    # ══════════════════════════════════════════
    def _copy_selected(self):
        if self._copying:
            self.log.log("Copy in progress – please wait!", "warn")
            return
        # Priority: drop queue > tree selection
        if hasattr(self, '_queue_items') and self._queue_items:
            paths = list(self._queue_items)
        else:
            paths = self._selected_paths
        if not paths:
            messagebox.showwarning("Nothing to copy",
                "Add files/folders to the drop zone\nor select them in the tree above.")
            return
        drives = self._get_active_drives()
        if not drives:
            messagebox.showerror("No drives", "No active destination drives.")
            return
        threading.Thread(target=self._do_copy, args=(paths, drives), daemon=True).start()

    def _do_copy(self, src_paths, drives):
        self._copying = True
        self.copy_btn.config(state="disabled")
        total = len(src_paths) * len(drives)
        done  = 0
        self.log.log(f"Copying: {len(src_paths)} item(s) → {len(drives)} drive(s)", "info")
        for drive_idx, drive_root in drives:
            panel = self.drive_panels[drive_idx]
            panel.set_status("⏳ Copying...", ORANGE)
            rel = panel.relative_subpath
            dest_folder = os.path.join(drive_root, rel) if rel else drive_root
            os.makedirs(dest_folder, exist_ok=True)
            for src in src_paths:
                if not src:
                    continue
                name = os.path.basename(src)
                dest = os.path.join(dest_folder, name)
                try:
                    if os.path.isdir(src):
                        if os.path.exists(dest):
                            shutil.rmtree(dest)
                        shutil.copytree(src, dest)
                    else:
                        shutil.copy2(src, dest)
                    self.log.log(f"✔ {name} → Drive {drive_idx+1}", "ok")
                except Exception as e:
                    self.log.log(f"✘ {name} → Drive {drive_idx+1}: {e}", "err")
                done += 1
                self.progress_var.set((done / total) * 100)
            panel.set_status("✔ Done", GREEN)
            panel.refresh()
        self.progress_var.set(100)
        self.log.log("Copy complete!", "ok")
        self._copying = False
        self.copy_btn.config(state="normal")
        messagebox.showinfo("Done", "Copy completed successfully!")

    def _delete_selected(self):
        paths = self._selected_paths
        if not paths:
            messagebox.showwarning("Nothing selected", "Select items to delete from drives.")
            return
        drives = self._get_active_drives()
        if not drives:
            messagebox.showerror("No drives", "No active drives.")
            return
        names = [os.path.basename(p) for p in paths]
        msg = f"Delete {len(names)} item(s) from {len(drives)} drive(s)?\n\n" + \
              "\n".join(names[:8])
        if len(names) > 8:
            msg += f"\n... and {len(names)-8} more"
        if not messagebox.askyesno("Confirm delete", msg):
            return
        for drive_idx, drive_root in drives:
            panel = self.drive_panels[drive_idx]
            rel = panel.relative_subpath
            dest_folder = os.path.join(drive_root, rel) if rel else drive_root
            for src in paths:
                name = os.path.basename(src)
                target = os.path.join(dest_folder, name)
                try:
                    if os.path.isdir(target):
                        shutil.rmtree(target)
                    elif os.path.isfile(target):
                        os.remove(target)
                    self.log.log(f"🗑 {name} deleted from Drive {drive_idx+1}", "warn")
                except Exception as e:
                    self.log.log(f"✘ Delete error {name}: {e}", "err")
            panel.refresh()

    def _sync_all(self):
        src = self.source_tree.root_path
        if not src or not os.path.exists(src):
            messagebox.showerror("Error", "No active source folder.")
            return
        drives = self._get_active_drives()
        if not drives:
            messagebox.showerror("No drives", "No active drives.")
            return
        rel = self.drive_panels[0].relative_subpath if self.drive_panels else ""
        rel_display = rel if rel else "(root folder)"
        msg = (f"SYNC:\n{src}\n\n"
               f"→ subfolder on drives: {rel_display}\n"
               f"→ {len(drives)} drive(s)\n\nFiles will be OVERWRITTEN!")
        if not messagebox.askyesno("Confirm sync", msg):
            return
        threading.Thread(target=self._do_sync, args=(src, drives, rel), daemon=True).start()

    def _do_sync(self, src, drives, rel_subpath):
        self._copying = True
        self.copy_btn.config(state="disabled")
        self.log.log(f"Syncing: {src} → {len(drives)} drive(s)", "info")
        for drive_idx, drive_root in drives:
            panel = self.drive_panels[drive_idx]
            panel.set_status("⏳ Syncing...", ORANGE)
            dest_folder = os.path.join(drive_root, rel_subpath) if rel_subpath else drive_root
            try:
                os.makedirs(dest_folder, exist_ok=True)
                for item in os.scandir(src):
                    dest = os.path.join(dest_folder, item.name)
                    if item.is_dir():
                        if os.path.exists(dest):
                            shutil.rmtree(dest)
                        shutil.copytree(item.path, dest)
                    else:
                        shutil.copy2(item.path, dest)
                    self.log.log(f"✔ {item.name} → Drive {drive_idx+1}", "ok")
                panel.set_status("✔ Synced", GREEN)
                panel.refresh()
            except Exception as e:
                self.log.log(f"✘ Drive {drive_idx+1}: {e}", "err")
                panel.set_status("✘ Error", RED)
        self.log.log("Sync complete!", "ok")
        self._copying = False
        self.copy_btn.config(state="normal")

    # ══════════════════════════════════════════
    # SAFE EJECT
    # ══════════════════════════════════════════
    def _eject_all_drives(self):
        """Safely eject / power-off all configured drives (Windows & Linux)."""
        drives = self._get_active_drives()
        if not drives:
            messagebox.showinfo("Safely Eject", "No active drives to eject.")
            return
        names = [f"Drive {i+1}: {path}" for i, path in drives]
        msg = "Safely eject the following drives?\n\n" + "\n".join(names)
        if not messagebox.askyesno("Safely Eject All Drives", msg):
            return
        threading.Thread(target=self._do_eject, args=(drives,), daemon=True).start()

    def _do_eject(self, drives):
        system = platform.system()
        results = []
        for drive_idx, drive_path in drives:
            ok, detail = self._eject_drive(system, drive_path)
            tag = "ok" if ok else "err"
            status = "✔ Ejected" if ok else "✘ Failed"
            self.log.log(f"⏏ Drive {drive_idx+1} {status}: {detail}", tag)
            results.append((drive_idx, ok, detail))

        # Update panels that were successfully ejected
        for drive_idx, ok, _ in results:
            panel = self.drive_panels[drive_idx]
            if ok:
                panel.set_status("⏏ Ejected – safe to remove", "#22c55e")
            else:
                panel.set_status("✘ Eject failed", "#ef4444")

        success = sum(1 for _, ok, _ in results if ok)
        fail    = len(results) - success
        summary = f"Eject complete: {success} succeeded"
        if fail:
            summary += f", {fail} failed (check log)"
        self.after(0, lambda: messagebox.showinfo("Safely Eject", summary))

    def _eject_drive(self, system, path):
        """Platform-specific eject. Returns (success: bool, detail: str)."""
        try:
            if system == "Windows":
                return self._eject_windows(path)
            elif system == "Linux":
                return self._eject_linux(path)
            elif system == "Darwin":
                return self._eject_mac(path)
            else:
                return False, f"Unsupported OS: {system}"
        except Exception as e:
            return False, str(e)

    def _eject_windows(self, path):
        """Windows: use mountvol to dismount, then DeviceIoControl via PowerShell."""
        drive_letter = os.path.splitdrive(path)[0]  # e.g. "E:"
        if not drive_letter:
            return False, "Could not determine drive letter"
        # Try PowerShell-based safe removal (works for USB drives)
        ps_script = (
            "$vol = (Get-WmiObject Win32_Volume | Where-Object {$_.DriveLetter -eq '"
            + drive_letter + "'});"
            "if($vol){$vol.Dismount($false,$false)} else {'notfound'}"
        )
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_script],
                capture_output=True, text=True, timeout=15
            )
            out = result.stdout.strip()
            if "notfound" in out.lower():
                return False, f"Volume {drive_letter} not found via WMI"
            if result.returncode == 0:
                return True, f"Dismounted {drive_letter} via PowerShell"
            # Fallback: mountvol /d
            r2 = subprocess.run(
                ["mountvol", drive_letter + "\\", "/d"],
                capture_output=True, text=True, timeout=10
            )
            if r2.returncode == 0:
                return True, f"Unmounted {drive_letter} via mountvol"
            return False, result.stderr.strip() or "Unknown error"
        except FileNotFoundError:
            # powershell not on PATH – try mountvol directly
            r2 = subprocess.run(
                ["mountvol", drive_letter + "\\", "/d"],
                capture_output=True, text=True, timeout=10
            )
            return (r2.returncode == 0,
                    f"mountvol {drive_letter}" if r2.returncode == 0 else r2.stderr.strip())
        except subprocess.TimeoutExpired:
            return False, "Timeout waiting for eject"

    def _eject_linux(self, path):
        """Linux: try udisksctl power-off first, then umount+eudiscs or udisks."""
        # Resolve the real block device for the path
        try:
            result = subprocess.run(
                ["df", "--output=source", path],
                capture_output=True, text=True, timeout=5
            )
            lines = result.stdout.strip().splitlines()
            device = lines[-1].strip() if len(lines) >= 2 else ""
        except Exception:
            device = ""

        if not device or device == "Filesystem":
            return False, f"Could not resolve block device for {path}"

        # Strip partition number to get disk (e.g. /dev/sdb1 -> /dev/sdb)
        import re
        disk = re.sub(r'p?\d+$', '', device)  # handles /dev/sda1, /dev/nvme0n1p1

        # Try udisksctl power-off (safest – spins down + removes)
        try:
            r = subprocess.run(
                ["udisksctl", "power-off", "-b", disk],
                capture_output=True, text=True, timeout=15
            )
            if r.returncode == 0:
                return True, f"Power-off {disk} via udisksctl"
        except FileNotFoundError:
            pass

        # Fallback: unmount the partition, then eject
        try:
            r = subprocess.run(
                ["udisksctl", "unmount", "-b", device],
                capture_output=True, text=True, timeout=10
            )
        except FileNotFoundError:
            # udisksctl not available – plain umount
            subprocess.run(["umount", path], capture_output=True, timeout=10)

        # Try eject command
        try:
            r = subprocess.run(
                ["eject", disk],
                capture_output=True, text=True, timeout=10
            )
            return (r.returncode == 0,
                    f"eject {disk}" if r.returncode == 0 else r.stderr.strip())
        except FileNotFoundError:
            return False, "Neither udisksctl nor eject found. Install udisks2."

    def _eject_mac(self, path):
        """macOS: diskutil eject."""
        try:
            r = subprocess.run(
                ["diskutil", "eject", path],
                capture_output=True, text=True, timeout=10
            )
            return (r.returncode == 0,
                    f"diskutil eject {path}" if r.returncode == 0 else r.stderr.strip())
        except FileNotFoundError:
            return False, "diskutil not found"

    def _on_close(self):
        self.withdraw()


# ─────────────────────────────────────────────
# MAIN WINDOW (4 drive panels)
# ─────────────────────────────────────────────
# Base class is TkinterDnD.Tk when available so every child widget
# can register as a drop target without extra work.
_TkBase = _dnd_mod.Tk if DND_AVAILABLE else tk.Tk

class MainWindow(_TkBase):  # type: ignore[misc]
    def __init__(self):
        super().__init__()
        self.config_data = load_config()
        self.title("BackupFlow – Drive Browser")
        self.configure(bg=BG)
        self.geometry("1280x780")
        self.minsize(800, 500)
        self._build()
        self.update_idletasks()
        apply_dark_titlebar(self)
        self._open_control_panel()

    def _build(self):
        # ── Header ──
        header = tk.Frame(self, bg=BG3, pady=10, padx=16)
        header.pack(fill="x")
        tk.Label(header, text="💾  BackupFlow", font=("Segoe UI", 16, "bold"),
                 fg=ACCENT2, bg=BG3).pack(side="left")
        tk.Label(header, text="External Drive Browser",
                 font=FONT_MAIN, fg=TEXT_DIM, bg=BG3).pack(side="left", padx=16)
        tk.Button(header, text="⌨  Control Panel", command=self._open_control_panel,
                  bg=ACCENT, fg=TEXT, font=FONT_BOLD, relief="flat",
                  padx=12, pady=4, cursor="hand2").pack(side="right")
        tk.Button(header, text="🔄  Refresh all", command=self._refresh_all,
                  bg=BG2, fg=TEXT_DIM, font=FONT_BOLD, relief="flat",
                  padx=10, pady=4, cursor="hand2").pack(side="right", padx=6)

        # ── 4 Drive panels in 2×2 grid ──
        grid = tk.Frame(self, bg=BG)
        grid.pack(fill="both", expand=True, padx=6, pady=6)
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)
        grid.rowconfigure(0, weight=1)
        grid.rowconfigure(1, weight=1)

        self.drive_panels = []
        positions = [(0, 0), (0, 1), (1, 0), (1, 1)]
        for i, (row, col) in enumerate(positions):
            panel = DrivePanel(grid, i, self.config_data)
            panel.grid(row=row, column=col, sticky="nsew", padx=4, pady=4)
            self.drive_panels.append(panel)

        # ── Status bar ──
        status = tk.Frame(self, bg=BG3, pady=4)
        status.pack(fill="x", side="bottom")
        self.status_label = tk.Label(status, text="BackupFlow ready",
                                      font=FONT_SMALL, fg=TEXT_DIM, bg=BG3)
        self.status_label.pack(side="left", padx=10)
        tk.Label(status,
                 text=f"v1.0  |  {datetime.now().strftime('%d.%m.%Y')}",
                 font=FONT_SMALL, fg=TEXT_DIM, bg=BG3).pack(side="right", padx=10)

        self.control_panel = None

    def _refresh_all(self):
        for panel in self.drive_panels:
            panel.refresh()

    def _open_control_panel(self):
        if self.control_panel and self.control_panel.winfo_exists():
            self.control_panel.deiconify()
            self.control_panel.lift()
        else:
            self.control_panel = ControlPanel(
                self, self.config_data, self.drive_panels
            )
            # Position to the right of main window
            x = self.winfo_x() + self.winfo_width() + 10
            y = self.winfo_y()
            self.control_panel.geometry(f"+{x}+{y}")


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────
if __name__ == "__main__":
    app = MainWindow()
    app.mainloop()
