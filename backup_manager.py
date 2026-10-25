"""
BackupFlow - Backup Manager
Application for managing backups across multiple external drives
"""

import os
import sys
import shutil
import stat
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import subprocess
import platform
from pathlib import Path
import time
from datetime import datetime
import json
import queue

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

# ── Try to import Pillow (image preview). Auto-install if missing. ──────────
PIL_AVAILABLE = False
try:
    from PIL import Image, ImageTk, ImageOps
    PIL_AVAILABLE = True
except ImportError:
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "pillow", "--quiet"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        from PIL import Image, ImageTk, ImageOps
        PIL_AVAILABLE = True
    except Exception:
        Image = ImageTk = ImageOps = None

# Extensions shown in the image preview panel of the source tree
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp",
              ".tif", ".tiff", ".ico"}
PREVIEW_WIDTH = 300   # px, width of the preview panel

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".backup_manager_config.json")

# Total drive slots supported. First MAIN_DRIVES are shown in the main window;
# the rest (up to NUM_DRIVES) live in the secondary "More Drives" window.
NUM_DRIVES  = 8
MAIN_DRIVES = 4

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    else:
        cfg = {"drives": [], "source_path": str(Path.home()), "window_positions": {}}
    # Migrate/pad older configs (which may only have 4 drive slots) up to NUM_DRIVES.
    drives = cfg.get("drives", [])
    if len(drives) < NUM_DRIVES:
        drives = drives + [""] * (NUM_DRIVES - len(drives))
    cfg["drives"] = drives[:NUM_DRIVES]
    return cfg

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

# ── "New folder" toolbar icon (flat folder + green "+" badge, 20x20 PNG) ──
NEW_FOLDER_ICON_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAADN0lEQVR4nKWUS2gkZRSFv3v/"
    "v6rT3XnS4yRkMTIwAVEYdCEoCM4ggquACxGU+JrZiAuXgiA9vXSpLgRBNItZOIoKuvCxiQsR"
    "3agTRMQHPsZRwph3d6frca+L7iRtTAbBA1U/VFHnnnPurSsMw104CAEQ/9fz/4dDCh0BGVwO"
    "8OT7PrWxsftqg4kTE7x8F+uIeLPp2rrA4Upl34E0m01dOnNBT/6evxkqyd1lLzMEBTFNgpZ5"
    "8W1lLL33lXnpHKWq2XRttcR2FbKw6I0Qsz9DkkYvfTc33CFEyHc6d+Za+y4UaBmxXaIJoFPD"
    "F++X9WHLPHDJ03qWL4c0zJVZYYAOpec4WyL7RD64C2IxTcl72VudNH3q5m8GYT/xro9ZO/te"
    "YzJtee6I/KMJohGRXSIDBPV+Tdd+eenuzL36SPWHCLCVkdShekTkeJm7iSMuREsxgV7YAMGT"
    "bEzU1RMZCXhTI0CS44PShxMKEjzFpODXqQ9YqX9BN67gGCPFMY73btfR9ZOKtEwAHrroUynZ"
    "TxqSSSsOWnbUI1lYZ3n6RVZrl1FPUY/9ADx3KhCsuuylL8SjVA0liEnO8vRLrNYuUymmMDEC"
    "gAgliUjXXcbiaWtnH+r1qBwjWsLV8SVWa19TKaYoJSeIsG07bBZtogiuLradmYQwc13Cvjpn"
    "pf45aikuRpTA1d415o/dwbnZ+7jSu0YQBRH1wnzPsoOBD/rcP9WDZLrl3bgiSkQFtssuD8/c"
    "w/OnzlMPIwC8/sdH1EIFw0UBkgwXqInooBkqIAIC4uKY7yl2p5GMU9WUKIHj6SQ+NG+x6a4t"
    "2Hj0IosS7Tw5gCmImBQk5Sg1n5E1+cvMoo7HGi/89jYK3JBO8uyPrzFbaWBu4P0/ZW/bnLvU"
    "PeWMBHo9ADphLdbKmeKzE08/njfaz5RrWS4qSRClXe5g7ozFKqUbmDtBh+bNXYbX0DCmvzpd"
    "r3Vu+zKMJnPlZi8XkaT/qQyUeSnVJHi36O7P4WDnHSRbOrOkn9x6tn3jp7fMy46+E8YrN1k7"
    "x8z7xkTQ0TRYr7iCyGP/bRN7U5GWzX680BgZDy2cBzFr4CBBNj3Ie+V297lfzr7x89+JYnTM"
    "/Wcw7gAAAABJRU5ErkJggg=="
)


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
    if os.path.isdir(lp(path)):
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
# FILE-OPERATION HELPERS (rename / delete / move in drive panels)
# ─────────────────────────────────────────────
INVALID_NAME_CHARS = set('<>:"/\\|?*') if platform.system() == "Windows" else {"/"}

def ask_text_dialog(parent, title, default="", select_len=None):
    """Small dark modal dialog asking for one line of text. Returns the
    stripped text, or None if cancelled / empty. select_len pre-selects only
    the first N characters (used to skip the extension when renaming)."""
    top = parent.winfo_toplevel()
    dialog = tk.Toplevel(top)
    dialog.title(title)
    dialog.configure(bg=BG2)
    dialog.resizable(False, False)
    dialog.transient(top)
    result = [None]

    tk.Label(dialog, text=title + ":", font=FONT_BOLD, fg=TEXT,
             bg=BG2).pack(padx=16, pady=(12, 4))
    entry = tk.Entry(dialog, font=FONT_MAIN, bg=BG, fg=TEXT,
                     insertbackground=TEXT, relief="flat", bd=4, width=44)
    entry.insert(0, default)
    entry.pack(padx=16, pady=4)
    entry.select_range(0, select_len if select_len is not None else "end")

    def ok(e=None):
        result[0] = entry.get().strip() or None
        dialog.destroy()

    def cancel(e=None):
        dialog.destroy()

    btn_row = tk.Frame(dialog, bg=BG2)
    btn_row.pack(pady=10)
    tk.Button(btn_row, text="OK", command=ok, bg=ACCENT, fg=TEXT,
              font=FONT_BOLD, relief="flat", padx=12, cursor="hand2").pack(side="left", padx=6)
    tk.Button(btn_row, text="Cancel", command=cancel, bg=BG3, fg=TEXT_DIM,
              font=FONT_BOLD, relief="flat", padx=12, cursor="hand2").pack(side="left")
    entry.bind("<Return>", ok)
    entry.bind("<Escape>", cancel)

    dialog.update_idletasks()
    try:
        x = top.winfo_rootx() + (top.winfo_width() - dialog.winfo_reqwidth()) // 2
        y = top.winfo_rooty() + (top.winfo_height() - dialog.winfo_reqheight()) // 3
        dialog.geometry(f"+{max(x, 0)}+{max(y, 0)}")
    except Exception:
        pass
    apply_dark_titlebar(dialog)
    try:
        dialog.wait_visibility()
        dialog.grab_set()
    except Exception:
        pass
    entry.focus_force()
    dialog.wait_window()
    return result[0]

def lp(path):
    """Long-path helper (Windows). Plain Win32 calls fail for paths of 260+
    characters (MAX_PATH) unless the path carries the extended-length prefix
    (backslash backslash question-mark backslash). Returns `path` unchanged
    on other systems and for short paths, so only paths that really need it
    are rewritten.

    Rule used throughout the app: paths that are STORED / DISPLAYED / compared
    stay in their normal form; lp() is applied only at the moment a path is
    handed to os.* / open() / shutil.*."""
    if os.name != "nt" or not isinstance(path, str) or not path:
        return path
    if path.startswith("\\\\?\\"):
        return path
    try:
        full = os.path.abspath(path)
    except Exception:
        return path
    if len(full) < 240:
        return path
    if full.startswith("\\\\"):                    # UNC share
        return "\\\\?\\UNC\\" + full[2:]
    return "\\\\?\\" + full


def _rmtree_retry(func, path, *_):
    """rmtree error handler: clear the read-only flag and retry once
    (Windows refuses to delete read-only files, e.g. inside .git)."""
    os.chmod(path, stat.S_IWRITE)
    func(path)

def remove_path(path):
    """Permanently delete a file or a whole folder tree (long-path safe)."""
    p = lp(path)
    if os.path.isdir(p):
        if _is_reparse(path):            # symlink / junction: remove only the link
            try:
                os.rmdir(p)
            except OSError:
                os.unlink(p)
        elif sys.version_info >= (3, 12):
            shutil.rmtree(p, onexc=_rmtree_retry)
        else:
            shutil.rmtree(p, onerror=_rmtree_retry)
    else:
        try:
            os.remove(p)
        except PermissionError:
            os.chmod(p, stat.S_IWRITE)
            os.remove(p)

class OperationCancelled(BaseException):
    """Raised inside a worker thread when the user pressed STOP ALL.
    Derives from BaseException on purpose: the copy/move/sync code has many
    `except Exception` blocks that must NOT swallow a cancellation."""


def check_cancel(cancel):
    if cancel is not None and cancel.is_set():
        raise OperationCancelled()


def _is_reparse(path):
    """True for symlinks AND Windows junctions (never recurse into those
    when deleting - that would wipe the link's target)."""
    try:
        st = os.lstat(lp(path))
    except OSError:
        return False
    if stat.S_ISLNK(st.st_mode):
        return True
    return bool(getattr(st, "st_file_attributes", 0) & 0x400)


def copy_file_cancellable(src, dst, cancel, chunk=1024 * 1024):
    """copy2() replacement that checks the cancel flag every chunk, so
    even a multi-GB file can be interrupted. Partial target is removed.
    Long-path safe (see lp)."""
    s_, d_ = lp(src), lp(dst)
    try:
        with open(s_, "rb") as fsrc, open(d_, "wb") as fdst:
            while True:
                check_cancel(cancel)
                buf = fsrc.read(chunk)
                if not buf:
                    break
                fdst.write(buf)
    except OperationCancelled:
        try:
            os.remove(d_)
        except OSError:
            pass
        raise
    try:
        shutil.copystat(s_, d_)
    except OSError:
        pass


def copytree_cancellable(src, dst, cancel):
    """copytree() replacement: cancel checked before every entry/chunk.
    Like shutil.copytree it keeps going after a single-file error and
    raises shutil.Error with the collected errors at the end."""
    errors = []
    os.makedirs(lp(dst), exist_ok=True)
    with os.scandir(lp(src)) as it:
        entries = list(it)
    for e in entries:
        check_cancel(cancel)
        sp = os.path.join(src, e.name)      # keep paths in normal form
        d = os.path.join(dst, e.name)
        try:
            if e.is_dir():
                copytree_cancellable(sp, d, cancel)
            else:
                copy_file_cancellable(sp, d, cancel)
        except OSError as ex:
            errors.append((sp, d, str(ex)))
    try:
        shutil.copystat(lp(src), lp(dst))
    except OSError:
        pass
    if errors:
        raise shutil.Error(errors)


def remove_path_cancellable(path, cancel):
    """remove_path() replacement that checks the cancel flag per entry."""
    check_cancel(cancel)
    p = lp(path)
    if os.path.isdir(p) and not _is_reparse(path):
        with os.scandir(p) as it:
            entries = list(it)
        for e in entries:
            remove_path_cancellable(os.path.join(path, e.name), cancel)
        try:
            os.rmdir(p)
        except PermissionError:
            os.chmod(p, stat.S_IWRITE)
            os.rmdir(p)
    elif os.path.isdir(p):             # symlink / junction to a folder
        try:
            os.rmdir(p)
        except OSError:
            os.unlink(p)
    else:
        remove_path(path)


def move_path(src, dst, cancel=None):
    """shutil.move() replacement that is long-path safe: instant rename on
    the same volume, otherwise copy + delete (like shutil.move does)."""
    try:
        os.rename(lp(src), lp(dst))
        return
    except OSError:
        pass
    if os.path.isdir(lp(src)):
        copytree_cancellable(src, dst, cancel)
    else:
        copy_file_cancellable(src, dst, cancel)
    remove_path(src)


def same_volume(a, b):
    try:
        if platform.system() == "Windows":
            return (os.path.splitdrive(os.path.abspath(a))[0].lower()
                    == os.path.splitdrive(os.path.abspath(b))[0].lower())
        return os.stat(a).st_dev == os.stat(b).st_dev
    except Exception:
        return False

def _norm_path(p):
    return os.path.normcase(os.path.abspath(p))


# ─────────────────────────────────────────────
# FILE TREE WIDGET (reused in multiple panels)
# ─────────────────────────────────────────────
class FileTree(tk.Frame):
    def __init__(self, parent, root_path="", on_select=None, readonly=False,
                 on_new_folder=None, show_preview=False, editable=False,
                 status_cb=None, **kwargs):
        super().__init__(parent, bg=BG2, **kwargs)
        # editable=True enables: right-click menu (Rename / Delete), F2 / Del
        # keys and drag & drop moving of (multi-)selected files and folders
        # onto folders of this or any other editable tree (e.g. another drive).
        self.editable = editable
        self.status_cb = status_cb     # optional fn(msg, color) for progress text
        self._busy = False
        self._status_token = 0
        self._hl = None                # current drop-highlight (see _set_highlight)
        self._hl_key = None
        if editable:
            # constant 2px border that turns blue when this tree is a drop target
            self.config(highlightthickness=2, highlightbackground=BG2,
                        highlightcolor=BG2)
        self.show_preview = show_preview
        self._preview_path = None      # path currently shown in the preview
        self._preview_token = 0        # invalidates stale background loads
        self._preview_job = None       # debounce timer id
        self._preview_img = None       # keep a reference (Tk would GC it)
        self._preview_last_size = (0, 0)
        self.root_path = root_path
        self.on_select_cb = on_select
        self.readonly = readonly
        self.on_new_folder_cb = on_new_folder
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
        self.btn_up = tk.Button(toolbar, text="⬆", command=self.go_up,
                  bg=BG3, fg=TEXT_DIM, font=FONT_BOLD, relief="flat", bd=0,
                  padx=8, cursor="hand2")
        self.btn_up.pack(side="left", padx=(0, 4))
        tk.Button(toolbar, text="🔄", command=self.refresh,
                  bg=BG3, fg=TEXT_DIM, font=FONT_BOLD, relief="flat", bd=0,
                  padx=8, cursor="hand2").pack(side="left", padx=(0, 6))

        # "New folder" button — only shown when a callback was supplied
        # (source tree gets one; read-only drive-preview trees don't).
        if self.on_new_folder_cb:
            self._new_folder_icon = tk.PhotoImage(data=NEW_FOLDER_ICON_B64)
            tk.Button(toolbar, image=self._new_folder_icon,
                      command=self.on_new_folder_cb,
                      bg=BG3, activebackground=BG3, relief="flat", bd=0,
                      padx=4, cursor="hand2").pack(side="left", padx=(0, 6))

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
        self.tree.tag_configure("droptarget", background="#1e40af", foreground=TEXT)

        vsb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        vsb.pack(side="right", fill="y")
        if self.show_preview:
            self._build_preview()
            self.preview_frame.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)

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
        if self.editable:
            self._setup_editing()
            return
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

    # ══════════════════════════════════════════
    # EDITING (only when editable=True): context menu, rename, delete,
    # drag & drop move
    # ══════════════════════════════════════════
    def _setup_editing(self):
        t = self.tree
        t.bind("<Button-3>", self._context_menu)
        t.bind("<F2>", lambda e: self.rename_selected())
        t.bind("<Delete>", lambda e: self.delete_selected())
        t.bind("<Control-a>", self._select_all)
        t.bind("<Escape>", self._dd_cancel)
        t.bind("<ButtonPress-1>", self._dd_press)
        t.bind("<B1-Motion>", self._dd_motion)
        t.bind("<ButtonRelease-1>", self._dd_release)
        self._dd = {"pressed": False, "dragging": False}

    def _select_all(self, event=None):
        self.tree.selection_set(self.tree.get_children())
        return "break"

    def _status(self, msg, color=TEXT_DIM, clear_after=None):
        if not self.status_cb:
            return
        try:
            self.status_cb(msg, color)
            if clear_after:
                self._status_token += 1
                tok = self._status_token
                self.after(clear_after,
                           lambda: self._status_token == tok and self.status_cb("", TEXT_DIM))
        except Exception:
            pass  # widget destroyed

    def _msg_parent(self):
        return self.winfo_toplevel()

    # ── Right-click menu ──────────────────────
    def _context_menu(self, event):
        item = self.tree.identify_row(event.y)
        if not item:
            return
        # If the right-clicked row isn't part of the selection, select just it.
        if item not in self.tree.selection():
            self.tree.selection_set(item)
        self.tree.focus(item)
        paths = self.get_selected_paths()
        if not paths:
            return
        menu = tk.Menu(self, tearoff=0, bg=BG2, fg=TEXT,
                       activebackground=ACCENT, activeforeground=TEXT,
                       relief="flat", bd=0)
        if len(paths) == 1:
            menu.add_command(label="✎  Rename\tF2", command=self.rename_selected)
            menu.add_separator()
        label = "✕  Delete\tDel" if len(paths) == 1 else f"✕  Delete {len(paths)} items\tDel"
        menu.add_command(label=label, command=self.delete_selected)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    # ── Rename ────────────────────────────────
    def rename_selected(self):
        paths = self.get_selected_paths()
        if len(paths) != 1 or self._busy:
            return
        src = paths[0]
        old_name = os.path.basename(src)
        stem_len = None if os.path.isdir(lp(src)) else len(os.path.splitext(old_name)[0])
        new_name = ask_text_dialog(self, "New name", old_name, select_len=stem_len)
        if not new_name or new_name == old_name:
            return
        if any(c in INVALID_NAME_CHARS for c in new_name):
            bad = " ".join(sorted(INVALID_NAME_CHARS))
            messagebox.showerror("Rename", f"Name can't contain: {bad}",
                                 parent=self._msg_parent())
            return
        new_path = os.path.join(os.path.dirname(src), new_name)
        # A pure case change (foo -> Foo) "exists" on Windows but is allowed.
        if os.path.lexists(lp(new_path)) and _norm_path(new_path) != _norm_path(src):
            messagebox.showerror("Rename", f"'{new_name}' already exists in this folder.",
                                 parent=self._msg_parent())
            return
        try:
            os.rename(lp(src), lp(new_path))
        except Exception as e:
            messagebox.showerror("Rename", f"Could not rename:\n{e}",
                                 parent=self._msg_parent())
            return
        self._status(f"✔ Renamed: {old_name} → {new_name}", GREEN, 6000)
        self.refresh_async(on_done=lambda: self.select_paths([new_path]))

    # ── Delete ────────────────────────────────
    def delete_selected(self):
        paths = self.get_selected_paths()
        if not paths or self._busy:
            return
        names = [os.path.basename(p) for p in paths]
        msg = f"Delete {len(names)} item(s)?\n\n" + "\n".join(names[:8])
        if len(names) > 8:
            msg += f"\n... and {len(names) - 8} more"
        msg += "\n\n⚠ Permanently — NOT sent to the Recycle Bin. This can't be undone."
        if not messagebox.askyesno("Confirm delete", msg, icon="warning",
                                   default="no", parent=self._msg_parent()):
            return

        def work():
            ok, errs = 0, []
            for p in paths:
                try:
                    remove_path(p)
                    ok += 1
                except Exception as e:
                    errs.append(f"{os.path.basename(p)}: {e}")
            return ok, errs

        def done(res):
            ok, errs = res
            self.refresh_async()
            if errs:
                self._status(f"✘ Deleted {ok}, {len(errs)} failed", RED, 8000)
                messagebox.showerror("Delete", "Could not delete:\n\n" + "\n".join(errs[:8]),
                                     parent=self._msg_parent())
            else:
                self._status(f"✔ Deleted {ok} item(s)", GREEN, 6000)

        self._status("⏳ Deleting...", ORANGE)
        self._run_bg(work, done)

    def _run_bg(self, work, done):
        """Run work() on a worker thread, then done(result) on the main thread."""
        self._busy = True

        def runner():
            try:
                res = work()
            except Exception as e:
                res = (0, [str(e)])
            try:
                self.after(0, lambda: finish(res))
            except Exception:
                pass  # widget destroyed meanwhile

        def finish(res):
            self._busy = False
            done(res)

        threading.Thread(target=runner, daemon=True).start()

    # ── Move (target of drag & drop) ──────────
    @staticmethod
    def _movable(paths, dest):
        """Filter out sources that are already in dest, or that are dest itself /
        one of dest's ancestors (can't move a folder into itself)."""
        nd = _norm_path(dest)
        out = []
        for p in paths:
            np_ = _norm_path(p)
            if _norm_path(os.path.dirname(p)) == nd:
                continue
            if nd == np_ or nd.startswith(np_.rstrip("\\/") + os.sep):
                continue
            out.append(p)
        return out

    def _move_items(self, paths, dest_dir, dest_tree):
        if self._busy:
            return
        paths = self._movable(paths, dest_dir)
        if not paths:
            return
        parent = self._msg_parent()
        if not os.path.isdir(lp(dest_dir)):
            messagebox.showerror("Move", f"Target folder not found:\n{dest_dir}", parent=parent)
            return

        if any(not same_volume(p, dest_dir) for p in paths):
            if not messagebox.askyesno(
                    "Move to another drive",
                    f"Move {len(paths)} item(s) to another drive?\n\n→ {dest_dir}\n\n"
                    "They will be copied there and then deleted from the original "
                    "location. This can take a while.",
                    default="no", parent=parent):
                return

        plan = []   # (src, target, replace)
        for src in paths:
            name = os.path.basename(src)
            target = os.path.join(dest_dir, name)
            replace = False
            if os.path.lexists(lp(target)):
                if _norm_path(src).startswith(_norm_path(target).rstrip("\\/") + os.sep):
                    messagebox.showerror(
                        "Move", f"Can't replace '{name}': the item you're moving is inside it.",
                        parent=parent)
                    continue
                ans = messagebox.askyesnocancel(
                    "Name conflict",
                    f"'{name}' already exists in:\n{dest_dir}\n\n"
                    "Yes  = replace it (the existing one is deleted)\n"
                    "No   = skip this item\n"
                    "Cancel = abort the whole move",
                    icon="warning", parent=parent)
                if ans is None:
                    return
                if not ans:
                    continue
                replace = True
            plan.append((src, target, replace))
        if not plan:
            return

        def work():
            ok, errs = 0, []
            for src, target, replace in plan:
                try:
                    if replace:
                        remove_path(target)
                    move_path(src, target)
                    ok += 1
                except Exception as e:
                    errs.append(f"{os.path.basename(src)}: {e}")
            return ok, errs

        def done(res):
            ok, errs = res
            self.refresh_async()
            if dest_tree is not self:
                dest_tree.refresh_async()
            dname = os.path.basename(dest_dir.rstrip("\\/")) or dest_dir
            if errs:
                self._status(f"✘ Moved {ok}, {len(errs)} failed", RED, 8000)
                messagebox.showerror("Move", "Could not move:\n\n" + "\n".join(errs[:8]),
                                     parent=self._msg_parent())
            else:
                self._status(f"✔ Moved {ok} item(s) → {dname}", GREEN, 6000)

        self._status("⏳ Moving...", ORANGE)
        self._run_bg(work, done)

    # ── Drag & drop (mouse driven, multi-selection aware) ──
    def _dd_press(self, event):
        tree = self.tree
        region = tree.identify_region(event.x, event.y)
        item = tree.identify_row(event.y) if region in ("tree", "cell") else ""
        ctrl = bool(event.state & 0x0004)
        shift = bool(event.state & 0x0001)
        selected = tree.selection()
        # Pressing on an already-selected row of a multi-selection must NOT
        # collapse the selection yet (it might become a drag) — decide on release.
        defer = bool(item) and not ctrl and not shift and item in selected and len(selected) > 1
        self._dd = {"pressed": bool(item), "dragging": False, "cancelled": False,
                    "x": event.x_root, "y": event.y_root, "ghost": None,
                    "ghost_lbl": None, "paths": [], "label": "",
                    "defer_item": item if defer else None}
        tree.focus_set()
        if defer:
            return "break"

    def _dd_motion(self, event):
        d = self._dd
        block = "break" if d.get("defer_item") else None
        if not d.get("pressed") or d.get("cancelled"):
            return block
        if not d["dragging"]:
            if abs(event.x_root - d["x"]) < 8 and abs(event.y_root - d["y"]) < 8:
                return block
            paths = self.get_selected_paths()
            if not paths:
                return block
            d["dragging"] = True
            d["paths"] = paths
            d["label"] = os.path.basename(paths[0]) if len(paths) == 1 else f"{len(paths)} items"
            ghost = tk.Toplevel(self)
            ghost.overrideredirect(True)
            try:
                ghost.attributes("-topmost", True)
                ghost.attributes("-alpha", 0.9)
            except Exception:
                pass
            lbl = tk.Label(ghost, text=f"📦  {d['label']}", bg="#475569", fg=TEXT,
                           font=FONT_BOLD, padx=10, pady=5)
            lbl.pack()
            d["ghost"], d["ghost_lbl"] = ghost, lbl

        try:
            d["ghost"].geometry(f"+{event.x_root + 14}+{event.y_root + 10}")
        except Exception:
            pass
        target = self._resolve_drop(event.x_root, event.y_root)
        valid = bool(target) and bool(self._movable(d["paths"], target["dest"]))
        self._set_highlight(target if valid else None)
        try:
            if valid:
                dname = os.path.basename(target["dest"].rstrip("\\/")) or target["dest"]
                d["ghost_lbl"].config(text=f"📦  {d['label']}  →  {dname}", bg=ACCENT)
            else:
                d["ghost_lbl"].config(text=f"📦  {d['label']}", bg="#475569")
        except Exception:
            pass
        return block

    def _dd_release(self, event):
        d = self._dd
        block = "break" if d.get("defer_item") else None
        if d.get("dragging"):
            target = None if d.get("cancelled") else self._resolve_drop(event.x_root, event.y_root)
            paths = d.get("paths", [])
            self._dd_cleanup()
            if target:
                movable = self._movable(paths, target["dest"])
                if movable:
                    # let the button-release finish before any dialog grabs input
                    self.after(20, lambda: self._move_items(movable, target["dest"], target["ft"]))
        elif d.get("pressed") and d.get("defer_item") and not d.get("cancelled"):
            # plain click on a multi-selected row -> collapse to that row
            self.tree.selection_set(d["defer_item"])
            self.tree.focus(d["defer_item"])
        self._dd = {"pressed": False, "dragging": False}
        return block

    def _dd_cancel(self, event=None):
        d = getattr(self, "_dd", None)
        if d and d.get("dragging"):
            d["cancelled"] = True
            self._dd_cleanup()

    def _dd_cleanup(self):
        d = self._dd
        self._clear_highlight()
        if d.get("ghost") is not None:
            try:
                d["ghost"].destroy()
            except Exception:
                pass
            d["ghost"] = None

    def _resolve_drop(self, x_root, y_root):
        """What is under the mouse? Returns {"ft", "dest", "mode", "row", "widget"}
        or None. Modes: "row" = a folder row, "parent" = the ◀/⬆ buttons (move
        to the parent folder), "current" = anywhere else in a tree (its current folder)."""
        try:
            origin = self.winfo_containing(x_root, y_root)
        except Exception:
            return None
        w, ft = origin, None
        while w is not None:
            if isinstance(w, FileTree) and w.editable:
                ft = w
                break
            w = getattr(w, "master", None)
        if ft is None or not ft.root_path:
            return None
        dest, mode, row, widget = None, "current", None, None
        if origin is ft.tree:
            rx = x_root - ft.tree.winfo_rootx()
            ry = y_root - ft.tree.winfo_rooty()
            if ft.tree.identify_region(rx, ry) in ("tree", "cell"):
                r = ft.tree.identify_row(ry)
                p = getattr(ft.tree, "_item_paths", {}).get(r) if r else None
                if p and "dir" in ft.tree.item(r, "tags"):
                    dest, mode, row = p, "row", r
        elif origin in (ft.btn_back, ft.btn_up):
            parent = str(Path(ft.root_path).parent)
            if parent == ft.root_path:
                return None
            dest, mode, widget = parent, "parent", origin
        if dest is None:
            dest = ft.root_path
        return {"ft": ft, "dest": dest, "mode": mode, "row": row, "widget": widget}

    def _set_highlight(self, target):
        key = None
        if target:
            key = (id(target["ft"]), target["mode"], target["row"], str(target["widget"]))
        if key == self._hl_key:
            return
        self._clear_highlight()
        if not target:
            return
        ft, mode = target["ft"], target["mode"]
        try:
            if mode == "row":
                tags = [t for t in ft.tree.item(target["row"], "tags") if t != "droptarget"]
                ft.tree.item(target["row"], tags=tags + ["droptarget"])
            elif mode == "parent":
                target["widget"].config(bg=ACCENT)
            else:
                ft.config(highlightbackground=ACCENT2, highlightcolor=ACCENT2)
        except tk.TclError:
            return
        self._hl = target
        self._hl_key = key

    def _clear_highlight(self):
        t, self._hl, self._hl_key = self._hl, None, None
        if not t:
            return
        ft = t["ft"]
        try:
            if t["mode"] == "row":
                tags = [x for x in ft.tree.item(t["row"], "tags") if x != "droptarget"]
                ft.tree.item(t["row"], tags=tags)
            elif t["mode"] == "parent":
                t["widget"].config(bg=BG3)
            else:
                ft.config(highlightbackground=BG2, highlightcolor=BG2)
        except tk.TclError:
            pass  # row/widget no longer exists

    def select_paths(self, paths):
        wanted = {_norm_path(p) for p in paths}
        items = [i for i, p in getattr(self.tree, "_item_paths", {}).items()
                 if _norm_path(p) in wanted]
        if items:
            self.tree.selection_set(items)
            self.tree.focus(items[0])
            self.tree.see(items[0])

    def refresh_async(self, on_done=None):
        """Re-list the current folder on a worker thread (never blocks the UI),
        then repopulate on the main thread. Skipped if the user navigated
        elsewhere in the meantime."""
        path = self.root_path
        if not path:
            return

        def worker():
            entries = self.list_directory(path)
            try:
                self.after(0, lambda: apply(entries))
            except Exception:
                pass

        def apply(entries):
            if entries is None or self.root_path != path:
                return
            self.apply_entries(path, entries)
            if on_done:
                on_done()

        threading.Thread(target=worker, daemon=True).start()

    @staticmethod
    def list_directory(path):
        """Pure disk I/O — safe to call from a background thread. Returns a
        list of (full_path, name, is_dir, size_str, mtime_str) tuples, or
        None if the path is missing/unreadable. Does not touch any widget."""
        if not path or not os.path.exists(lp(path)):
            return None
        try:
            items = sorted(os.scandir(lp(path)), key=lambda e: (not e.is_dir(), e.name.lower()))
        except OSError:          # PermissionError, path too long, drive gone...
            return None
        result = []
        for entry in items:
            # Built from the NORMAL path (not entry.path, which would carry
            # the extended-length prefix for long folders) so selection/queue/compare
            # logic keeps working with ordinary paths.
            icon_path = os.path.join(path, entry.name)
            try:
                stat = entry.stat()
                size = format_size(stat.st_size) if entry.is_file() else ""
                mtime = datetime.fromtimestamp(stat.st_mtime).strftime("%d.%m.%y %H:%M")
            except Exception:
                size, mtime = "", ""
            result.append((icon_path, entry.name, entry.is_dir(), size, mtime))
        return result

    def apply_entries(self, path, entries):
        """Populate the tree from already-fetched entries (see
        list_directory). This is the ONLY part of a refresh that touches Tk
        widgets, so it's safe to call from the main thread after a
        background list_directory() call — used for non-blocking refreshes
        while a copy/move/sync is in progress on the same drive."""
        self.root_path = path
        self.path_var.set(path)
        self.tree.delete(*self.tree.get_children())
        self.tree._item_paths = {}
        if self.show_preview:
            self._preview_clear()
        if not entries:
            return
        for full_path, name, is_dir, size, mtime in entries:
            icon = get_item_icon(full_path)
            iid = self.tree.insert("", "end", text=f"  {icon}  {name}",
                                    values=(size, mtime),
                                    tags=("dir" if is_dir else "file",))
            self.tree._item_paths[iid] = full_path

    def load(self, path, _from_history=False):
        if not path or not os.path.exists(lp(path)):
            return
        entries = self.list_directory(path)
        if entries is None:
            return
        self.apply_entries(path, entries)

    def go_up(self):
        parent = str(Path(self.root_path).parent)
        if parent != self.root_path:
            self.load(parent)

    def refresh(self):
        self.load(self.root_path)

    def _on_double_click(self, event):
        item = self.tree.focus()
        path = getattr(self.tree, "_item_paths", {}).get(item)
        if path and os.path.isdir(lp(path)):
            self.load(path)

    def _on_select(self, event):
        if self.show_preview:
            self._preview_update_from_selection()
        if self.on_select_cb:
            items = self.tree.selection()
            paths = [getattr(self.tree, "_item_paths", {}).get(i) for i in items]
            self.on_select_cb([p for p in paths if p])

    # ── Image preview panel ───────────────────────────────────────────────
    def _build_preview(self):
        self.preview_frame = tk.Frame(self, bg=BG, width=PREVIEW_WIDTH,
                                      highlightthickness=1,
                                      highlightbackground=BORDER)
        self.preview_frame.pack_propagate(False)
        self.preview_info = tk.Label(self.preview_frame, text="", font=FONT_SMALL,
                                     fg=TEXT_DIM, bg=BG, justify="center",
                                     wraplength=PREVIEW_WIDTH - 16)
        self.preview_info.pack(side="bottom", fill="x", padx=6, pady=(2, 6))
        self.preview_label = tk.Label(self.preview_frame, text="", font=FONT_SMALL,
                                      fg=TEXT_DIM, bg=BG, bd=0)
        self.preview_label.pack(side="top", fill="both", expand=True,
                                padx=4, pady=4)
        self.preview_frame.bind("<Configure>", self._preview_on_resize)
        self._preview_clear()

    def _preview_clear(self, message="No image selected"):
        """Reset the panel to its placeholder state."""
        self._preview_token += 1
        self._preview_path = None
        self._preview_img = None
        if self._preview_job is not None:
            try:
                self.after_cancel(self._preview_job)
            except Exception:
                pass
            self._preview_job = None
        try:
            self.preview_label.config(image="", text=message)
            self.preview_info.config(text="")
        except Exception:
            pass

    def _preview_update_from_selection(self):
        sel = self.tree.selection()
        path = None
        if sel:
            focus = self.tree.focus()
            iid = focus if focus in sel else sel[-1]
            path = getattr(self.tree, "_item_paths", {}).get(iid)
        if (path and os.path.isfile(lp(path))
                and Path(path).suffix.lower() in IMAGE_EXTS):
            if path != self._preview_path:
                self._preview_request(path)
        else:
            self._preview_clear()

    def _preview_target_size(self):
        w = self.preview_frame.winfo_width()
        h = self.preview_frame.winfo_height()
        if w <= 1:
            w = PREVIEW_WIDTH
        if h <= 1:
            h = 300
        # leave room for paddings and the caption under the image
        return max(w - 16, 40), max(h - 70, 40)

    def _preview_request(self, path):
        """Debounced: fast arrow-key scrolling won't load every image."""
        self._preview_path = path
        self._preview_token += 1
        token = self._preview_token
        if self._preview_job is not None:
            try:
                self.after_cancel(self._preview_job)
            except Exception:
                pass
        self._preview_job = self.after(
            80, lambda: self._preview_start(path, token))

    def _preview_start(self, path, token):
        self._preview_job = None
        if token != self._preview_token:
            return
        size = self._preview_target_size()
        self._preview_last_size = size
        self.preview_label.config(image="", text="Loading…")
        if not PIL_AVAILABLE:
            self._preview_fallback_tk(path, size)
            return
        threading.Thread(target=self._preview_worker,
                         args=(path, size, token), daemon=True).start()

    def _preview_worker(self, path, size, token):
        """Background thread: disk I/O + decoding + resizing (no Tk calls)."""
        try:
            img = Image.open(lp(path))
            orig_w, orig_h = img.size
            fmt = img.format or ""
            try:
                img.draft("RGB", (size[0] * 2, size[1] * 2))  # fast JPEG decode
            except Exception:
                pass
            try:
                img = ImageOps.exif_transpose(img)
            except Exception:
                pass
            img = img.convert("RGBA")
            resample = getattr(getattr(Image, "Resampling", Image), "LANCZOS")
            img.thumbnail(size, resample)      # never upscales
            # flatten transparency onto the panel background
            bg = Image.new("RGBA", img.size, BG2)
            bg.alpha_composite(img)
            img = bg.convert("RGB")
            try:
                fsize = format_size(os.path.getsize(lp(path)))
            except Exception:
                fsize = ""
            info = f"{os.path.basename(path)}\n{orig_w} × {orig_h} px"
            if fsize:
                info += f"  ·  {fsize}"
            if fmt:
                info += f"  ·  {fmt}"
            result = (img, info, None)
        except Exception as exc:
            result = (None, os.path.basename(path), str(exc))
        try:
            self.after(0, lambda: self._preview_apply(token, *result))
        except Exception:
            pass  # widget destroyed

    def _preview_apply(self, token, pil_img, info, error):
        if token != self._preview_token:
            return  # selection changed while loading
        try:
            if pil_img is None:
                self._preview_img = None
                self.preview_label.config(image="", text="Cannot preview this file")
                self.preview_info.config(text=info)
                return
            self._preview_img = ImageTk.PhotoImage(pil_img)
            self.preview_label.config(image=self._preview_img, text="")
            self.preview_info.config(text=info)
        except Exception:
            pass

    def _preview_fallback_tk(self, path, size):
        """No Pillow: Tk itself can only show PNG/GIF (scaled down by integer
        factors)."""
        try:
            if Path(path).suffix.lower() not in (".png", ".gif"):
                raise ValueError("needs Pillow")
            img = tk.PhotoImage(file=path)
            f = max(1, -(-img.width() // size[0]), -(-img.height() // size[1]))
            if f > 1:
                img = img.subsample(f, f)
            self._preview_img = img
            self.preview_label.config(image=img, text="")
            self.preview_info.config(text=os.path.basename(path))
        except Exception:
            self._preview_img = None
            self.preview_label.config(
                image="", text="Install Pillow to preview this format")
            self.preview_info.config(text=os.path.basename(path))

    def _preview_on_resize(self, event):
        """Re-render when the panel is resized (window resize / maximize)."""
        if not self._preview_path:
            return
        new = (max(event.width - 16, 40), max(event.height - 70, 40))
        old = self._preview_last_size
        if abs(new[0] - old[0]) < 8 and abs(new[1] - old[1]) < 8:
            return
        self._preview_request(self._preview_path)

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
        self._avail_result_queue = queue.Queue()
        self._avail_check_running = False
        self._build()

    def _build(self):
        # Header
        header = tk.Frame(self, bg=BG3, pady=6)
        header.pack(fill="x")

        dot_color = GREEN if (self.drive_path and os.path.exists(self.drive_path)) else RED
        self.dot_label = tk.Label(header, text="●", font=("Segoe UI", 14), fg=dot_color,
                 bg=BG3)
        self.dot_label.pack(side="left", padx=(8, 4))
        self._available = bool(self.drive_path and os.path.exists(self.drive_path))

        self.title_var = tk.StringVar(value=f"Drive {self.drive_index + 1}")
        title_lbl = tk.Label(header, textvariable=self.title_var,
                              font=FONT_TITLE, fg=TEXT, bg=BG3)
        title_lbl.pack(side="left")

        select_btn = tk.Button(header, text="📂 Select", command=self.choose_drive,
                  bg=ACCENT, fg=TEXT, font=FONT_SMALL, relief="flat",
                  padx=6, pady=2, cursor="hand2")
        select_btn.pack(side="right", padx=8)

        # Operation status (copying/moving/syncing/ejecting/disconnected...).
        # Lives in the header, between the title and the Select button, so it
        # adds no extra vertical row to the panel — an earlier version used a
        # standalone row here which pushed the main window's bottom status
        # bar past the fixed window height and got clipped.
        # Kept SEPARATE from the path bar below: browsing folders during a
        # copy used to overwrite the "⏳ Copying..." message because both
        # used to share one label. This one is only ever touched by
        # set_status() (copy/move/sync/eject progress + connect/disconnect).
        self.op_status_var = tk.StringVar(value="")
        self.op_status_bar = tk.Label(header, textvariable=self.op_status_var,
                                       font=FONT_SMALL, fg=TEXT_DIM, bg=BG3,
                                       anchor="e", padx=6)
        self.op_status_bar.pack(side="right", fill="x", expand=True, padx=(12, 0))

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
        self.file_tree = FileTree(self, root_path=self.drive_path, readonly=True,
                                  editable=True, status_cb=self.set_status)
        self.file_tree.pack(fill="both", expand=True, padx=4, pady=4)

        # Path bar — always shows the current folder relative to the drive
        # root. Only touched by navigate_to_relative()/refresh()/set_drive().
        self.path_var = tk.StringVar(value="")
        self.path_bar = tk.Label(self, textvariable=self.path_var,
                                  font=FONT_SMALL, fg=TEXT_DIM, bg=BG3,
                                  anchor="w", padx=6)
        self.path_bar.pack(fill="x", side="bottom")

        self._update_info()
        # Start watching this drive for disconnects/reconnects so the file
        # listing and green dot never go stale after a drive is unplugged.
        self.after(1500, self._poll_availability)

    def choose_drive(self):
        path = filedialog.askdirectory(title=f"Select root folder for Drive {self.drive_index + 1}")
        if path:
            self.set_drive(path)

    def set_drive(self, path):
        self.drive_path = path
        self.relative_subpath = ""
        self.path_var.set("")
        self.config["drives"][self.drive_index] = path
        save_config(self.config)
        self._available = bool(path and os.path.exists(path))
        self.dot_label.config(fg=GREEN if self._available else RED)
        self.file_tree.load(path)
        self._update_info()

    def _poll_availability(self):
        """Runs every ~1.5s ON THE MAIN THREAD, but never touches the disk
        itself — that's delegated to a background worker (see
        _availability_worker) because os.path.exists()/disk_usage() on a
        drive letter that's mid-mount/spinning up can block for seconds on
        Windows, which would otherwise freeze the whole UI."""
        try:
            while True:
                exists, total, used, free = self._avail_result_queue.get_nowait()
                self._apply_availability(exists, total, used, free)
        except queue.Empty:
            pass
        if not self._avail_check_running:
            self._avail_check_running = True
            threading.Thread(target=self._availability_worker, daemon=True).start()
        try:
            self.after(1500, self._poll_availability)
        except Exception:
            pass  # widget destroyed

    def _availability_worker(self):
        """Background thread: all potentially-blocking disk I/O happens
        here. Never touches Tk widgets directly — only pushes results
        onto a thread-safe queue for the main thread to pick up."""
        path = self.drive_path
        exists = bool(path) and os.path.exists(path)
        total = used = free = None
        if exists:
            total, used, free = get_drive_info(path)
        try:
            self._avail_result_queue.put((exists, total, used, free))
        finally:
            self._avail_check_running = False

    def _apply_availability(self, exists, total, used, free):
        """Runs on the main thread. Cheap — just updates widgets."""
        if exists != self._available:
            self._available = exists
            if exists:
                self.dot_label.config(fg=GREEN)
                self.file_tree.load(self.drive_path)
                self.set_status("✔ Reconnected", GREEN)
            else:
                self.dot_label.config(fg=RED)
                self.file_tree.tree.delete(*self.file_tree.tree.get_children())
                self.file_tree.path_var.set("")
                self.set_status("✘ Disconnected", RED)
        if exists and total:
            pct = (used / total) * 100
            self.progress["value"] = pct
            self.info_label.config(
                text=f"Free: {format_size(free)}  |  Used: {format_size(used)}  |  Total: {format_size(total)}",
                fg=TEXT
            )
            short = os.path.splitdrive(self.drive_path)[0] or self.drive_path[:20]
            self.title_var.set(f"Drive {self.drive_index + 1}  ({short})")
        elif not exists:
            self.info_label.config(text="— no drive —", fg=TEXT_DIM)
            self.progress["value"] = 0
            self.title_var.set(f"Drive {self.drive_index + 1}")

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
            self.path_var.set(f"📂 {rel_subpath or '(root)'}")
            self.path_bar.config(fg=TEXT_DIM)
        else:
            self.path_var.set(f"✘ missing: {rel_subpath}")
            self.path_bar.config(fg=RED)

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
            self.title_var.set(f"Drive {self.drive_index + 1}")

    def refresh(self):
        self._update_info()
        if self.drive_path and os.path.exists(self.drive_path):
            self._available = True
            self.dot_label.config(fg=GREEN)
            self.file_tree.refresh()
        else:
            self._available = False
            self.dot_label.config(fg=RED)
            self.file_tree.tree.delete(*self.file_tree.tree.get_children())
            self.file_tree.path_var.set("")

    def refresh_async(self):
        """Non-blocking refresh: shutil.disk_usage() and the directory
        listing both do real disk I/O, which can stall for a long time (or
        effectively forever) if another operation is actively copying to
        the same drive. refresh() ran that I/O directly on the main thread,
        so clicking "Refresh drives" mid-copy could freeze the whole app.
        This does the I/O on a worker thread and only touches widgets in
        _apply_refresh(), scheduled back onto the main thread via after() —
        same pattern as _availability_worker. Safe to call from any thread."""
        if getattr(self, "_refresh_running", False):
            return
        self._refresh_running = True
        drive_path = self.drive_path
        listing_path = self.file_tree.root_path or drive_path
        threading.Thread(target=self._refresh_worker,
                          args=(drive_path, listing_path), daemon=True).start()

    def _refresh_worker(self, drive_path, listing_path):
        exists = bool(drive_path) and os.path.exists(drive_path)
        total = used = free = None
        if exists:
            total, used, free = get_drive_info(drive_path)
        entries = FileTree.list_directory(listing_path) if exists else None
        self.after(0, self._apply_refresh, exists, total, used, free, listing_path, entries)

    def _apply_refresh(self, exists, total, used, free, listing_path, entries):
        self._refresh_running = False
        self._available = exists
        self.dot_label.config(fg=GREEN if exists else RED)
        if exists and total:
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
            self.title_var.set(f"Drive {self.drive_index + 1}")
        if exists:
            if entries is not None:
                self.file_tree.apply_entries(listing_path, entries)
        else:
            self.file_tree.tree.delete(*self.file_tree.tree.get_children())
            self.file_tree.path_var.set("")

    def set_status(self, msg, color=TEXT_DIM):
        """Operation status (copying/moving/syncing/ejecting/connect state).
        Separate from the path bar so it can't be clobbered by folder
        navigation happening at the same time (see _sync_drive_panels)."""
        self.op_status_var.set(msg)
        self.op_status_bar.config(fg=color)


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
        self._op_gen = 0              # bumped per operation / force-release
        self._op_cancel = None        # threading.Event of the running operation
        self._stop_requested = False
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
        self._src_frame = src_frame

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

        # Row 1: drives 1..MAIN_DRIVES (same row as "Custom path")
        # Row 2: drives MAIN_DRIVES+1..NUM_DRIVES (extra drives, own row)
        src_frame2 = tk.Frame(self, bg=BG2, pady=0, padx=8)
        tk.Label(src_frame2, text="", font=FONT_BOLD, bg=BG2).pack(
            side="left", padx=(0, 6))  # spacer to align with "SOURCE:" above

        self.drive_rbs = []
        for i in range(NUM_DRIVES):
            drv = self.config["drives"][i]
            lbl = os.path.splitdrive(drv)[0] if drv else f"Drive {i+1}"
            row = src_frame if i < MAIN_DRIVES else src_frame2
            rb = tk.Radiobutton(row, text=lbl,
                                 variable=self.src_mode, value=f"drive{i}",
                                 command=self._on_src_mode_change,
                                 bg=BG2, fg=TEXT_DIM, selectcolor=BG2,
                                 activebackground=BG2, activeforeground=TEXT,
                                 font=FONT_SMALL, cursor="hand2",
                                 relief="flat", bd=0)
            rb.pack(side="left", padx=2)
            self.drive_rbs.append(rb)
        if any(self.config["drives"][MAIN_DRIVES:NUM_DRIVES]):
            src_frame2.pack(fill="x", padx=6, pady=(0, 5))
        self._src_frame2 = src_frame2

        # Custom path entry row
        path_row = tk.Frame(self, bg=BG2, pady=3, padx=8)
        path_row.pack(fill="x", padx=6)
        self.src_var = tk.StringVar(value=self.config.get("source_path", str(Path.home())))
        self.src_entry = tk.Entry(path_row, textvariable=self.src_var, font=FONT_MONO,
                                   bg=BG, fg=TEXT, insertbackground=TEXT,
                                   readonlybackground=BG, disabledbackground=BG,
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
                                     on_select=self._on_source_select,
                                     on_new_folder=self._create_new_folder_everywhere,
                                     show_preview=True)
        self.source_tree.tree.bind("<Double-1>", self._on_source_navigate, add="+")
        self.source_tree.tree.bind("<Button-3>", self._source_context_menu)
        self._orig_go_up = self.source_tree.go_up
        self.source_tree.go_up = self._go_up_synced
        self._patch_source_tree_toolbar()
        self.source_tree.pack(fill="both", expand=True)

        # Drop queue panel (replaces old tiny drop bar)
        self._build_drop_queue(right)

        # Allow dragging items directly from the Control Panel file preview
        # into the Drop Zone (same as dragging from Explorer)
        self._setup_internal_drag()

        # ── Destination checkboxes ────────────
        dest_frame = tk.Frame(self, bg=BG2, pady=5, padx=12)
        dest_frame.pack(fill="x", padx=6, pady=(2, 0))
        self._dest_frame = dest_frame
        tk.Label(dest_frame, text="COPY TO:", font=FONT_BOLD, fg=TEXT_DIM,
                 bg=BG2).pack(side="left", padx=(0, 10))

        # Second row for extra drives (5..NUM_DRIVES), created below dest_frame
        dest_frame2 = tk.Frame(self, bg=BG2, pady=0, padx=12)
        tk.Label(dest_frame2, text="", font=FONT_BOLD, bg=BG2).pack(
            side="left", padx=(0, 10))  # spacer to align with "COPY TO:"

        self.dest_vars = []
        self.dest_cbs  = []
        for i in range(NUM_DRIVES):
            var = tk.BooleanVar(value=True)
            self.dest_vars.append(var)
            drv = self.config["drives"][i]
            label = os.path.splitdrive(drv)[0] if drv else f"Drive {i+1}"
            row = dest_frame if i < MAIN_DRIVES else dest_frame2
            cb = tk.Checkbutton(row, text=label, variable=var,
                                 bg=BG2, fg=TEXT, selectcolor=BG2,
                                 activebackground=BG2, activeforeground=TEXT,
                                 font=FONT_MAIN, cursor="hand2",
                                 relief="flat", bd=0)
            cb.pack(side="left", padx=6)
            self.dest_cbs.append(cb)

        # Only show the extra-drives row once any of drives 5..8 are configured
        if any(self.config["drives"][MAIN_DRIVES:NUM_DRIVES]):
            dest_frame2.pack(fill="x", padx=6, pady=(0, 5))
        self._dest_frame2 = dest_frame2

        # ── Action buttons ────────────────────
        btn_frame = tk.Frame(self, bg=BG, pady=5)
        btn_frame.pack(fill="x", padx=6)
        self.copy_btn = styled_button(btn_frame, "📋  COPY SELECTED",
                                       self._copy_selected, GREEN)
        self.copy_btn.pack(side="left", padx=(0, 6))
        self.move_btn = styled_button(btn_frame, "✂  MOVE SELECTED",
                                       self._move_selected, "#f97316")
        self.move_btn.pack(side="left", padx=(0, 6))
        self.delete_btn = styled_button(btn_frame, "🗑  DELETE from drives",
                      self._delete_selected, RED)
        self.delete_btn.pack(side="left", padx=(0, 6))
        self.sync_btn = styled_button(btn_frame, "🔄 SYNC folder",
                                      self._sync_all, ORANGE)
        self.sync_btn.pack(side="left", padx=(0, 6))
        self.progress_var = tk.DoubleVar()
        self.prog_bar = ttk.Progressbar(btn_frame, variable=self.progress_var,
                                         maximum=100, length=150, mode="determinate")
        self.prog_bar.pack(side="right", padx=6)
        # STOP ALL — sits left of the progress bar; only active while an
        # operation runs (see _set_ops_ui / _stop_all).
        self.stop_btn = tk.Button(
            btn_frame, text="⛔  STOP ALL", command=self._stop_all,
            bg=BG3, fg=TEXT_DIM, disabledforeground=TEXT_DIM,
            activebackground="#b91c1c", activeforeground=TEXT,
            font=FONT_BOLD, relief="flat", bd=0, padx=12, pady=6,
            state="disabled")
        self.stop_btn.pack(side="right", padx=6)

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
        # Show the "extra drives" rows only once any of drives 5..8 are configured
        extra_configured = any(self.config["drives"][MAIN_DRIVES:NUM_DRIVES])
        if extra_configured:
            if not self._src_frame2.winfo_ismapped():
                self._src_frame2.pack(fill="x", padx=6, pady=(0, 5), after=self._src_frame)
            if not self._dest_frame2.winfo_ismapped():
                self._dest_frame2.pack(fill="x", padx=6, pady=(0, 5), after=self._dest_frame)
        else:
            self._src_frame2.pack_forget()
            self._dest_frame2.pack_forget()

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
            icon = "📁" if os.path.isdir(lp(p)) else get_item_icon(p)
            exists = os.path.exists(lp(p))
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

        # Keep _selected_paths in sync so COPY always uses queue
        self._selected_paths = list(self._queue_items)

    # ══════════════════════════════════════════
    # INTERNAL DRAG & DROP (Control Panel preview → Drop Zone)
    # ══════════════════════════════════════════
    def _setup_internal_drag(self):
        """
        Lets the user drag items straight out of the Control Panel's own
        file preview (self.source_tree) and drop them onto the Drop Zone —
        exactly like dragging from Windows Explorer, but internal to the app.
        """
        self._src_drag = {"pressed": False, "dragging": False}
        tree = self.source_tree.tree
        tree.bind("<ButtonPress-1>", self._src_drag_press, add="+")
        tree.bind("<B1-Motion>", self._src_drag_motion, add="+")
        tree.bind("<ButtonRelease-1>", self._src_drag_release, add="+")

    def _src_drag_press(self, event):
        tree = self.source_tree.tree
        item = tree.identify_row(event.y)
        ctrl = bool(event.state & 0x0004)
        shift = bool(event.state & 0x0001)
        selected = tree.selection()
        # If the user pressed down on an item that's already part of a
        # multi-selection (no Ctrl/Shift), defer Treeview's default behavior
        # (which would otherwise instantly collapse the selection to just
        # this item) until we know if this turns into a click or a drag —
        # same as Explorer's "click-and-drag a multi-selection" behavior.
        defer = bool(item) and not ctrl and not shift and item in selected and len(selected) > 1
        self._src_drag = {
            "pressed": True, "dragging": False,
            "x": event.x_root, "y": event.y_root, "ghost": None, "paths": [],
            "defer_item": item if defer else None,
        }
        if defer:
            return "break"

    def _src_drag_motion(self, event):
        d = getattr(self, "_src_drag", None)
        if not d or not d.get("pressed"):
            return
        block_default = bool(d.get("defer_item"))
        if not d["dragging"]:
            dx = abs(event.x_root - d["x"])
            dy = abs(event.y_root - d["y"])
            if dx < 8 and dy < 8:
                return "break" if block_default else None
            paths = self.source_tree.get_selected_paths()
            if not paths:
                return "break" if block_default else None
            d["dragging"] = True
            d["paths"] = paths
            count = len(paths)
            label = os.path.basename(paths[0]) if count == 1 else f"{count} items"
            ghost = tk.Toplevel(self)
            ghost.overrideredirect(True)
            try:
                ghost.attributes("-topmost", True)
                ghost.attributes("-alpha", 0.88)
            except Exception:
                pass
            tk.Label(ghost, text=f"📦  {label}", bg=ACCENT, fg=TEXT,
                     font=FONT_BOLD, padx=10, pady=5).pack()
            d["ghost"] = ghost

        if d["dragging"] and d["ghost"] is not None:
            try:
                d["ghost"].geometry(f"+{event.x_root + 14}+{event.y_root + 10}")
            except Exception:
                pass
            target = self._widget_under_point(event.x_root, event.y_root)
            if self._is_drop_zone_widget(target):
                self.drop_surface.config(highlightbackground=ACCENT, bg="#1a2540")
                self.drop_placeholder.config(fg=ACCENT2, bg="#1a2540")
                self.queue_listbox.config(bg="#1a2540")
            else:
                self._queue_reset_surface()
        return "break" if block_default else None

    def _src_drag_release(self, event):
        d = getattr(self, "_src_drag", None)
        if not d:
            return
        block_default = bool(d.get("defer_item"))
        if d.get("dragging"):
            target = self._widget_under_point(event.x_root, event.y_root)
            if self._is_drop_zone_widget(target):
                added = 0
                for p in d.get("paths", []):
                    if p and p not in self._queue_items:
                        self._queue_items.append(p)
                        added += 1
                self._queue_refresh()
                if added:
                    self.log.log(
                        f"⬇ Dragged {added} item(s) from Control Panel preview into Drop Zone",
                        "info"
                    )
            self._queue_reset_surface()
            if d.get("ghost") is not None:
                try:
                    d["ghost"].destroy()
                except Exception:
                    pass
        elif block_default and d.get("defer_item"):
            # It was just a plain click (no drag) on an item that was part of
            # a multi-selection — now collapse the selection to that single
            # item, mimicking the default behavior we suppressed on press.
            tree = self.source_tree.tree
            item = d["defer_item"]
            tree.selection_set(item)
            tree.focus(item)
        self._src_drag = {"pressed": False, "dragging": False}
        return "break" if block_default else None

    def _widget_under_point(self, x_root, y_root):
        try:
            return self.winfo_containing(x_root, y_root)
        except Exception:
            return None

    def _is_drop_zone_widget(self, widget):
        if widget is None:
            return False
        w = widget
        for _ in range(10):
            if w is None:
                return False
            if w in (self.drop_surface, self.queue_listbox, self.drop_placeholder):
                return True
            try:
                w = w.master
            except Exception:
                return False
        return False

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

    def _source_context_menu(self, event):
        """Right-click on the source tree: Rename (single item) / Remove (any selection).
        Both actions apply to the selected item(s) AND their counterparts on all
        active destination drives."""
        tree = self.source_tree.tree
        item = tree.identify_row(event.y)
        if not item:
            return
        # If the right-clicked row isn't part of the current selection, select just it.
        if item not in tree.selection():
            tree.selection_set(item)
        paths = self.source_tree.get_selected_paths()
        if not paths:
            return
        menu = tk.Menu(self, tearoff=0, bg=BG2, fg=TEXT,
                        activebackground=ACCENT, activeforeground=TEXT,
                        relief="flat", bd=0)
        if len(paths) == 1:
            menu.add_command(label="✎  Rename", command=self._source_rename_selected)
            menu.add_separator()
        menu.add_command(label="✕  Remove", command=self._source_remove_selected)
        menu.tk_popup(event.x_root, event.y_root)

    def _source_rename_selected(self):
        """Rename the single selected source item, then rename its counterpart
        (matched by old name) on every active destination drive."""
        paths = self.source_tree.get_selected_paths()
        if len(paths) != 1:
            return
        src = paths[0]
        old_name = os.path.basename(src)
        new_name = self._ask_name("New name", old_name)
        if not new_name or new_name == old_name:
            return
        parent_dir = os.path.dirname(src)
        new_src = os.path.join(parent_dir, new_name)
        if os.path.exists(lp(new_src)):
            messagebox.showerror("Rename", f"'{new_name}' already exists in this folder.")
            return
        try:
            os.rename(lp(src), lp(new_src))
            self.log.log(f"✎ Renamed source: {old_name} → {new_name}", "ok")
        except Exception as e:
            self.log.log(f"✘ Rename error (source) {old_name}: {e}", "err")
            messagebox.showerror("Rename", f"Could not rename source item:\n{e}")
            return

        for drive_idx, drive_root in self._get_active_drives():
            panel = self.drive_panels[drive_idx]
            rel = panel.relative_subpath
            dest_folder = os.path.join(drive_root, rel) if rel else drive_root
            old_target = os.path.join(dest_folder, old_name)
            new_target = os.path.join(dest_folder, new_name)
            if os.path.exists(lp(old_target)):
                try:
                    if os.path.exists(lp(new_target)):
                        remove_path(new_target)
                    os.rename(lp(old_target), lp(new_target))
                    self.log.log(f"✎ Renamed on Drive {drive_idx+1}: {old_name} → {new_name}", "ok")
                except Exception as e:
                    self.log.log(f"✘ Rename error on Drive {drive_idx+1}: {e}", "err")
            panel.refresh_async()

        self._selected_paths = []
        self.source_tree.refresh()

    def _source_remove_selected(self):
        """Remove the selected item(s) from the source folder AND from every
        active destination drive (matched by name)."""
        paths = self.source_tree.get_selected_paths()
        if not paths:
            return
        drives = self._get_active_drives()
        names = [os.path.basename(p) for p in paths]
        msg = f"Remove {len(names)} item(s)?\n\n" + "\n".join(names[:8])
        if len(names) > 8:
            msg += f"\n... and {len(names) - 8} more"
        msg += "\n\n⚠ This deletes them from the source folder"
        msg += f" and from {len(drives)} active drive(s)." if drives else "."
        if not messagebox.askyesno("Confirm remove", msg):
            return

        removed = 0
        for src in paths:
            name = os.path.basename(src)
            try:
                if os.path.isdir(lp(src)) or os.path.isfile(lp(src)):
                    remove_path(src)
                removed += 1
                self.log.log(f"🗑 {name} removed from source", "warn")
            except Exception as e:
                self.log.log(f"✘ Remove error {name} (source): {e}", "err")

            for drive_idx, drive_root in drives:
                panel = self.drive_panels[drive_idx]
                rel = panel.relative_subpath
                dest_folder = os.path.join(drive_root, rel) if rel else drive_root
                target = os.path.join(dest_folder, name)
                try:
                    if os.path.isdir(lp(target)):
                        remove_path(target)
                        self.log.log(f"🗑 {name} removed from Drive {drive_idx+1}", "warn")
                    elif os.path.isfile(lp(target)):
                        remove_path(target)
                        self.log.log(f"🗑 {name} removed from Drive {drive_idx+1}", "warn")
                except Exception as e:
                    self.log.log(f"✘ Remove error {name} on Drive {drive_idx+1}: {e}", "err")

        for drive_idx, _ in drives:
            self.drive_panels[drive_idx].refresh_async()

        self._selected_paths = []
        self.source_tree.refresh()
        self.log.log(f"Remove complete: {removed} item(s) removed.", "ok")

    def _create_new_folder_everywhere(self):
        """Create a new folder in the currently browsed source directory,
        and mirror it into the same relative location on every active
        destination drive."""
        current_dir = self.source_tree.root_path
        if not current_dir or not os.path.isdir(lp(current_dir)):
            messagebox.showerror("New folder", "No valid source folder is open.")
            return
        name = self._ask_name("New folder name", "New Folder")
        if not name:
            return
        # Guard against path separators / illegal names sneaking in
        if any(c in name for c in '\\/:*?"<>|'):
            messagebox.showerror("New folder", "Folder name contains invalid characters.")
            return

        new_path = os.path.join(current_dir, name)
        if os.path.exists(lp(new_path)):
            messagebox.showerror("New folder", f"'{name}' already exists here.")
            return

        try:
            os.makedirs(lp(new_path))
            self.log.log(f"📁 Created folder: {name} (source)", "ok")
        except Exception as e:
            self.log.log(f"✘ Could not create folder (source): {e}", "err")
            messagebox.showerror("New folder", f"Could not create folder:\n{e}")
            return

        created, failed = 0, 0
        for drive_idx, drive_root in self._get_active_drives():
            panel = self.drive_panels[drive_idx]
            rel = panel.relative_subpath
            dest_folder = os.path.join(drive_root, rel) if rel else drive_root
            target = os.path.join(dest_folder, name)
            try:
                os.makedirs(lp(target), exist_ok=True)
                created += 1
                self.log.log(f"📁 Created folder: {name} → Drive {drive_idx+1}", "ok")
            except Exception as e:
                failed += 1
                self.log.log(f"✘ Could not create folder on Drive {drive_idx+1}: {e}", "err")
            panel.refresh_async()

        self.source_tree.refresh()
        summary = f"Folder '{name}' created."
        if created or failed:
            summary += f" ({created} drive(s) ok"
            summary += f", {failed} failed)" if failed else ")"
        self.log.log(summary, "ok" if not failed else "warn")

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
        # refresh_async: refresh() blocks on disk I/O and would freeze the
        # whole app if a drive is busy from an ongoing copy/move/sync — this
        # is the exact "Refresh Drives freezes the app mid-copy" bug.
        for panel in self.drive_panels:
            panel.refresh_async()
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
    def _ui(self, fn, *args, **kwargs):
        """Schedule a Tk widget update from a background thread.
        Tk/Tcl is NOT thread-safe: calling widget methods directly from a
        worker thread (e.g. self.log.log(...), panel.set_status(...),
        messagebox.showinfo(...)) races with the main thread's event loop
        and can freeze the whole app with no error, especially while the
        user is interacting with the UI at the same time (e.g. browsing
        folders). Everything that touches a widget from _do_copy/_do_move/
        _do_sync/_do_eject must go through here instead — same pattern as
        _availability_worker uses via its queue.

        Calls from a worker that was force-released (STOP ALL pressed twice)
        are dropped, so a thread that wakes up later can't scribble over the
        UI of a newer operation."""
        gen = getattr(threading.current_thread(), "op_gen", None)
        if gen is not None and gen != self._op_gen:
            return
        try:
            self.after(0, lambda: fn(*args, **kwargs))
        except Exception:
            pass  # widget destroyed

    # ── Operation runner / STOP ALL ───────────
    def _cur_cancel(self):
        """Cancel flag of the operation running on the CURRENT worker thread."""
        return getattr(threading.current_thread(), "cancel_event", None) or threading.Event()

    def _set_ops_ui(self, running):
        for b in (self.copy_btn, self.move_btn, self.delete_btn, self.sync_btn):
            b.config(state="disabled" if running else "normal")
        if running:
            self.stop_btn.config(state="normal", text="⛔  STOP ALL",
                                 bg="#dc2626", fg=TEXT, cursor="hand2")
        else:
            self.stop_btn.config(state="disabled", text="⛔  STOP ALL",
                                 bg=BG3, fg=TEXT_DIM, cursor="arrow")

    def _start_op(self, target, *args):
        """Run target(*args) on a worker thread with a cancel flag, and
        finalise the UI (buttons, statuses, refresh) in ONE place."""
        self._op_gen += 1
        gen = self._op_gen
        cancel = threading.Event()
        self._op_cancel = cancel
        self._stop_requested = False
        self._copying = True
        self.progress_var.set(0)
        self._set_ops_ui(True)

        def runner():
            th = threading.current_thread()
            th.op_gen = gen
            th.cancel_event = cancel
            outcome, payload = "done", None
            try:
                payload = target(*args)
            except OperationCancelled:
                outcome = "cancelled"
            except Exception as e:
                outcome, payload = "error", e
            try:
                self.after(0, lambda: self._finish_op(gen, outcome, payload))
            except Exception:
                pass  # widget destroyed

        threading.Thread(target=runner, daemon=True).start()

    def _mark_interrupted_panels(self):
        for p in self.drive_panels:
            if p.op_status_var.get().startswith("⏳"):
                p.set_status("⛔ Stopped", ORANGE)

    def _finish_op(self, gen, outcome, payload):
        if gen != self._op_gen:
            return      # this worker was force-released earlier — ignore it
        self._copying = False
        self._op_cancel = None
        self._stop_requested = False
        self._set_ops_ui(False)
        if outcome == "cancelled":
            self.progress_var.set(0)
            self._mark_interrupted_panels()
            self.log.log("⛔ Operation stopped by user.", "warn")
        elif outcome == "error":
            self.progress_var.set(0)
            self._mark_interrupted_panels()
            self.log.log(f"✘ Operation failed: {payload}", "err")
        else:
            self.progress_var.set(100)
        for p in self.drive_panels:
            p.refresh_async()
        try:
            self.source_tree.refresh()
        except Exception:
            pass
        if outcome == "done" and payload:
            messagebox.showinfo(*payload)

    def _stop_all(self):
        """1st click: ask the worker to stop (checked between files and
        every 1 MB while copying a file). 2nd click (FORCE STOP): release
        the UI immediately even if the worker is stuck inside a blocking
        call on a hung drive."""
        if not self._copying or self._op_cancel is None:
            return
        if not self._stop_requested:
            self._stop_requested = True
            self._op_cancel.set()
            self.log.log("⛔ Stop requested – finishing the current chunk…", "warn")
            self.stop_btn.config(text="⚠  FORCE STOP", bg="#7f1d1d")
            gen = self._op_gen
            self.after(4000, lambda: self._stop_hint(gen))
        else:
            self._force_release()

    def _stop_hint(self, gen):
        if gen == self._op_gen and self._copying and self._stop_requested:
            self.log.log("Still stopping – a drive is probably not responding. "
                         "Press FORCE STOP to release the app.", "warn")

    def _force_release(self):
        self._op_gen += 1               # orphan the stuck worker thread
        if self._op_cancel is not None:
            self._op_cancel.set()       # it exits as soon as it wakes up
        self._op_cancel = None
        self._copying = False
        self._stop_requested = False
        self._set_ops_ui(False)
        self.progress_var.set(0)
        self._mark_interrupted_panels()
        self.log.log("⚠ FORCE STOP: the app was released, but the worker is "
                     "blocked in a drive I/O call. Check the drive/cable, use "
                     "Refresh Drives, and avoid starting a new copy to the "
                     "same drive until it responds again.", "err")

    def _clear_all_drive_statuses(self):
        """Clear the operation-status text ('✔ Done', '✔ Synced', ...) on
        EVERY drive panel, not just the ones in this operation's active
        drive list. Without this, a panel left out of a new copy/move/
        delete/sync (e.g. its checkbox got unticked) keeps showing the
        leftover status from the previous operation forever — including
        while a different drive is actively "⏳ Copying...". Must run via
        self._ui() since this is always called from a background thread."""
        for panel in self.drive_panels:
            self._ui(panel.set_status, "", TEXT_DIM)

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
        self._start_op(self._do_copy, paths, drives)

    def _do_copy(self, src_paths, drives):
        # Runs on a worker thread started by _start_op (which already set
        # _copying / disabled buttons and finalises the UI afterwards).
        # No Tk widget may be touched directly — use self._ui(...).
        cancel = self._cur_cancel()
        self._clear_all_drive_statuses()
        total = len(src_paths) * len(drives)
        done  = 0
        self._ui(self.log.log, f"Copying: {len(src_paths)} item(s) → {len(drives)} drive(s)", "info")
        for drive_idx, drive_root in drives:
            check_cancel(cancel)
            panel = self.drive_panels[drive_idx]
            self._ui(panel.set_status, "⏳ Copying...", ORANGE)
            rel = panel.relative_subpath
            dest_folder = os.path.join(drive_root, rel) if rel else drive_root
            os.makedirs(lp(dest_folder), exist_ok=True)
            last_refresh = 0
            for src in src_paths:
                check_cancel(cancel)
                if not src:
                    continue
                name = os.path.basename(src)
                dest = os.path.join(dest_folder, name)
                try:
                    if os.path.isdir(lp(src)):
                        if os.path.exists(lp(dest)):
                            remove_path_cancellable(dest, cancel)
                        copytree_cancellable(src, dest, cancel)
                    else:
                        copy_file_cancellable(src, dest, cancel)
                    self._ui(self.log.log, f"✔ {name} → Drive {drive_idx+1}", "ok")
                except OperationCancelled:
                    self._ui(self.log.log,
                             f"⛔ Interrupted while copying {name} → Drive {drive_idx+1} "
                             f"(an incomplete copy may remain there)", "warn")
                    raise
                except Exception as e:
                    self._ui(self.log.log, f"✘ {name} → Drive {drive_idx+1}: {e}", "err")
                done += 1
                self._ui(self.progress_var.set, (done / total) * 100)
                now = time.time()
                if now - last_refresh > 0.75:
                    panel.refresh_async()
                    last_refresh = now
            self._ui(panel.set_status, "✔ Done", GREEN)
            panel.refresh_async()
        self._ui(self.log.log, "Copy complete!", "ok")
        return ("Done", "Copy completed successfully!")

    def _move_selected(self):
        if self._copying:
            self.log.log("Operation in progress – please wait!", "warn")
            return
        # Priority: drop queue > tree selection (works from Explorer path,
        # from a custom path, AND from any of the 4 drives selected as source)
        if hasattr(self, '_queue_items') and self._queue_items:
            paths = list(self._queue_items)
        else:
            paths = self._selected_paths
        if not paths:
            messagebox.showwarning("Nothing to move",
                "Add files/folders to the Drop Zone\nor select them in the preview above.")
            return
        drives = self._get_active_drives()
        if not drives:
            messagebox.showerror("No drives", "No active destination drives.")
            return
        names = [os.path.basename(p) for p in paths]
        msg = (f"Move {len(names)} item(s) to {len(drives)} drive(s)?\n\n"
               + "\n".join(names[:8]))
        if len(names) > 8:
            msg += f"\n... and {len(names) - 8} more"
        msg += "\n\n⚠ Original files will be REMOVED from the source after copying."
        if not messagebox.askyesno("Confirm move", msg):
            return
        self._start_op(self._do_move, paths, drives)

    def _do_move(self, src_paths, drives):
        # Worker thread (see _do_copy). Originals are removed ONLY after every
        # copy finished, so stopping during the copy phase never loses data.
        cancel = self._cur_cancel()
        self._clear_all_drive_statuses()
        total = len(src_paths) * len(drives)
        done = 0
        failed_sources = set()
        same_target_sources = set()
        self._ui(self.log.log, f"Moving: {len(src_paths)} item(s) → {len(drives)} drive(s)", "info")
        for drive_idx, drive_root in drives:
            check_cancel(cancel)
            panel = self.drive_panels[drive_idx]
            self._ui(panel.set_status, "⏳ Moving...", ORANGE)
            rel = panel.relative_subpath
            dest_folder = os.path.join(drive_root, rel) if rel else drive_root
            os.makedirs(lp(dest_folder), exist_ok=True)
            last_refresh = 0
            for src in src_paths:
                check_cancel(cancel)
                if not src:
                    continue
                name = os.path.basename(src)
                dest = os.path.join(dest_folder, name)
                # Moving a folder/file onto itself (source == destination drive/path) — skip copy step
                try:
                    same_target = os.path.exists(lp(src)) and os.path.exists(lp(dest)) and \
                                  os.path.samefile(lp(src), lp(dest))
                except Exception:
                    same_target = False
                try:
                    if same_target:
                        same_target_sources.add(src)
                        self._ui(self.log.log, f"↷ {name}: already on Drive {drive_idx+1}, skipping copy", "warn")
                    elif os.path.isdir(lp(src)):
                        if os.path.exists(lp(dest)):
                            remove_path_cancellable(dest, cancel)
                        copytree_cancellable(src, dest, cancel)
                        self._ui(self.log.log, f"✔ {name} → Drive {drive_idx+1}", "ok")
                    else:
                        copy_file_cancellable(src, dest, cancel)
                        self._ui(self.log.log, f"✔ {name} → Drive {drive_idx+1}", "ok")
                except OperationCancelled:
                    self._ui(self.log.log,
                             f"⛔ Interrupted while copying {name} → Drive {drive_idx+1}. "
                             f"Originals were NOT removed.", "warn")
                    raise
                except Exception as e:
                    self._ui(self.log.log, f"✘ {name} → Drive {drive_idx+1}: {e}", "err")
                    failed_sources.add(src)
                done += 1
                self._ui(self.progress_var.set, (done / total) * 100)
                now = time.time()
                if now - last_refresh > 0.75:
                    panel.refresh_async()
                    last_refresh = now
            self._ui(panel.set_status, "✔ Done", GREEN)
            panel.refresh_async()

        # Remove originals — only for items that copied successfully to ALL drives
        removed = 0
        for src in src_paths:
            if not src or src in failed_sources:
                continue
            if src in same_target_sources:
                self._ui(
                    self.log.log,
                    f"↷ Keeping source (already the copy on a destination drive): "
                    f"{os.path.basename(src)}", "warn"
                )
                continue
            try:
                check_cancel(cancel)
                remove_path_cancellable(src, cancel)
                removed += 1
                self._ui(self.log.log, f"✂ Removed source: {os.path.basename(src)}", "warn")
            except OperationCancelled:
                self._ui(self.log.log,
                         f"⛔ Stopped while removing originals (copies on the drives are complete; "
                         f"{os.path.basename(src)} may be partially removed).", "warn")
                raise
            except Exception as e:
                self._ui(self.log.log, f"✘ Could not remove source {os.path.basename(src)}: {e}", "err")

        # Clean up queue/selection
        def _finish_move():
            if hasattr(self, '_queue_items'):
                self._queue_items = [p for p in self._queue_items if p in failed_sources]
                self._queue_refresh()
            self._selected_paths = []
        self._ui(_finish_move)
        self._ui(self.log.log, f"Move complete! {removed} item(s) moved.", "ok")
        return ("Done", "Move completed successfully!")

    def _delete_selected(self):
        if self._copying:
            self.log.log("Operation in progress – please wait!", "warn")
            return
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
        self._start_op(self._do_delete, paths, drives)

    def _do_delete(self, paths, drives):
        # Worker thread (see _do_copy).
        cancel = self._cur_cancel()
        self._clear_all_drive_statuses()
        for drive_idx, drive_root in drives:
            check_cancel(cancel)
            panel = self.drive_panels[drive_idx]
            self._ui(panel.set_status, "⏳ Deleting...", ORANGE)
            rel = panel.relative_subpath
            dest_folder = os.path.join(drive_root, rel) if rel else drive_root
            last_refresh = 0
            for src in paths:
                check_cancel(cancel)
                name = os.path.basename(src)
                target = os.path.join(dest_folder, name)
                try:
                    if os.path.isdir(lp(target)) or os.path.isfile(lp(target)):
                        remove_path_cancellable(target, cancel)
                        self._ui(self.log.log, f"🗑 {name} deleted from Drive {drive_idx+1}", "warn")
                except OperationCancelled:
                    self._ui(self.log.log,
                             f"⛔ Stopped while deleting {name} from Drive {drive_idx+1} "
                             f"(it may be partially deleted).", "warn")
                    raise
                except Exception as e:
                    self._ui(self.log.log, f"✘ Delete error {name}: {e}", "err")
                now = time.time()
                if now - last_refresh > 0.75:
                    panel.refresh_async()
                    last_refresh = now
            self._ui(panel.set_status, "✔ Done", GREEN)
            panel.refresh_async()

    def _sync_all(self):
        src = self.source_tree.root_path
        if not src or not os.path.exists(lp(src)):
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
        self._start_op(self._do_sync, src, drives, rel)

    def _do_sync(self, src, drives, rel_subpath):
        # Worker thread (see _do_copy).
        cancel = self._cur_cancel()
        self._clear_all_drive_statuses()
        self._ui(self.log.log, f"Syncing: {src} → {len(drives)} drive(s)", "info")
        for drive_idx, drive_root in drives:
            check_cancel(cancel)
            panel = self.drive_panels[drive_idx]
            self._ui(panel.set_status, "⏳ Syncing...", ORANGE)
            dest_folder = os.path.join(drive_root, rel_subpath) if rel_subpath else drive_root
            try:
                os.makedirs(lp(dest_folder), exist_ok=True)
                last_refresh = 0
                with os.scandir(lp(src)) as it:
                    items = list(it)
                for item in items:
                    check_cancel(cancel)
                    dest = os.path.join(dest_folder, item.name)
                    if item.is_dir():
                        if os.path.exists(lp(dest)):
                            remove_path_cancellable(dest, cancel)
                        copytree_cancellable(os.path.join(src, item.name), dest, cancel)
                    else:
                        copy_file_cancellable(os.path.join(src, item.name), dest, cancel)
                    self._ui(self.log.log, f"✔ {item.name} → Drive {drive_idx+1}", "ok")
                    now = time.time()
                    if now - last_refresh > 0.75:
                        panel.refresh_async()
                        last_refresh = now
                self._ui(panel.set_status, "✔ Synced", GREEN)
                panel.refresh_async()
            except OperationCancelled:
                self._ui(self.log.log,
                         f"⛔ Sync to Drive {drive_idx+1} interrupted "
                         f"(an incomplete item may remain there).", "warn")
                raise
            except Exception as e:
                self._ui(self.log.log, f"✘ Drive {drive_idx+1}: {e}", "err")
                self._ui(panel.set_status, "✘ Error", RED)
        self._ui(self.log.log, "Sync complete!", "ok")

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
        # Background thread — all Tk access goes through self._ui(...).
        system = platform.system()
        results = []
        for drive_idx, drive_path in drives:
            ok, detail = self._eject_drive(system, drive_path)
            # "mountvol only" = filesystem-dismount fallback, not a full USB
            # safe-eject (see _eject_windows Method 3) — flag it distinctly
            # instead of reporting it the same as a real safe-eject.
            partial = ok and "mountvol only" in detail
            tag = "warn" if partial else ("ok" if ok else "err")
            status = "✔ Ejected" if ok and not partial else ("⚠ Dismounted only" if partial else "✘ Failed")
            self._ui(self.log.log, f"⏏ Drive {drive_idx+1} {status}: {detail}", tag)
            results.append((drive_idx, ok, detail, partial))

        # Update panels that were successfully ejected
        for drive_idx, ok, _, partial in results:
            panel = self.drive_panels[drive_idx]
            if ok and not partial:
                self._ui(panel.set_status, "⏏ Ejected – safe to remove", "#22c55e")
            elif ok and partial:
                self._ui(panel.set_status, "⚠ Dismounted only – wait before unplugging", ORANGE)
            else:
                self._ui(panel.set_status, "✘ Eject failed", "#ef4444")

        success = sum(1 for _, ok, _, partial in results if ok and not partial)
        partial_count = sum(1 for _, ok, _, partial in results if ok and partial)
        fail = len(results) - success - partial_count
        summary = f"Eject complete: {success} fully ejected"
        if partial_count:
            summary += f", {partial_count} dismounted only (wait a few seconds before unplugging)"
        if fail:
            summary += f", {fail} failed (check log)"
        self._ui(messagebox.showinfo, "Safely Eject", summary)

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
        """Windows: safe removal for ALL USB drive types.

        Strategy (tried in order, each one only runs if the previous one failed):
          1. cfgmgr32 CM_RequestDeviceEject via ctypes — the exact mechanism used by
             Windows 'Safely Remove Hardware' tray. Works for ALL USB types including
             USB-SATA bridges (RTL9210, JMS578, etc.).
          2. DeviceIoControl IOCTL_STORAGE_EJECT_MEDIA on the physical disk handle —
             a different code path than method 1, catches cases where the PnP-tree
             walk in method 1 can't find a USB parent node.
          3. mountvol /d — true last resort. Filesystem-only dismount: data is safe
             (buffers are flushed), but Windows does NOT get a USB safe-removal
             signal, so the tray icon may stay and the drive's own write cache
             (if enabled) isn't guaranteed spun down before physical unplug.
        """
        drive_letter = os.path.splitdrive(path)[0]  # e.g. "E:"
        if not drive_letter:
            return False, "Could not determine drive letter"

        last_error = "unknown error"

        # ── Method 1: CM_RequestDeviceEject via ctypes ───────────────────────
        # Pure Python call into cfgmgr32.dll — the same API that the Windows
        # 'Safely Remove Hardware' tray icon uses. No PowerShell, no C# compile.
        # Works for ALL USB types: flash drives, USB-SATA bridges (RTL9210 etc.),
        # card readers, and any other device Windows exposes via the PnP tree.
        try:
            import ctypes
            import ctypes.wintypes
            import struct

            kernel32  = ctypes.windll.kernel32
            cfgmgr32  = ctypes.windll.cfgmgr32

            GENERIC_READ            = 0x80000000
            GENERIC_WRITE           = 0x40000000
            FILE_SHARE_READ         = 0x00000001
            FILE_SHARE_WRITE        = 0x00000002
            OPEN_EXISTING           = 3
            IOCTL_STORAGE_GET_DEVICE_NUMBER     = 0x002D1080
            IOCTL_VOLUME_GET_VOLUME_DISK_EXTENTS = 0x00560000
            FSCTL_LOCK_VOLUME       = 0x00090018
            FSCTL_DISMOUNT_VOLUME   = 0x00090020
            INVALID_HANDLE          = ctypes.wintypes.HANDLE(-1).value

            # ── Step A: resolve physical disk number from drive letter ──
            vol_handle = kernel32.CreateFileW(
                f"\\\\.\\{drive_letter}",
                GENERIC_READ | GENERIC_WRITE,
                FILE_SHARE_READ | FILE_SHARE_WRITE,
                None, OPEN_EXISTING, 0, None
            )
            if vol_handle == INVALID_HANDLE:
                # Try read-only — sufficient for IOCTL_VOLUME_GET_VOLUME_DISK_EXTENTS
                vol_handle = kernel32.CreateFileW(
                    f"\\\\.\\{drive_letter}",
                    GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE,
                    None, OPEN_EXISTING, 0, None
                )
            if vol_handle == INVALID_HANDLE:
                raise OSError(f"Cannot open volume handle for {drive_letter}")

            buf = ctypes.create_string_buffer(512)
            br  = ctypes.c_ulong(0)
            disk_number = None

            # IOCTL_VOLUME_GET_VOLUME_DISK_EXTENTS is more reliable than
            # IOCTL_STORAGE_GET_DEVICE_NUMBER for multi-partition disks
            if kernel32.DeviceIoControl(
                vol_handle, IOCTL_VOLUME_GET_VOLUME_DISK_EXTENTS,
                None, 0, buf, 512, ctypes.byref(br), None
            ):
                # VOLUME_DISK_EXTENTS: DWORD NumberOfDiskExtents (4 bytes),
                # then DISK_EXTENT[0]: DiskNumber (DWORD, 4 bytes) at offset 8
                # (4 bytes padding for alignment after the DWORD count)
                disk_number = struct.unpack_from("<I", buf, 8)[0]
            else:
                # Fallback: IOCTL_STORAGE_GET_DEVICE_NUMBER
                # Returns STORAGE_DEVICE_NUMBER: Type(4), Number(4), Partition(4)
                if kernel32.DeviceIoControl(
                    vol_handle, IOCTL_STORAGE_GET_DEVICE_NUMBER,
                    None, 0, buf, 512, ctypes.byref(br), None
                ):
                    disk_number = struct.unpack_from("<I", buf, 4)[0]

            # Lock + dismount the volume so OS releases open handles
            kernel32.DeviceIoControl(vol_handle, FSCTL_LOCK_VOLUME,
                                     None, 0, None, 0, ctypes.byref(br), None)
            kernel32.DeviceIoControl(vol_handle, FSCTL_DISMOUNT_VOLUME,
                                     None, 0, None, 0, ctypes.byref(br), None)
            kernel32.CloseHandle(vol_handle)

            if disk_number is None:
                raise OSError("Could not resolve physical disk number")

            # ── Step B: get PnP Device ID for PhysicalDriveN via WMI ──
            # Use PowerShell WMI query (single fast line, no Add-Type needed)
            ps_wmi = (
                f"(Get-WmiObject Win32_DiskDrive | "
                f"Where-Object {{$_.Index -eq {disk_number}}}).PNPDeviceID"
            )
            wmi_result = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_wmi],
                capture_output=True, text=True, timeout=10
            )
            pnp_id = wmi_result.stdout.strip()
            if not pnp_id:
                raise OSError(f"WMI returned no PNPDeviceID for PhysicalDrive{disk_number}")

            # ── Step C: locate PnP device node and walk up to USB parent ──
            CM_LOCATE_DEVNODE_NORMAL = 0
            CR_SUCCESS = 0

            dev_inst = ctypes.c_ulong(0)
            ret = cfgmgr32.CM_Locate_DevNodeW(
                ctypes.byref(dev_inst),
                ctypes.c_wchar_p(pnp_id),
                CM_LOCATE_DEVNODE_NORMAL
            )
            if ret != CR_SUCCESS:
                raise OSError(f"CM_Locate_DevNodeW failed: CR={ret} for {pnp_id}")

            # Walk up the device tree until we reach a node whose ID starts with USB\
            # (the USB composite or hub parent — this is the node to eject)
            MAX_DEVICE_ID_LEN = 200
            for _ in range(12):
                id_buf = ctypes.create_unicode_buffer(MAX_DEVICE_ID_LEN)
                cfgmgr32.CM_Get_Device_IDW(
                    dev_inst, id_buf, MAX_DEVICE_ID_LEN, 0
                )
                node_id = id_buf.value
                if node_id.upper().startswith("USB\\"):
                    # Found the USB device node — request safe eject
                    veto_buf = ctypes.create_unicode_buffer(MAX_DEVICE_ID_LEN)
                    cr = cfgmgr32.CM_Request_Device_EjectW(
                        dev_inst,
                        None,           # pVetoType — we don't need the veto type
                        veto_buf,
                        MAX_DEVICE_ID_LEN,
                        0
                    )
                    if cr == CR_SUCCESS:
                        return True, f"Ejected {drive_letter} via CM_Request_Device_Eject ({node_id})"
                    veto = veto_buf.value
                    raise OSError(
                        f"CM_Request_Device_Eject CR={cr}"
                        + (f" veto='{veto}'" if veto else "")
                    )
                # Go up one level in the PnP tree
                parent = ctypes.c_ulong(0)
                if cfgmgr32.CM_Get_Parent(
                    ctypes.byref(parent), dev_inst, 0
                ) != CR_SUCCESS:
                    break
                dev_inst = parent

            raise OSError(f"No USB parent found in PnP tree for {pnp_id}")

        except OSError as e:
            last_error = str(e)
        except Exception as e:
            last_error = f"ctypes error: {e}"

        # ── Method 2: DeviceIoControl IOCTL_STORAGE_EJECT_MEDIA ──────────────
        # Only reached if Method 1 failed. Opens the physical disk handle
        # (\\.\PhysicalDriveN) directly and sends the storage-level eject —
        # a different code path than the PnP-tree walk above, so it can
        # succeed in cases where Method 1's USB-parent lookup fails.
        try:
            import ctypes, ctypes.wintypes
            kernel32 = ctypes.windll.kernel32
            GENERIC_READ  = 0x80000000
            GENERIC_WRITE = 0x40000000
            FILE_SHARE_READ  = 0x00000001
            FILE_SHARE_WRITE = 0x00000002
            OPEN_EXISTING = 3
            IOCTL_VOLUME_GET_VOLUME_DISK_EXTENTS = 0x00560000
            IOCTL_STORAGE_EJECT_MEDIA = 0x2D4808
            FSCTL_LOCK_VOLUME     = 0x00090018
            FSCTL_DISMOUNT_VOLUME = 0x00090020

            # Step 1: get physical disk number from volume handle
            vol_handle = kernel32.CreateFileW(
                f"\\\\.\\{drive_letter}",
                GENERIC_READ | GENERIC_WRITE,
                FILE_SHARE_READ | FILE_SHARE_WRITE,
                None, OPEN_EXISTING, 0, None
            )
            INVALID = ctypes.wintypes.HANDLE(-1).value
            disk_number = None
            if vol_handle != INVALID:
                buf = ctypes.create_string_buffer(512)
                br  = ctypes.c_ulong(0)
                if kernel32.DeviceIoControl(
                    vol_handle, IOCTL_VOLUME_GET_VOLUME_DISK_EXTENTS,
                    None, 0, buf, 512, ctypes.byref(br), None
                ):
                    # Structure: DWORD NumberOfDiskExtents, then extents[0].DiskNumber (DWORD)
                    disk_number = ctypes.cast(buf[4:8],
                                              ctypes.POINTER(ctypes.c_ulong))[0]
                # Lock + dismount volume before physical eject
                kernel32.DeviceIoControl(vol_handle, FSCTL_LOCK_VOLUME,
                                         None, 0, None, 0, ctypes.byref(br), None)
                kernel32.DeviceIoControl(vol_handle, FSCTL_DISMOUNT_VOLUME,
                                         None, 0, None, 0, ctypes.byref(br), None)
                kernel32.CloseHandle(vol_handle)

            # Step 2: open PhysicalDrive handle and send IOCTL_STORAGE_EJECT_MEDIA
            if disk_number is not None:
                phys_handle = kernel32.CreateFileW(
                    f"\\\\.\\PhysicalDrive{disk_number}",
                    GENERIC_READ | GENERIC_WRITE,
                    FILE_SHARE_READ | FILE_SHARE_WRITE,
                    None, OPEN_EXISTING, 0, None
                )
                if phys_handle != INVALID:
                    br2 = ctypes.c_ulong(0)
                    ok = kernel32.DeviceIoControl(
                        phys_handle, IOCTL_STORAGE_EJECT_MEDIA,
                        None, 0, None, 0, ctypes.byref(br2), None
                    )
                    kernel32.CloseHandle(phys_handle)
                    if ok:
                        return True, f"Ejected {drive_letter} via IOCTL_STORAGE_EJECT_MEDIA (PhysicalDrive{disk_number})"
                    last_error = f"{last_error}; IOCTL_STORAGE_EJECT_MEDIA failed (PhysicalDrive{disk_number})"
                else:
                    last_error = f"{last_error}; could not open PhysicalDrive{disk_number}"
            else:
                last_error = f"{last_error}; could not resolve physical disk number"
        except Exception as e:
            last_error = f"{last_error}; IOCTL eject error: {e}"

        # ── Method 3: mountvol /d — true last resort ──────────────────────────
        # Only reached if Methods 1 AND 2 both failed. Filesystem-only dismount:
        # data is safe (buffers flushed), but Windows does NOT send a USB
        # safe-removal signal, so the tray icon may stay and the drive's own
        # write cache (if enabled) isn't guaranteed spun down before unplug.
        # This is intentionally reported differently from a full eject so the
        # UI/log don't claim a level of safety this method doesn't provide.
        try:
            r = subprocess.run(
                ["mountvol", drive_letter + "\\", "/d"],
                capture_output=True, text=True, timeout=10
            )
            if r.returncode == 0:
                return True, (
                    f"Dismounted {drive_letter} via mountvol only — NOT a full safe-eject "
                    f"({last_error}). Filesystem is safe to unplug, but wait a few seconds "
                    f"for the drive to finish any pending writes before removing it."
                )
            return False, f"All eject methods failed ({last_error}); mountvol: {r.stderr.strip() or 'unknown error'}"
        except FileNotFoundError:
            return False, f"All eject methods failed ({last_error}); mountvol not found"
        except subprocess.TimeoutExpired:
            return False, f"All eject methods failed ({last_error}); mountvol timeout"

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
# EXTRA DRIVES WINDOW (drives 5..NUM_DRIVES)
# ─────────────────────────────────────────────
class ExtraDrivesWindow(tk.Toplevel):
    """Secondary window holding drive panels 5..NUM_DRIVES.
    Hidden (withdrawn) rather than destroyed on close, so the DrivePanel
    widgets inside it (and their state) stay alive for the whole session."""
    def __init__(self, parent, config, on_close=None):
        super().__init__(parent)
        self.config_data = config
        self._on_close_cb = on_close
        self.title("BackupFlow – More Drives (5–8)")
        self.configure(bg=BG)
        self.geometry("1280x780")
        self.minsize(800, 500)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._build()
        self.update_idletasks()
        apply_dark_titlebar(self)

    def _build(self):
        header = tk.Frame(self, bg=BG3, pady=10, padx=16)
        header.pack(fill="x")
        tk.Label(header, text="💾  BackupFlow", font=("Segoe UI", 16, "bold"),
                 fg=ACCENT2, bg=BG3).pack(side="left")
        tk.Label(header, text="More Drives (5–8)",
                 font=FONT_MAIN, fg=TEXT_DIM, bg=BG3).pack(side="left", padx=16)
        tk.Button(header, text="🔄  Refresh", command=self._refresh_all,
                  bg=BG2, fg=TEXT_DIM, font=FONT_BOLD, relief="flat",
                  padx=10, pady=4, cursor="hand2").pack(side="right", padx=6)

        grid = tk.Frame(self, bg=BG)
        grid.pack(fill="both", expand=True, padx=6, pady=6)
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)
        grid.rowconfigure(0, weight=1)
        grid.rowconfigure(1, weight=1)

        self.drive_panels = []
        positions = [(0, 0), (0, 1), (1, 0), (1, 1)]
        for slot, (row, col) in enumerate(positions):
            drive_index = MAIN_DRIVES + slot  # 4..7
            panel = DrivePanel(grid, drive_index, self.config_data)
            panel.grid(row=row, column=col, sticky="nsew", padx=4, pady=4)
            self.drive_panels.append(panel)

    def _refresh_all(self):
        # refresh_async: refresh() blocks on disk I/O and would freeze the
        # whole app if a drive is busy from an ongoing copy/move/sync.
        for panel in self.drive_panels:
            panel.refresh_async()

    def _on_close(self):
        if self._on_close_cb:
            self._on_close_cb()
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
        self.more_drives_btn = tk.Button(
            header, text="🖥  More Drives (5–8)", command=self._toggle_extra_drives,
            bg=BG2, fg=TEXT_DIM, font=FONT_BOLD, relief="flat",
            padx=10, pady=4, cursor="hand2")
        self.more_drives_btn.pack(side="right", padx=6)
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

        # Extra drives (5..8) live in a secondary window. It's created now
        # (hidden) so self.drive_panels always has all NUM_DRIVES entries —
        # the Control Panel's copy/move/delete/sync/eject logic addresses
        # drives purely by index and expects every slot to exist.
        self.extra_window = ExtraDrivesWindow(
            self, self.config_data, on_close=self._on_extra_window_closed)
        self.extra_window.withdraw()
        self.drive_panels.extend(self.extra_window.drive_panels)

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
        # refresh_async: refresh() blocks on disk I/O and would freeze the
        # whole app if a drive is busy from an ongoing copy/move/sync.
        for panel in self.drive_panels:
            panel.refresh_async()

    def _toggle_extra_drives(self):
        if self.extra_window.state() == "withdrawn":
            self.extra_window.deiconify()
            self.extra_window.lift()
            x = self.winfo_x() + 40
            y = self.winfo_y() + 40
            self.extra_window.geometry(f"+{x}+{y}")
            self.more_drives_btn.config(text="🖥  Hide Drives (5–8)", bg=ACCENT, fg=TEXT)
        else:
            self.extra_window.withdraw()
            self.more_drives_btn.config(text="🖥  More Drives (5–8)", bg=BG2, fg=TEXT_DIM)

    def _on_extra_window_closed(self):
        self.more_drives_btn.config(text="🖥  More Drives (5–8)", bg=BG2, fg=TEXT_DIM)

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
