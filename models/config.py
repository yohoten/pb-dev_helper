"""Application configuration."""

import json
import os
import shutil
import sys
from dataclasses import dataclass, field
from models.enums import PBORCA_ENCODING, PBORCA_CLOBBER

# Environment variable to override config path (optional)
_ENV_CONFIG_PATH = "PBDEV_CONFIG_PATH"

# Current config file version for future migration support
CONFIG_VERSION = "1.0"


@dataclass
class AppConfig:
    """Persistent application settings."""
    pb_ide_path: str = r"C:\Program Files (x86)\Appeon\PowerBuilder 25.0\IDE"
    pb_runtime_path: str = r"C:\Program Files (x86)\Appeon\Common\PowerBuilder\Runtime 25.0.0.3683"
    pb_version: str = "25"
    export_encoding: int = 1   # PBORCA_ENCODING.UTF8
    export_headers: bool = True
    export_include_binary: bool = False
    clobber_mode: int = 2      # PBORCA_CLOBBER.CLOBBER_ALWAYS
    backup_before_import: bool = True
    last_pbl_path: str = ""
    last_export_dir: str = ""
    last_import_dir: str = ""
    # Custom PB search paths (user-configurable, appended to registry/glob detection)
    custom_pb_paths: list = field(default_factory=list)
    # Config file version for migration support
    version: str = CONFIG_VERSION

    _DEFAULT_PATH = None

    @classmethod
    def config_path(cls) -> str:
        """Get the path to the configuration file.
        
        In PyInstaller bundles, config is stored in the same directory as the executable.
        In development mode, it's stored in the project root.
        """
        if cls._DEFAULT_PATH:
            return cls._DEFAULT_PATH
        env_path = os.environ.get(_ENV_CONFIG_PATH)
        if env_path:
            return env_path
        
        # Handle both dev mode and PyInstaller bundle
        if getattr(sys, 'frozen', False):
            base = os.path.dirname(sys.executable)
        else:
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base, "pbdev_config.json")

    @classmethod
    def set_config_path(cls, path: str) -> None:
        """Override the config file path (call before load())."""
        cls._DEFAULT_PATH = path

    @classmethod
    def load(cls) -> "AppConfig":
        path = cls.config_path()
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # Filter out unknown keys to avoid dataclass errors on downgrade
                valid_keys = {f.name for f in cls.__dataclass_fields__.values()}
                filtered = {k: v for k, v in data.items() if k in valid_keys}
                return cls(**filtered)
            except (json.JSONDecodeError, TypeError, KeyError) as e:
                # Corrupted config — attempt to use backup
                backup_path = path + ".bak"
                if os.path.exists(backup_path):
                    try:
                        with open(backup_path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        valid_keys = {f.name for f in cls.__dataclass_fields__.values()}
                        filtered = {k: v for k, v in data.items() if k in valid_keys}
                        return cls(**filtered)
                    except Exception:
                        pass
                return cls()
        return cls()

    def save(self) -> None:
        """Save config to disk with automatic backup of previous version."""
        path = self.config_path()
        data = {k: v for k, v in self.__dict__.items() if not k.startswith("_")}
        # Ensure version field is always written
        data.setdefault("version", CONFIG_VERSION)

        # Create backup of existing config before overwriting
        if os.path.exists(path):
            backup_path = path + ".bak"
            try:
                shutil.copy2(path, backup_path)
            except OSError:
                pass  # Non-critical: proceed even if backup fails

        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
