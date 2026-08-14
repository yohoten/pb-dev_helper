"""Settings tab — configure PB paths, worker, and export preferences."""

import sys
import tkinter as tk
from tkinter import ttk, messagebox
import os

from models.config import AppConfig
from models.enums import ENC_MAP
from gui.widgets import FilePicker, LogWidget
from utils.pb_path import find_pb_paths, validate_pb_paths


class SettingsTab(ttk.Frame):
    """Settings panel for PB paths and export preferences."""

    def __init__(self, parent, config: AppConfig, log_widget: LogWidget, **kw):
        super().__init__(parent, **kw)
        self._config = config
        self._log = log_widget

        # Use Notebook for grouped settings
        settings_notebook = ttk.Notebook(self)
        settings_notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # ── Tab 1: PowerBuilder Paths ──
        pb_tab = ttk.Frame(settings_notebook, padding=10)
        settings_notebook.add(pb_tab, text="⚙️ PB Paths")

        # PB version selector
        ver_frame = ttk.Frame(pb_tab)
        ver_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(ver_frame, text="PB Version:").pack(side=tk.LEFT, padx=(0, 10))
        self._ver_var = tk.StringVar(value=config.pb_version)
        ver_combo = ttk.Combobox(ver_frame, textvariable=self._ver_var, state="readonly",
                                 values=["10", "25"], width=5)
        ver_combo.pack(side=tk.LEFT)
        ver_combo.bind("<<ComboboxSelected>>", lambda e: self._on_version_changed())

        # PB paths
        self._ide_picker = FilePicker(pb_tab, "ORCA/IDE Path:", file_mode=False,
                                      default_path=config.pb_ide_path)
        self._ide_picker.pack(fill=tk.X, pady=(0, 10))

        self._runtime_picker = FilePicker(pb_tab, "Runtime Path:", file_mode=False,
                                          default_path=config.pb_runtime_path)
        self._runtime_picker.pack(fill=tk.X, pady=(0, 10))

        btn_frame = ttk.Frame(pb_tab)
        btn_frame.pack(fill=tk.X, pady=(5, 0))
        ttk.Button(btn_frame, text="🔍 Auto Detect", command=self._auto_detect).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(btn_frame, text="✓ Validate Paths", command=self._validate).pack(side=tk.LEFT)

        # ── Tab 2: Export Defaults ──
        export_tab = ttk.Frame(settings_notebook, padding=10)
        settings_notebook.add(export_tab, text="📤 Export")

        ttk.Label(export_tab, text="Encoding:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10), pady=5)
        enc_map_rev = {1: "UTF8", 0: "UNICODE", 3: "ANSI_DBCS", 2: "HEXASCII"}
        self._enc_var = tk.StringVar(value=enc_map_rev.get(config.export_encoding, "UTF8"))
        enc_combo = ttk.Combobox(export_tab, textvariable=self._enc_var, state="readonly",
                                 values=["UTF8", "UNICODE", "ANSI_DBCS", "HEXASCII"], width=12)
        enc_combo.grid(row=0, column=1, sticky=tk.W, pady=5)

        self._headers_var = tk.BooleanVar(value=config.export_headers)
        ttk.Checkbutton(export_tab, text="☑ Include export headers", variable=self._headers_var).grid(
            row=1, column=0, columnspan=2, sticky=tk.W, pady=5)

        self._binary_var = tk.BooleanVar(value=config.export_include_binary)
        ttk.Checkbutton(export_tab, text="☑ Include binary objects", variable=self._binary_var).grid(
            row=2, column=0, columnspan=2, sticky=tk.W, pady=5)

        # ── Tab 3: Worker Configuration ──
        worker_tab = ttk.Frame(settings_notebook, padding=10)
        settings_notebook.add(worker_tab, text="🔌 Worker")

        self._worker_picker = FilePicker(worker_tab, "Worker Python (32-bit):", file_mode=True,
                                         file_types=[("Python EXE", "python.exe"), ("All Files", "*.*")])
        self._worker_picker.pack(fill=tk.X, pady=(0, 10))

        # Auto-set worker path to dist/worker/
        # Works both in dev mode and PyInstaller bundle
        if getattr(sys, 'frozen', False):
            base = os.path.dirname(sys.executable)
        else:
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        default_worker = os.path.join(base, "dist", "worker", "python.exe")
        if os.path.exists(default_worker) and not self._worker_picker.get():
            self._worker_picker.set(default_worker)

        info_label = ttk.Label(worker_tab, 
                               text="ℹ️ The worker requires 32-bit Python to interact with ORCA API.",
                               foreground="#666", wraplength=400)
        info_label.pack(pady=(0, 10))

        ttk.Button(worker_tab, text="🔌 Test Connection", command=self._test_connection).pack(side=tk.LEFT)

        # ── Bottom: Save button ──
        save_frame = ttk.Frame(self)
        save_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        ttk.Button(save_frame, text="💾 Save All Settings", command=self._save).pack(side=tk.RIGHT)

    def _on_version_changed(self):
        """When PB version changes, re-run auto-detect to update paths."""
        self._auto_detect()

    def _auto_detect(self):
        target_ver = self._ver_var.get()
        # Pass existing config paths as hints for discovery
        config_hints = [
            p for p in [self._config.pb_ide_path, self._config.pb_runtime_path]
            if p and os.path.isdir(p)
        ]
        orca_dir, rt_dir, ver = find_pb_paths(
            prefer=target_ver,
            custom_paths=self._config.custom_pb_paths,
            config_paths=config_hints,
        )
        if orca_dir:
            self._ide_picker.set(orca_dir)
            self._runtime_picker.set(rt_dir or orca_dir)
            if ver:
                self._ver_var.set(ver)
            if ver and ver != target_ver:
                self._log.append(
                    f"⚠️ PB {target_ver} not found. Fell back to PB {ver}. "
                    f"Add PB {target_ver} path to 'custom_pb_paths' in config.",
                    "WARN",
                )
            else:
                self._log.append(f"✅ Auto-detected PB {ver or '?'} paths.", "SUCCESS")
        else:
            self._log.append(
                f"❌ Could not find PB {target_ver} paths. "
                f"Add the path to 'custom_pb_paths' in pbdev_config.json or set manually.",
                "ERROR",
            )

    def _validate(self):
        missing = validate_pb_paths(
            self._ide_picker.get(), self._runtime_picker.get(),
            pb_version=self._ver_var.get(),
        )
        if not missing:
            self._log.append("✅ All required DLLs found.", "SUCCESS")
            messagebox.showinfo("Validate", "✅ All required DLLs found.")
        else:
            self._log.append("❌ Missing DLLs:", "ERROR")
            for m in missing:
                self._log.append(f"  - {m}", "ERROR")
            
            # Format error message for better readability
            error_msg = "Missing files:\n\n"
            for m in missing:
                # Truncate long paths for display
                if len(m) > 80:
                    display_m = m[:77] + "..."
                else:
                    display_m = m
                error_msg += f"• {display_m}\n"
            
            error_msg += "\nPlease check your PB installation paths."
            messagebox.showerror("Validation Failed", error_msg)

    def _test_connection(self):
        self._log.append("🔄 Testing ORCA worker connection...", "INFO")
        from orca.rpc_client import OrcaRpcClient
        from orca.session import OrcaSession

        # Handle both dev mode and PyInstaller bundle
        if getattr(sys, 'frozen', False):
            base = os.path.dirname(sys.executable)
        else:
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        worker_script = os.path.join(base, "scripts", "orca_worker.py")
        worker_python = self._worker_picker.get()

        # Debug: show resolved paths
        self._log.append(f"  Worker Python: {worker_python}", "INFO")
        self._log.append(f"  Worker Script: {worker_script}", "INFO")
        self._log.append(f"  ORCA path: {self._ide_picker.get()}", "INFO")
        self._log.append(f"  PB version: {self._ver_var.get()}", "INFO")

        if not os.path.exists(worker_python):
            self._log.append(f"❌ Worker Python not found: {worker_python}", "ERROR")
            return
        if not os.path.exists(worker_script):
            self._log.append(f"❌ Worker script not found: {worker_script}", "ERROR")
            return

        client = OrcaRpcClient(
            worker_python=worker_python,
            worker_script=worker_script,
            ide_path=self._ide_picker.get(),
            runtime_path=self._runtime_picker.get(),
            pb_version=self._ver_var.get(),
        )
        err = client.start()
        if err:
            self._log.append(f"❌ Failed to start worker: {err}", "ERROR")
            return

        try:
            session = OrcaSession(client)
            result = session.ping()
            if result.get("result", {}).get("pong"):
                self._log.append("✅ Worker connection OK!", "SUCCESS")
            else:
                self._log.append(f"⚠️ Worker response: {result}", "WARN")
        finally:
            client.stop()

    def _save(self):
        self._config.pb_ide_path = self._ide_picker.get()
        self._config.pb_runtime_path = self._runtime_picker.get()
        self._config.pb_version = self._ver_var.get()
        self._config.export_encoding = ENC_MAP.get(self._enc_var.get(), 1)
        self._config.export_headers = self._headers_var.get()
        self._config.export_include_binary = self._binary_var.get()
        self._config.save()
        self._log.append("✅ Settings saved.", "SUCCESS")

    def get_ide_path(self) -> str:
        return self._ide_picker.get()

    def get_runtime_path(self) -> str:
        return self._runtime_picker.get()

    def get_worker_python(self) -> str:
        return self._worker_picker.get()
