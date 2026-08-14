"""Find PowerBuilder installation paths."""

import os
import glob
import winreg


# ── Built-in fallback candidates ──────────────────────────────────────────────
# PB 10 paths (hardcoded fallbacks; registry/glob/custom paths are preferred)
_CANDIDATE_PB10_PATHS = [
    r"C:\Program Files (x86)\Sybase\PowerBuilder 10.0",
    r"C:\Program Files\Sybase\PowerBuilder 10.0",
]

# PB 2025 paths
_CANDIDATE_PB25_IDE = [
    r"C:\Program Files (x86)\Appeon\PowerBuilder 25.0\IDE",
    r"C:\Program Files\Appeon\PowerBuilder 25.0\IDE",
]
_CANDIDATE_PB25_RT = [
    r"C:\Program Files (x86)\Appeon\Common\PowerBuilder\Runtime 25.0.0.3683",
    r"C:\Program Files\Appeon\Common\PowerBuilder\Runtime 25.0.0.3683",
]

# Registry keys to search for PowerBuilder installations
_PB_REGISTRY_KEYS = [
    # Appeon PowerBuilder 2022+
    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Appeon\PowerBuilder"),
    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Appeon\PowerBuilder"),
    # Sybase PowerBuilder 10/11/12.x
    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Sybase\PowerBuilder"),
    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Sybase\PowerBuilder"),
]

# Glob patterns to discover PB installations in common directories.
# Each tuple: (glob_pattern, dll_to_check, is_ide_flag)
#   dll_to_check: "pborc100.dll" for PB10, "pborc.dll" for PB25
_PB_DISCOVERY_GLOBS = [
    # Sybase PowerBuilder (PB 10/11/12.x) — standard installs & portable
    (r"C:\Program Files (x86)\Sybase\PowerBuilder*",        "pborc100.dll", True),
    (r"C:\Program Files\Sybase\PowerBuilder*",              "pborc100.dll", True),
    (r"D:\Program Files (x86)\Sybase\PowerBuilder*",        "pborc100.dll", True),
    (r"D:\Program Files\Sybase\PowerBuilder*",              "pborc100.dll", True),
    (r"E:\Sybase\PowerBuilder*",                            "pborc100.dll", True),
    (r"E:\Program Files\Sybase\PowerBuilder*",              "pborc100.dll", True),
    # Appeon PowerBuilder IDE (PB 2022+)
    (r"C:\Program Files (x86)\Appeon\PowerBuilder*\IDE",    "pborc.dll",    True),
    (r"C:\Program Files\Appeon\PowerBuilder*\IDE",          "pborc.dll",    True),
    (r"D:\Program Files (x86)\Appeon\PowerBuilder*\IDE",    "pborc.dll",    True),
    (r"D:\Program Files\Appeon\PowerBuilder*\IDE",          "pborc.dll",    True),
]


def _read_registry_paths() -> list[str]:
    """Scan the Windows registry for PowerBuilder installation directories.

    Returns a list of candidate directories found in the registry.
    """
    candidates = []
    for hive, sub_key in _PB_REGISTRY_KEYS:
        try:
            with winreg.OpenKey(hive, sub_key) as root_key:
                i = 0
                while True:
                    try:
                        version_name = winreg.EnumKey(root_key, i)
                        i += 1
                        try:
                            with winreg.OpenKey(root_key, version_name) as ver_key:
                                # Try common value names
                                for val_name in ("InstallDir", "Path", "InstallPath", ""):
                                    try:
                                        val, _ = winreg.QueryValueEx(ver_key, val_name)
                                        if val and isinstance(val, str) and os.path.isdir(val):
                                            candidates.append(val)
                                            # Also check IDE subdirectory
                                            ide_sub = os.path.join(val, "IDE")
                                            if os.path.isdir(ide_sub):
                                                candidates.append(ide_sub)
                                    except (FileNotFoundError, OSError):
                                        continue
                        except (FileNotFoundError, OSError):
                            pass
                    except OSError:
                        break
        except (FileNotFoundError, OSError):
            pass
    return candidates


def _discover_pb_installations() -> tuple[list[str], list[str]]:
    """Scan common directories for PowerBuilder installations using glob patterns.

    Returns:
        (pb10_dirs, pb25_dirs) — deduplicated lists of discovered paths.
    """
    pb10_found: list[str] = []
    pb25_found: list[str] = []
    seen: set[str] = set()

    for pattern, dll_name, _ in _PB_DISCOVERY_GLOBS:
        for match in glob.glob(pattern):
            norm = os.path.normcase(match)
            if norm in seen:
                continue
            seen.add(norm)
            if os.path.isfile(os.path.join(match, dll_name)):
                if dll_name == "pborc100.dll":
                    pb10_found.append(match)
                else:
                    pb25_found.append(match)

    return pb10_found, pb25_found


def _find_pb25_ide() -> str | None:
    for path in _CANDIDATE_PB25_IDE:
        if os.path.exists(os.path.join(path, "pborc.dll")):
            return path
    for pat in [r"C:\Program Files (x86)\Appeon\PowerBuilder*\IDE\pborc.dll",
                r"C:\Program Files\Appeon\PowerBuilder*\IDE\pborc.dll"]:
        matches = glob.glob(pat)
        if matches:
            return os.path.dirname(matches[0])
    return None


def _find_pb25_runtime() -> str | None:
    for path in _CANDIDATE_PB25_RT:
        if os.path.exists(os.path.join(path, "pbvm.dll")):
            return path
    for pat in [r"C:\Program Files (x86)\Appeon\Common\PowerBuilder\Runtime *\pbvm.dll",
                r"C:\Program Files\Appeon\Common\PowerBuilder\Runtime *\pbvm.dll"]:
        matches = glob.glob(pat)
        if matches:
            return os.path.dirname(matches[0])
    return None


def find_pb_paths(
    prefer: str = "25",
    custom_paths: list[str] | None = None,
    config_paths: list[str] | None = None,
) -> tuple[str | None, str | None, str | None]:
    """Find PB installation paths.

    Search order:
    1. User-supplied custom_paths (from pbdev_config.json "custom_pb_paths")
    2. Existing config paths (pb_ide_path / pb_runtime_path from config)
    3. Glob discovery (scan common directories for PB installations)
    4. Windows registry (auto-detected installations)
    5. Built-in hardcoded fallback candidates

    Args:
        prefer: "25" or "10" — which version to search for first.
        custom_paths: Optional list of additional directories to search.
        config_paths: Optional list of paths from existing config (hints).

    Returns (orca_dir, runtime_dir, pb_version).
    """
    # ── Build candidate lists ──

    # Glob discovery: scan common dirs for PB installations
    glob_pb10, glob_pb25 = _discover_pb_installations()

    # Registry paths
    registry_paths = _read_registry_paths()

    # Config hints: paths from existing configuration
    hints = list(config_paths or [])

    # Combine all PB10 candidates: custom → config hints → glob → registry → built-in
    all_pb10 = (
        list(custom_paths or [])
        + hints
        + glob_pb10
        + registry_paths
        + _CANDIDATE_PB10_PATHS
    )
    # Deduplicate while preserving order
    seen: set[str] = set()
    pb10_candidates = []
    for p in all_pb10:
        norm = os.path.normcase(p)
        if norm not in seen:
            seen.add(norm)
            pb10_candidates.append(p)

    if prefer == "10":
        # Try PB10 first
        for path in pb10_candidates:
            orca_dll = os.path.join(path, "pborc100.dll")
            if os.path.exists(orca_dll):
                return (path, path, "10")
        # Fallback to PB25
        ide = _find_pb25_ide() or (glob_pb25[0] if glob_pb25 else None)
        rt = _find_pb25_runtime()
        if ide and rt:
            return (ide, rt, "25")
    else:
        # Try PB 2025 first (default)
        ide = _find_pb25_ide() or (glob_pb25[0] if glob_pb25 else None)
        rt = _find_pb25_runtime()
        if ide and rt:
            return (ide, rt, "25")
        # Fallback to PB10
        for path in pb10_candidates:
            orca_dll = os.path.join(path, "pborc100.dll")
            if os.path.exists(orca_dll):
                return (path, path, "10")

    return (None, None, None)


def validate_pb_paths(ide_path: str, runtime_path: str, pb_version: str = "10") -> list[str]:
    """Validate PB paths. Returns list of missing files.
    Auto-detects if the selected version doesn't match the actual DLLs in the paths.
    """
    missing = []
    if pb_version == "10":
        required = {
            os.path.join(ide_path, "pborc100.dll"): "pborc100.dll",
            os.path.join(runtime_path, "pbvm100.dll"): "pbvm100.dll",
            os.path.join(runtime_path, "pbshr100.dll"): "pbshr100.dll",
        }
        # Check if PB25 DLLs exist here instead (wrong version selected)
        if not os.path.exists(os.path.join(ide_path, "pborc100.dll")):
            if os.path.exists(os.path.join(ide_path, "pborc.dll")):
                missing.append("Version mismatch: paths contain PB 25 DLLs but version is set to 10. "
                               "Switch version to 25 or point to PB 10 paths.")
    else:
        required = {
            os.path.join(ide_path, "pborc.dll"): "pborc.dll",
            os.path.join(ide_path, "pbcmp.dll"): "pbcmp.dll",
            os.path.join(runtime_path, "pbvm.dll"): "pbvm.dll",
            os.path.join(runtime_path, "pbshr.dll"): "pbshr.dll",
        }
        if not os.path.exists(os.path.join(ide_path, "pborc.dll")):
            if os.path.exists(os.path.join(ide_path, "pborc100.dll")):
                missing.append("Version mismatch: paths contain PB 10 DLLs but version is set to 25. "
                               "Switch version to 10 or point to PB 10 paths.")

    if not missing:  # only check individual files if no version mismatch
        for filepath, label in required.items():
            if not os.path.exists(filepath):
                missing.append(f"{label}: {filepath}")
    return missing
