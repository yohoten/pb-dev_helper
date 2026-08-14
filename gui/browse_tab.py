"""Browse & Export tab — open PBL, search/filter, export entries."""

import datetime
import subprocess
import threading
import tkinter as tk
from tkinter import ttk, filedialog
import os

from models.config import AppConfig
from models.enums import ENC_MAP
from gui.widgets import FilePicker

# Debounce delay for search filter (milliseconds)
_FILTER_DEBOUNCE_MS = 300


class BrowseTab(ttk.Frame):
    """Combined PBL browsing + search + export panel."""

    def __init__(self, parent, config: AppConfig, log_widget,
                 get_session, update_status=None, **kw):
        super().__init__(parent, **kw)
        self._config = config
        self._log = log_widget
        self._get_session = get_session
        self._update_status = update_status or (lambda **kwargs: None)
        self._entries: list[dict] = []
        self._all_entries: list[dict] = []  # unfiltered
        self._filter_after_id: str | None = None  # debounce timer handle

        # ── Zone 1: Compact Toolbar (merged PBL + Filter) ──
        toolbar = ttk.Frame(self)
        toolbar.pack(fill=tk.X, padx=8, pady=6)

        # Left: PBL picker with icon buttons
        pbl_group = ttk.LabelFrame(toolbar, text="📄 Library", padding=4)
        pbl_group.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))

        self._pbl_picker = FilePicker(
            pbl_group, "",
            file_types=[("PowerBuilder Library", "*.pbl"), ("All Files", "*.*")],
            default_path=config.last_pbl_path,
        )
        self._pbl_picker.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

        # Icon buttons for quick actions
        btn_frame = ttk.Frame(pbl_group)
        btn_frame.pack(side=tk.LEFT, padx=(5, 0))
        ttk.Button(btn_frame, text="📂", command=self._load, width=3).pack(side=tk.LEFT, padx=1)
        ttk.Button(btn_frame, text="➕", command=self._create_lib, width=3).pack(side=tk.LEFT, padx=1)
        ttk.Button(btn_frame, text="🔍", command=self._launch_pbpicker, width=3).pack(side=tk.LEFT, padx=1)

        # Right: Inline filter
        filter_group = ttk.Frame(toolbar)
        filter_group.pack(side=tk.RIGHT, padx=(8, 0))

        ttk.Label(filter_group, text="🔎").pack(side=tk.LEFT)
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", lambda *a: self._schedule_filter())
        self._search_entry = ttk.Entry(filter_group, textvariable=self._search_var, width=15)
        self._search_entry.pack(side=tk.LEFT, padx=2)

        ttk.Label(filter_group, text="Type:").pack(side=tk.LEFT, padx=(5, 2))
        self._type_var = tk.StringVar(value="All")
        self._type_combo = ttk.Combobox(filter_group, textvariable=self._type_var, state="readonly",
                                        values=["All", "Application", "Window", "DataWindow",
                                                "Menu", "Function", "UserObject", "Structure",
                                                "Other"], width=8)
        self._type_combo.pack(side=tk.LEFT)
        self._type_combo.bind("<<ComboboxSelected>>", lambda e: self._apply_filter())

        # ── Zone 2: Entry table (maximized) ──
        tree_container = ttk.Frame(self)
        tree_container.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        columns = ("name", "type", "size", "mtime")
        self._tree = ttk.Treeview(tree_container, columns=columns, show="headings",
                                  selectmode="extended")
        self._tree.heading("name", text="Name", command=lambda: self._sort("name"))
        self._tree.heading("type", text="Type", command=lambda: self._sort("type"))
        self._tree.heading("size", text="Size", command=lambda: self._sort("size"))
        self._tree.heading("mtime", text="Modified", command=lambda: self._sort("mtime"))
        self._tree.column("name", width=200)
        self._tree.column("type", width=100)
        self._tree.column("size", width=70)
        self._tree.column("mtime", width=130)

        scrollbar = ttk.Scrollbar(tree_container, orient=tk.VERTICAL, command=self._tree.yview)
        self._tree.configure(yscrollcommand=scrollbar.set)
        self._tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Context menu support
        self._tree.bind("<Button-3>", self._show_context_menu)

        self._sort_col = "name"
        self._sort_rev = False

        # ── Zone 3: Bottom quick action bar ──
        bottom_bar = ttk.Frame(self)
        bottom_bar.pack(fill=tk.X, padx=8, pady=(0, 6))

        # Left: Info label
        self._info_label = ttk.Label(bottom_bar, text="0 / 0 objects", 
                                      font=("Segoe UI", 9), foreground="#666")
        self._info_label.pack(side=tk.LEFT)

        # Center: Quick export buttons
        quick_export = ttk.Frame(bottom_bar)
        quick_export.pack(side=tk.LEFT, padx=20)
        self._export_sel_btn = ttk.Button(quick_export, text="📤 Export Selected", 
                                           command=self._export_selected)
        self._export_sel_btn.pack(side=tk.LEFT, padx=2)
        self._export_all_btn = ttk.Button(quick_export, text="📤 All", 
                                           command=self._export_all)
        self._export_all_btn.pack(side=tk.LEFT, padx=2)

        # Right: Expand settings button
        ttk.Button(bottom_bar, text="⚙️ Export Settings...", 
                   command=self._show_export_dialog).pack(side=tk.RIGHT)

        # Export options variables (previously in CollapsibleFrame)
        self._out_dir_var = tk.StringVar(value=config.last_export_dir)
        self._enc_var = tk.StringVar(value="UTF8")
        self._headers_var = tk.BooleanVar(value=config.export_headers)
        
        # Export dialog reference (initialized lazily)
        self._export_dialog = None

    def _show_context_menu(self, event):
        """Show context menu on tree right-click."""
        menu = tk.Menu(self._tree, tearoff=0)
        menu.add_command(label="📤 Export Selected", command=self._export_selected)
        menu.add_command(label="📤 Export All", command=self._export_all)
        menu.add_separator()
        menu.add_command(label="☑ Select All", command=self._select_all)
        menu.add_command(label="❌ Clear Selection", command=self._clear_selection)
        menu.add_separator()
        menu.add_command(label="🔄 Refresh", command=self._load)
        menu.post(event.x_root, event.y_root)

    def _clear_selection(self):
        """Clear tree selection."""
        self._tree.selection_remove(self._tree.get_children())

    def _show_export_dialog(self):
        """Show export settings dialog."""
        if self._export_dialog is not None and self._export_dialog.winfo_exists():
            self._export_dialog.deiconify()
            self._export_dialog.lift()
            return

        self._export_dialog = tk.Toplevel(self)
        self._export_dialog.title("⚙️ Export Settings")
        self._export_dialog.geometry("500x300")
        self._export_dialog.resizable(False, False)
        self._export_dialog.transient(self)
        
        # Center on parent
        x = self.winfo_rootx() + (self.winfo_width() - 500) // 2
        y = self.winfo_rooty() + (self.winfo_height() - 300) // 2
        self._export_dialog.geometry(f"+{x}+{y}")

        frame = ttk.Frame(self._export_dialog, padding=15)
        frame.pack(fill=tk.BOTH, expand=True)

        # Output directory
        dir_frame = ttk.Frame(frame)
        dir_frame.pack(fill=tk.X, pady=5)
        ttk.Label(dir_frame, text="Output Directory:").pack(anchor=tk.W)
        dir_row = ttk.Frame(dir_frame)
        dir_row.pack(fill=tk.X, pady=2)
        ttk.Entry(dir_row, textvariable=self._out_dir_var, width=40).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        ttk.Button(dir_row, text="Browse...", command=self._browse_out_dir, width=8).pack(side=tk.LEFT)

        # Encoding
        enc_frame = ttk.Frame(frame)
        enc_frame.pack(fill=tk.X, pady=5)
        ttk.Label(enc_frame, text="Encoding:").pack(anchor=tk.W)
        ttk.Combobox(enc_frame, textvariable=self._enc_var, state="readonly",
                     values=["UTF8", "UNICODE", "ANSI_DBCS", "HEXASCII"], width=15).pack(anchor=tk.W, pady=2)

        # Headers checkbox
        ttk.Checkbutton(frame, text="☑ Include export headers", 
                        variable=self._headers_var).pack(anchor=tk.W, pady=5)

        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=(10, 0))
        ttk.Button(btn_frame, text="💾 Save & Close", command=self._export_dialog.destroy).pack(side=tk.RIGHT)

    # ── PBL operations ──────────────────────────

    def _load(self):
        pbl_path = self._pbl_picker.get()
        if not pbl_path or not os.path.exists(pbl_path):
            self._log.append(f"❌ PBL not found: {pbl_path}", "ERROR")
            return

        self._log.append(f"🔄 Loading: {pbl_path}", "INFO")
        session = self._get_session()
        if session is None:
            self._log.append("❌ Worker not connected. Check settings.", "ERROR")
            self._update_status(connected=False, message="Worker not connected")
            return

        result = session.list_entries(pbl_path)
        if "error" in result:
            self._log.append(f"❌ Error: {result['error']['message']}", "ERROR")
            return

        entries = result.get("result", {}).get("entries", [])
        self._all_entries = entries
        self._config.last_pbl_path = pbl_path
        self._config.save()
        self._apply_filter()
        self._update_status(connected=True, message=f"Loaded {len(entries)} objects", path=pbl_path)
        self._log.append(f"✅ Loaded {len(entries)} entries.", "SUCCESS")

    def _create_lib(self):
        from tkinter import simpledialog
        pbl_path = filedialog.asksaveasfilename(
            title="Create New PBL Library",
            defaultextension=".pbl",
            filetypes=[("PowerBuilder Library", "*.pbl")],
            initialfile="newlib.pbl",
        )
        if not pbl_path:
            return
        comment = simpledialog.askstring("Comment", "Library comment (optional):", parent=self)
        if comment is None:
            return

        session = self._get_session()
        if session is None:
            self._log.append("❌ Worker not connected. Check settings.", "ERROR")
            return

        result = session.create_lib(pbl_path, comment or "")
        if "error" in result:
            self._log.append(f"❌ Create failed: {result['error']['message']}", "ERROR")
            return
        created = result.get("result", {}).get("created", "")
        if created:
            self._pbl_picker.set(created)
            self._log.append(f"✅ Created: {created}", "SUCCESS")

    def _launch_pbpicker(self):
        """Launch built-in PB Picker from project tools directory."""
        # Handle both dev mode and PyInstaller bundle
        if getattr(sys, 'frozen', False):
            base = os.path.dirname(sys.executable)
        else:
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        exe = os.path.join(base, "tools", "pbpicker", "pb_picker.exe")
        d = os.path.dirname(exe)
        
        if not os.path.exists(exe):
            self._log.append(f"❌ PBPicker not found: {exe}", "ERROR")
            return
        
        self._log.append("🚀 Launching PB Picker...", "INFO")
        try:
            subprocess.Popen(exe, cwd=d)
        except OSError as e:
            self._log.append(f"❌ Failed: {e}", "ERROR")

    # ── Filter / Sort ───────────────────────────

    def _schedule_filter(self):
        """Debounce wrapper for _apply_filter.

        Cancels any pending timer and schedules a new one after
        _FILTER_DEBOUNCE_MS milliseconds.  Prevents redundant table
        rebuilds on every keystroke.
        """
        if self._filter_after_id is not None:
            self.after_cancel(self._filter_after_id)
        self._filter_after_id = self.after(_FILTER_DEBOUNCE_MS, self._apply_filter)

    def _apply_filter(self):
        search = self._search_var.get().lower()
        type_filter = self._type_var.get()

        filtered = self._all_entries
        if search:
            filtered = [e for e in filtered if search in e.get("name", "").lower()]
        if type_filter != "All":
            filtered = [e for e in filtered if e.get("typeLabel", "") == type_filter]

        self._entries = filtered
        self._populate_table(filtered)
        self._info_label.configure(text=f"{len(filtered)} / {len(self._all_entries)} objects")

    def _populate_table(self, entries: list[dict]):
        for item in self._tree.get_children():
            self._tree.delete(item)
        for e in entries:
            mtime = e.get("mtime", 0)
            mtime_str = ""
            if mtime > 0:
                try:
                    mtime_str = datetime.datetime.fromtimestamp(
                        mtime, tz=datetime.timezone.utc).strftime("%Y-%m-%d %H:%M")
                except (OSError, ValueError):
                    mtime_str = str(mtime)
            self._tree.insert("", tk.END, values=(
                e.get("name", ""),
                e.get("typeLabel", ""),
                f"{e.get('size', 0) // 1024}KB",
                mtime_str,
            ))

    def _sort(self, col: str):
        if self._sort_col == col:
            self._sort_rev = not self._sort_rev
        else:
            self._sort_col = col
            self._sort_rev = False
        items = [(self._tree.set(item, col), item) for item in self._tree.get_children("")]
        items.sort(key=lambda x: x[0].lower() if x[0] else "", reverse=self._sort_rev)
        for idx, (_, item) in enumerate(items):
            self._tree.move(item, "", idx)

    def _select_all(self):
        self._tree.selection_set(self._tree.get_children())

    def _get_selected_names(self) -> list[str]:
        names = []
        for sel in self._tree.selection():
            vals = self._tree.item(sel, "values")
            if vals:
                names.append(vals[0])
        return names

    # ── Export ──────────────────────────────────

    def _browse_out_dir(self):
        d = filedialog.askdirectory(title="Select Export Directory")
        if d:
            self._out_dir_var.set(d)

    def _export_selected(self):
        names = self._get_selected_names()
        if not names:
            self._log.append("⚠️ No entries selected.", "WARN")
            return
        self._do_export(names)

    def _export_all(self):
        if not self._all_entries:
            self._log.append("⚠️ Load a PBL first.", "WARN")
            return
        self._do_export([e["name"] for e in self._entries])

    def _do_export(self, names: list[str]):
        out_dir = self._out_dir_var.get()
        if not out_dir:
            self._log.append("⚠️ Select an output directory first.", "WARN")
            return

        pbl_path = self._pbl_picker.get()
        entries = [e for e in self._all_entries if e["name"] in names]

        session = self._get_session()
        if session is None:
            self._log.append("❌ Worker not connected.", "ERROR")
            return

        encoding = ENC_MAP.get(self._enc_var.get(), 1)

        self._log.append(f"📤 Exporting {len(entries)} entries to {out_dir}...", "INFO")
        self._update_status(connected=True, message=f"Exporting {len(entries)} files...")
        self._export_sel_btn.configure(state=tk.DISABLED)
        self._export_all_btn.configure(state=tk.DISABLED)

        threading.Thread(target=self._run_export, args=(
            session, pbl_path, out_dir, entries, encoding), daemon=True).start()

    def _run_export(self, session, pbl_path, out_dir, entries, encoding):
        result = session.export_entries(
            pbl_path=pbl_path, out_dir=out_dir,
            entries=[{"name": e["name"], "type": e["type"]} for e in entries],
            encoding=encoding,
            include_headers=self._headers_var.get(),
            include_binary=self._config.export_include_binary,
        )
        if "error" in result:
            self._log.append(f"❌ Export error: {result['error']['message']}", "ERROR")
            self._update_status(connected=True, message="Export failed")
        else:
            r = result.get("result", {})
            exported = r.get("exported", [])
            errors = r.get("errors", [])
            self._log.append(f"✅ Exported {len(exported)} files, {len(errors)} errors.", "SUCCESS")
            self._update_status(connected=True, message=f"Exported {len(exported)} files")
            for err in errors:
                self._log.append(f"  ❌ ERROR: {err['name']} — {err.get('error', 'unknown')}", "ERROR")
            self._config.last_export_dir = out_dir
            self._config.save()
        self._export_sel_btn.configure(state=tk.NORMAL)
        self._export_all_btn.configure(state=tk.NORMAL)
