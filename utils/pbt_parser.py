"""Parse PowerBuilder target (.pbt) files.

.pbt files are INI-like text files containing:
  AppName "myapp"
  AppLib "myapp.pbl"
  LibList "myapp.pbl;other.pbl;..."
"""

import os
import re
from dataclasses import dataclass, field


@dataclass
class PbtInfo:
    """Parsed .pbt file information."""
    app_name: str = ""
    app_lib: str = ""
    lib_list: list[str] = field(default_factory=list)
    pbt_dir: str = ""

    @property
    def has_app(self) -> bool:
        return bool(self.app_name and self.app_lib)


def parse_pbt(pbt_path: str) -> PbtInfo | None:
    """Parse a .pbt file and return PbtInfo.

    Returns None if the file cannot be read or parsed.
    """
    if not os.path.isfile(pbt_path):
        return None

    info = PbtInfo()
    info.pbt_dir = os.path.dirname(os.path.abspath(pbt_path))

    try:
        with open(pbt_path, "r", encoding="utf-8-sig") as f:
            content = f.read()
    except UnicodeDecodeError:
        try:
            with open(pbt_path, "r", encoding="ansi") as f:
                content = f.read()
        except Exception:
            return None
    except Exception:
        return None

    # Parse appname, applib, liblist lines
    # Format: Keyword Value  (value may be quoted)
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("//") or line.startswith("#"):
            continue

        # Match: AppName "value" or AppName value
        m = re.match(r'AppName\s+"?([^"]*)"?\s*$', line, re.IGNORECASE)
        if m:
            info.app_name = m.group(1)
            continue

        m = re.match(r'AppLib\s+"?([^"]*)"?\s*$', line, re.IGNORECASE)
        if m:
            app_lib_name = m.group(1)
            info.app_lib = os.path.join(info.pbt_dir, app_lib_name)
            continue

        m = re.match(r'LibList\s+"?([^"]*)"?\s*$', line, re.IGNORECASE)
        if m:
            libs = m.group(1)
            for lib in libs.split(";"):
                lib = lib.strip()
                if lib:
                    full = os.path.join(info.pbt_dir, lib)
                    info.lib_list.append(os.path.normpath(full))
            continue

    return info


def find_pbt_for_pbl(pbl_path: str) -> str | None:
    """Try to find a .pbt file that references the given PBL.

    Searches in the same directory as the PBL.
    """
    pbl_dir = os.path.dirname(os.path.abspath(pbl_path))
    pbl_name = os.path.basename(pbl_path)

    for f in os.listdir(pbl_dir):
        if f.lower().endswith(".pbt"):
            pbt_path = os.path.join(pbl_dir, f)
            info = parse_pbt(pbt_path)
            if info:
                for lib in info.lib_list:
                    if os.path.normpath(lib) == os.path.normpath(pbl_path):
                        return pbt_path
                if os.path.normpath(info.app_lib) == os.path.normpath(pbl_path):
                    return pbt_path
    return None
