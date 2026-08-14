"""Import tab — select SR directory, PBL target, import entries."""

import os
import threading
import tkinter as tk
from tkinter import ttk

from models.config import AppConfig
from models.enums import ENC_MAP, TYPE_LABELS, SR_EXTENSIONS
from gui.widgets import FilePicker, LogWidget, ProgressBar


def _scan_sr_dir(src_dir: str) -> list[dict]:
    """Scan a directory for SR files and return entry info."""
    entries = []
    if not os.path.isdir(src_dir):
        return entries

    # Build reverse map: extension → type
    ext_to_type = {}
    for ptype, ext in SR_EXTENSIONS.items():
        ext_to_type[ext] = ptype

    for fname in sorted(os.listdir(src_dir)):
        if not fname.startswith("$"):
            for ext, ptype in ext_to_type.items():
                if fname.endswith(ext):
                    name = fname[:-len(ext)]
                    fpath = os.path.join(src_dir, fname)
                    size = os.path.getsize(fpath)
                    entries.append({
                        "name": name,
                        "type": int(ptype),
                        "typeLabel": TYPE_LABELS.get(ptype, f"Unknown({int(ptype)})"),
                        "file": fname,
                        "size": size,
                    })
                    break
    return entries


class ImportTab(ttk.Frame):
    """Import SR files back into a PBL."""

    def __init__(self, parent, config: AppConfig, log_widget: LogWidget,
                 get_session, update_status=None, **kw):
        super().__init__(parent, **kw)
        self._config = config
        self._log = log_widget
        self._get_session = get_session
        self._update_status = update_status or (lambda **kwargs: None)
        self._entries: list[dict] = []

        # Main container — horizontal pack layout with collapsible preview
        main_container = ttk.Frame(self)
        main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Left side: Configuration panel (always visible, takes full width when preview hidden)
        left_frame = ttk.LabelFrame(main_container, text="⚙️ Import Configuration", padding=10)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Right side: Preview panel (hidden by default, shown on toggle)
        self._right_frame = ttk.LabelFrame(main_container, text="📋 Entries Preview", padding=10)
        # pack to RIGHT but NOT initially — hidden by _preview_visible=False

        # Preview table (inside right_frame)
        columns = ("name", "type", "file", "size")
        self._tree = ttk.Treeview(self._right_frame, columns=columns, show="headings",
                                  selectmode="extended")
        self._tree.heading("name", text="Name")
        self._tree.heading("type", text="Type")
        self._tree.heading("file", text="File")
        self._tree.heading("size", text="Size")
        self._tree.column("name", width=160)
        self._tree.column("type", width=100)
        self._tree.column("file", width=200)
        self._tree.column("size", width=80)
        scrollbar = ttk.Scrollbar(self._right_frame, orient=tk.VERTICAL, command=self._tree.yview)
        self._tree.configure(yscrollcommand=scrollbar.set)
        self._tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Progress bar in right panel
        self._progress = ProgressBar(self._right_frame)
        self._progress.pack(fill=tk.X, pady=(10, 0))

        # Track visibility state
        self._preview_visible = False

        # ── Left panel contents ──

        # SR source directory
        src_frame = ttk.Frame(left_frame)
        src_frame.pack(fill=tk.X, pady=(0, 10))
        self._src_picker = FilePicker(
            src_frame, "📁 SR Folder:", file_mode=False,
            default_path=config.last_export_dir,
        )
        self._src_picker.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        ttk.Button(src_frame, text="🔍 Scan", command=self._scan, width=8).pack(side=tk.LEFT)

        # Target PBL
        pbl_frame = ttk.Frame(left_frame)
        pbl_frame.pack(fill=tk.X, pady=(0, 10))
        self._pbl_picker = FilePicker(
            pbl_frame, "🎯 Target PBL:",
            file_types=[("PowerBuilder Library", "*.pbl"), ("All Files", "*.*")],
            default_path=config.last_pbl_path,
        )
        self._pbl_picker.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # PBT (optional)
        pbt_frame = ttk.Frame(left_frame)
        pbt_frame.pack(fill=tk.X, pady=(0, 10))
        self._pbt_picker = FilePicker(
            pbt_frame, "📋 PBT (opt):",
            file_types=[("PB Target", "*.pbt"), ("All Files", "*.*")],
            default_path="",
        )
        self._pbt_picker.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Warning: Import requires Application object
        warn_frame = tk.Frame(left_frame, bg="#FFF3CD", highlightbackground="#FFC107",
                              highlightthickness=1)
        warn_frame.pack(fill=tk.X, pady=(0, 10))
        warn_text = ("Target PBL must have an Application object.\n"
                     "If empty, create one in PB IDE first, or use Browse tab [Create] then open in PB IDE.")
        tk.Label(warn_frame, text=warn_text, bg="#FFF3CD", fg="#856404",
                 font=("Segoe UI", 8), justify=tk.LEFT, wraplength=280, padx=8, pady=4).pack()

        # Options
        opt_frame = ttk.LabelFrame(left_frame, text="Options", padding=10)
        opt_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(opt_frame, text="Encoding:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10), pady=2)
        self._enc_var = tk.StringVar(value="UTF8")
        enc_combo = ttk.Combobox(opt_frame, textvariable=self._enc_var, state="readonly",
                                 values=["UTF8", "UNICODE", "ANSI_DBCS", "HEXASCII"], width=12)
        enc_combo.grid(row=0, column=1, sticky=tk.W, pady=2)

        self._backup_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(opt_frame, text="☑ Backup PBL before import", variable=self._backup_var).grid(
            row=1, column=0, columnspan=2, sticky=tk.W, pady=2)

        # Buttons at bottom
        btn_frame = ttk.Frame(left_frame)
        btn_frame.pack(fill=tk.X, pady=(10, 0))
        self._import_btn = ttk.Button(btn_frame, text="📥 Import Selected", command=self._start_import)
        self._import_btn.pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(btn_frame, text="📥 Import All", command=self._import_all).pack(side=tk.LEFT, padx=(0, 5))

        # Toggle preview button (shows current state)
        self._toggle_preview_btn = ttk.Button(btn_frame, text="▶ Show Preview",
                                              command=self._toggle_preview)
        self._toggle_preview_btn.pack(side=tk.LEFT, padx=(0, 5))

        ttk.Button(btn_frame, text="🗑 Clear Log", command=self._log.clear).pack(side=tk.LEFT)

    def _toggle_preview(self):
        """Toggle the preview panel visibility."""
        if self._preview_visible:
            self._right_frame.pack_forget()
            self._preview_visible = False
            self._toggle_preview_btn.configure(text="▶ Show Preview")
        else:
            self._right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True,
                                   padx=(10, 0))
            self._preview_visible = True
            self._toggle_preview_btn.configure(text="◀ Hide Preview")

    def _scan(self):
        src_dir = self._src_picker.get()
        if not src_dir:
            self._log.append("⚠️ Select an SR source directory first.", "WARN")
            return
        self._entries = _scan_sr_dir(src_dir)
        self._populate_tree()
        self._update_status(connected=True, message=f"Scanned {len(self._entries)} SR files")
        self._log.append(f"✅ Found {len(self._entries)} SR files in {src_dir}", "INFO")

    def _populate_tree(self):
        for item in self._tree.get_children():
            self._tree.delete(item)
        for e in self._entries:
            self._tree.insert("", tk.END, values=(
                e["name"], e["typeLabel"], e["file"], str(e.get("size", 0)),
            ))

    def _get_selected_entries(self) -> list[dict]:
        names = set()
        for sel in self._tree.selection():
            values = self._tree.item(sel, "values")
            if values:
                names.add(values[0])
        return [e for e in self._entries if e["name"] in names]

    def _import_all(self):
        if not self._entries:
            self._log.append("⚠️ No entries to import. Scan a SR directory first.", "WARN")
            return
        self._do_import(self._entries)

    def _start_import(self):
        entries = self._get_selected_entries()
        if not entries:
            self._log.append("⚠️ No entries selected.", "WARN")
            return
        self._do_import(entries)

    def _do_import(self, entries: list[dict]):
        pbl_path = self._pbl_picker.get()
        src_dir = self._src_picker.get()

        if not pbl_path or not os.path.exists(pbl_path):
            self._log.append(f"❌ Target PBL not found: {pbl_path}", "ERROR")
            return

        session = self._get_session()
        if session is None:
            self._log.append("❌ Worker not connected. Check Settings tab.", "ERROR")
            self._update_status(connected=False, message="Worker not connected")
            return

        self._import_btn.configure(state=tk.DISABLED, text="⏳ Importing...")
        self._progress.reset()
        self._update_status(connected=True, message=f"Importing {len(entries)} files...")

        encoding = ENC_MAP.get(self._enc_var.get(), 1)
        pbt_path = self._pbt_picker.get()
        backup = self._backup_var.get()

        entry_params = [{"name": e["name"], "type": e["type"], "file": e["file"]} for e in entries]

        threading.Thread(
            target=self._run_import,
            args=(session, pbl_path, src_dir, entry_params, encoding, pbt_path, backup),
            daemon=True,
        ).start()

    def _run_import(self, session, pbl_path, src_dir, entries, encoding, pbt_path, backup):
        total = len(entries)
        self._log.append(f"🔄 Importing {total} entries to {pbl_path}...", "INFO")

        result = session.import_entries(
            pbl_path=pbl_path, src_dir=src_dir, entries=entries,
            encoding=encoding, pbt_path=pbt_path, backup=backup,
        )

        if "error" in result:
            self._log.append(f"❌ Import error: {result['error']['message']}", "ERROR")
            self._update_status(connected=True, message="Import failed")
            self._enable_button()
            return

        r = result.get("result", {})
        imported = r.get("imported", [])
        compile_errs = r.get("compile_errors", [])
        errors = r.get("errors", [])

        self._progress.set_progress(len(imported) + len(errors), total, f"Done: {len(imported)}/{total}")
        self._update_status(connected=True, message=f"Imported {len(imported)}/{total} files")
        self._log.append(
            f"✅ Import complete: {len(imported)} success, {len(compile_errs)} with warnings, {len(errors)} errors.",
            "SUCCESS"
        )
        for ce in compile_errs:
            n = ce["name"]
            for d in ce.get("diagnostics", []):
                self._log.append(f"  ⚠️ WARN: {n} line {d['line']}: {d['text']}", "WARN")
        for err in errors:
            self._log.append(f"  ❌ ERROR: {err['name']} — {err.get('error', 'unknown')}", "ERROR")

        self._config.last_pbl_path = pbl_path
        self._config.save()
        self._enable_button()

    def _enable_button(self):
        self._import_btn.configure(state=tk.NORMAL, text="📥 Import Selected")

