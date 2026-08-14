"""Main application window."""

import sys
import tkinter as tk
from tkinter import ttk
import os

from models.config import AppConfig
from gui.widgets import LogWidget
from gui.settings_tab import SettingsTab
from gui.browse_tab import BrowseTab
from gui.import_tab import ImportTab


class PBDevHelperApp:
    """Main PB Dev Helper application."""

    def __init__(self):
        self._config = AppConfig.load()
        self._client = None
        self._session = None

        # Root window
        self._root = tk.Tk()
        self._root.title("PB Dev Helper")
        self._root.geometry("1000x700")
        self._root.minsize(900, 600)
        
        # Set application icon
        if getattr(sys, 'frozen', False):
            base = os.path.dirname(sys.executable)
        else:
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        icon_path = os.path.join(base, "pb-dev-helper.ico")
        if os.path.exists(icon_path):
            try:
                self._root.iconbitmap(icon_path)
            except Exception:
                pass

        # Status bar at bottom
        self._status_bar = ttk.Frame(self._root)
        self._status_bar.pack(fill=tk.X, side=tk.BOTTOM, padx=5, pady=(5, 0))
        
        self._status_label = ttk.Label(self._status_bar, text="Worker: Disconnected",
                                        foreground="red", anchor=tk.W, font=("Segoe UI", 9))
        self._status_label.pack(side=tk.LEFT, padx=5)
        
        self._path_label = ttk.Label(self._status_bar, text="", anchor=tk.W, font=("Segoe UI", 9))
        self._path_label.pack(side=tk.LEFT, padx=10)
        
        self._progress_status = ttk.Label(self._status_bar, text="", anchor=tk.E, font=("Segoe UI", 9))
        self._progress_status.pack(side=tk.RIGHT, padx=5)

        # PanedWindow for resizable log area
        paned = ttk.PanedWindow(self._root, orient=tk.VERTICAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Notebook in upper pane
        notebook_frame = ttk.Frame(paned)
        self._notebook = ttk.Notebook(notebook_frame)
        self._notebook.pack(fill=tk.BOTH, expand=True)
        paned.add(notebook_frame, weight=3)

        # Log widget in lower pane (resizable)
        log_frame = ttk.Frame(paned)
        self._log = LogWidget(log_frame)
        self._log.pack(fill=tk.BOTH, expand=True)
        paned.add(log_frame, weight=1)

        # Settings tab (create first so other tabs can reference its paths)
        self._settings_tab = SettingsTab(self._notebook, self._config, self._log)
        self._notebook.add(self._settings_tab, text="⚙️ Settings")

        # Browse & Export tab (combined)
        self._browse_tab = BrowseTab(
            self._notebook, self._config, self._log,
            get_session=self.get_session,
            update_status=self.update_status,
        )
        self._notebook.add(self._browse_tab, text="📁 Browser")

        # Import tab
        self._import_tab = ImportTab(
            self._notebook, self._config, self._log,
            get_session=self.get_session,
            update_status=self.update_status,
        )
        self._notebook.add(self._import_tab, text="📤 Import")

    def update_status(self, connected: bool = False, message: str = ""):
        """Update status bar with connection state and optional message."""
        if connected:
            status_text = "✅ Worker: Connected"
            color = "green"
        else:
            status_text = "❌ Worker: Disconnected"
            color = "red"
        
        if message:
            status_text += f" | {message}"
        
        self._status_label.configure(text=status_text, foreground=color)

    def get_session(self):
        """Get or create an ORCA session. Auto-reconnects if worker crashed."""
        try:
            # Check if existing worker is still alive
            if self._session is not None and self._client and self._client.is_alive():
                return self._session

            # Worker died or not started — reconnect
            if self._session is not None:
                self._log.append("Worker disconnected. Reconnecting...", "WARN")
                self.stop_worker()

            from orca.rpc_client import OrcaRpcClient
            from orca.session import OrcaSession

            if getattr(sys, 'frozen', False):
                base = os.path.dirname(sys.executable)
            else:
                base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            worker_script = os.path.join(base, "scripts", "orca_worker.py")
            worker_python = self._settings_tab.get_worker_python()

            if not worker_python or not os.path.exists(worker_python):
                self._log.append("32-bit Python not configured. Go to Settings tab.", "ERROR")
                self.update_status(connected=False, message="Worker not configured")
                return None

            ide_path = self._settings_tab.get_ide_path()
            runtime_path = self._settings_tab.get_runtime_path()

            self._client = OrcaRpcClient(
                worker_python=worker_python,
                worker_script=worker_script,
                ide_path=ide_path,
                runtime_path=runtime_path,
                pb_version=self._config.pb_version,
            )
            self._client.set_log_callback(lambda level, msg: self._log.append(msg, level))

            err = self._client.start()
            if err:
                self._log.append(f"Failed to start worker: {err}", "ERROR")
                self.update_status(connected=False, message="Worker failed to start")
                self._client = None
                return None

            self._session = OrcaSession(self._client)
            self.update_status(connected=True, message="Ready")
            return self._session

        except Exception as e:
            self._log.append(f"❌ Worker error: {type(e).__name__}: {e}", "ERROR")
            self.update_status(connected=False, message="Worker error")
            self._client = None
            self._session = None
            return None

    def stop_worker(self):
        try:
            if self._client:
                self._client.stop()
                self._client = None
                self._session = None
                self.update_status(connected=False, message="Worker stopped")
        except Exception as e:
            self._log.append(f"⚠️ Error stopping worker: {e}", "WARN")
            self._client = None
            self._session = None

    def run(self):
        self._root.protocol("WM_DELETE_WINDOW", self._on_close)
        
        # Register keyboard shortcuts (P0 optimization)
        self._register_shortcuts()
        
        self._root.mainloop()

    def _register_shortcuts(self):
        """Register global keyboard shortcuts."""
        # Ctrl+L: Focus and load PBL in Browse tab
        self._root.bind('<Control-l>', lambda e: self._focus_browse_and_load())
        # Ctrl+E: Export selected in Browse tab
        self._root.bind('<Control-e>', lambda e: self._export_selected_quick())
        # F5: Refresh current operation
        self._root.bind('<F5>', lambda e: self._refresh_current())
        # Ctrl+S: Save settings
        self._root.bind('<Control-s>', lambda e: self._save_settings_quick())

    def _focus_browse_and_load(self):
        """Quick shortcut to focus browse tab and trigger load."""
        self._notebook.select(1)  # Browse tab is at index 1
        self._browse_tab._load()

    def _export_selected_quick(self):
        """Quick export selected items."""
        if self._notebook.index(self._notebook.select()) == 1:  # Browse tab
            self._browse_tab._export_selected()

    def _refresh_current(self):
        """Refresh current tab operation."""
        current_idx = self._notebook.index(self._notebook.select())
        if current_idx == 1:  # Browse tab
            self._browse_tab._load()
        elif current_idx == 2:  # Import tab
            self._import_tab._scan()

    def _save_settings_quick(self):
        """Quick save settings."""
        if self._notebook.index(self._notebook.select()) == 0:  # Settings tab
            self._settings_tab._save()

    def _on_close(self):
        self.stop_worker()
        self._root.destroy()
