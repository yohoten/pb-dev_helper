"""Reusable tkinter widgets."""

import re
import tkinter as tk
from tkinter import ttk, filedialog
import os

# Regex to detect emoji characters (covers most common emoji ranges)
_EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001F9FF"  # Misc Symbols, Emoticons, Dingbats, etc.
    "\U00002600-\U000027BF"  # Misc symbols, Dingbats
    "\U0000FE00-\U0000FE0F"  # Variation Selectors
    "\U0000200D"             # ZWJ
    "\U00002702-\U000027B0"  # Dingbats
    "]+",
    flags=re.UNICODE,
)


class FilePicker(ttk.Frame):
    """Label + entry + browse button for file/folder selection."""

    def __init__(self, parent, label: str, file_mode: bool = True,
                 file_types: list[tuple[str, str]] | None = None,
                 default_path: str = "", **kw):
        super().__init__(parent, **kw)
        self._file_mode = file_mode
        self._file_types = file_types or [("All Files", "*.*")]
        self._default_path = default_path

        ttk.Label(self, text=label).pack(side=tk.LEFT, padx=(0, 5))
        self._var = tk.StringVar(value=default_path)
        self._entry = ttk.Entry(self, textvariable=self._var, width=50)
        self._entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        ttk.Button(self, text="📂 Browse...", command=self._browse, width=12).pack(side=tk.LEFT)

    def _browse(self):
        if self._file_mode:
            path = filedialog.askopenfilename(
                filetypes=self._file_types,
                initialdir=self._get_start_dir(),
            )
        else:
            path = filedialog.askdirectory(
                initialdir=self._get_start_dir(),
            )
        if path:
            self._var.set(path)

    def _get_start_dir(self) -> str:
        cur = self._var.get()
        if cur and os.path.exists(cur):
            return cur if self._file_mode else os.path.dirname(cur)
        if self._default_path and os.path.exists(self._default_path):
            return self._default_path
        return ""

    def get(self) -> str:
        return self._var.get()

    def set(self, value: str):
        self._var.set(value)

    @property
    def var(self) -> tk.StringVar:
        return self._var


class LogWidget(ttk.Frame):
    """Scrollable log text area with emoji font fallback."""

    def __init__(self, parent, **kw):
        super().__init__(parent, **kw)
        self._text = tk.Text(self, height=8, wrap=tk.WORD, state=tk.DISABLED,
                             font=("Consolas", 9))
        scrollbar = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self._text.yview)
        self._text.configure(yscrollcommand=scrollbar.set)
        self._text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Emoji font tag — uses Segoe UI Emoji on Windows for proper emoji rendering
        self._text.tag_configure("EMOJI", font=("Segoe UI Emoji", 9))

        # Color tags for log levels
        self._text.tag_configure("INFO", foreground="black")
        self._text.tag_configure("WARN", foreground="orange")
        self._text.tag_configure("ERROR", foreground="red")
        self._text.tag_configure("SUCCESS", foreground="green")

    def append(self, message: str, level: str = "INFO"):
        self._text.configure(state=tk.NORMAL)
        base_index = self._text.index("end-1c linestart")
        self._text.insert(tk.END, message + "\n")
        line_start = f"{base_index} linestart"
        line_end = f"{base_index} lineend"
        # Apply level color to entire line
        self._text.tag_add(level.upper(), line_start, line_end)
        # Apply emoji font to emoji segments within the line
        line_text = self._text.get(line_start, line_end)
        for match in _EMOJI_RE.finditer(line_text):
            start_col = match.start()
            end_col = match.end()
            self._text.tag_add("EMOJI",
                               f"{base_index}+{start_col}c",
                               f"{base_index}+{end_col}c")
        self._text.see(tk.END)
        self._text.configure(state=tk.DISABLED)

    def clear(self):
        self._text.configure(state=tk.NORMAL)
        self._text.delete("1.0", tk.END)
        self._text.configure(state=tk.DISABLED)


class ProgressBar(ttk.Frame):
    """Progress bar with status text."""

    def __init__(self, parent, **kw):
        super().__init__(parent, **kw)
        self._bar = ttk.Progressbar(self, mode="determinate")
        self._bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        self._label = ttk.Label(self, text="", width=20, anchor=tk.E)
        self._label.pack(side=tk.RIGHT)

    def set_progress(self, current: int, total: int, text: str = ""):
        if total > 0:
            self._bar.configure(maximum=total, value=current)
        self._label.configure(text=text)

    def reset(self):
        self._bar.configure(value=0)
        self._label.configure(text="")

class CollapsibleFrame(ttk.Frame):
    """Collapsible frame with toggle button."""

    def __init__(self, parent, title: str = "", **kw):
        super().__init__(parent, **kw)
        
        # Header frame with toggle button
        header_frame = ttk.Frame(self)
        header_frame.pack(fill=tk.X)
        
        self._expanded = tk.BooleanVar(value=False)
        self._title = title
        self._toggle_btn = ttk.Button(header_frame, text=f"▶ {title}", 
                                       command=self._toggle)
        self._toggle_btn.pack(fill=tk.X, padx=2, pady=2)
        
        # Content frame (initially hidden)
        self._content_frame = ttk.Frame(self)
        
    def _toggle(self):
        if self._expanded.get():
            self._content_frame.pack_forget()
            self._toggle_btn.configure(text=f"▶ {self._title}")
            self._expanded.set(False)
        else:
            self._content_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            self._toggle_btn.configure(text=f"▼ {self._title}")
            self._expanded.set(True)
    
    def get_content_frame(self) -> ttk.Frame:
        """Get the content frame to add widgets to."""
        return self._content_frame


