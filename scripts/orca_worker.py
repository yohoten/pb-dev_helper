r"""ORCA Worker — 32-bit subprocess that loads pborc.dll via ctypes.

Communicates with the main process via JSON-lines RPC over stdin/stdout.
Must be run with a 32-bit Python interpreter.

Usage:
    python orca_worker.py --ide="C:\...IDE" --runtime="C:\...Runtime 25.0.0.3683"
"""

import sys
import os
import json
import ctypes
import argparse
from ctypes import wintypes

# ──────────────────────────────────────────────
# Enums (must match pborca.h)
# ──────────────────────────────────────────────

PBORCA_OK = 0
PBORCA_INVALIDPARMS = -1
PBORCA_OBJNOTFOUND = -3
PBORCA_BADLIBRARY = -4
PBORCA_LIBNOTINLIST = -6
PBORCA_LIBIOERROR = -7
PBORCA_OBJEXISTS = -8
PBORCA_BUFFERTOOSMALL = -10
PBORCA_COMPERROR = -11

# PBORCA_TYPE
PBORCA_APPLICATION = 0
PBORCA_DATAWINDOW = 1
PBORCA_FUNCTION = 2
PBORCA_MENU = 3
PBORCA_QUERY = 4
PBORCA_STRUCTURE = 5
PBORCA_USEROBJECT = 6
PBORCA_WINDOW = 7
PBORCA_PIPELINE = 8
PBORCA_PROJECT = 9
PBORCA_PROXYOBJECT = 10
PBORCA_BINARY = 11

# Encoding
PBORCA_UNICODE = 0
PBORCA_UTF8 = 1
PBORCA_HEXASCII = 2
PBORCA_ANSI_DBCS = 3

# Clobber
PBORCA_NOCLOBBER = 0
PBORCA_CLOBBER = 1
PBORCA_CLOBBER_ALWAYS = 2

TYPE_LABELS = {
    0: "Application", 1: "DataWindow", 2: "Function", 3: "Menu",
    4: "Query", 5: "Structure", 6: "UserObject", 7: "Window",
    8: "Pipeline", 9: "Project", 10: "ProxyObject", 11: "Binary",
}

SR_EXTENSIONS = {
    0: ".sra", 1: ".srd", 2: ".srf", 3: ".srm",
    4: ".srq", 5: ".srs", 6: ".sru", 7: ".srw",
    8: ".srp", 9: ".srj", 10: ".srx", 11: ".bin",
}

# ──────────────────────────────────────────────
# ctypes Structures (must match pborca.h layout, 32-bit packing)
# ──────────────────────────────────────────────

class PBORCA_CONFIG_SESSION(ctypes.Structure):
    _fields_ = [
        ("eClobber",            ctypes.c_int),
        ("eExportEncoding",     ctypes.c_int),
        ("bExportHeaders",      ctypes.c_int),
        ("bExportIncludeBinary", ctypes.c_int),
        ("bExportCreateFile",   ctypes.c_int),
        ("pExportDirectory",    ctypes.c_wchar_p),
        ("eImportEncoding",     ctypes.c_int),
        ("bDebug",              ctypes.c_int),
        ("filler2",             ctypes.c_void_p),
        ("filler3",             ctypes.c_void_p),
        ("filler4",             ctypes.c_void_p),
    ]


class PBORCA_DIRENTRY(ctypes.Structure):
    _fields_ = [
        ("szComments",  ctypes.c_wchar * 256),  # PBORCA_MAXCOMMENT(255) + 1
        ("lCreateTime", ctypes.c_long),
        ("lEntrySize",  ctypes.c_long),
        ("lpszEntryName", ctypes.c_wchar_p),
        ("otEntryType", ctypes.c_int),
    ]


class PBORCA_COMPERR(ctypes.Structure):
    _fields_ = [
        ("iLevel",            ctypes.c_int),
        ("lpszMessageNumber", ctypes.c_wchar_p),
        ("lpszMessageText",   ctypes.c_wchar_p),
        ("iColumnNumber",     ctypes.c_uint),
        ("iLineNumber",       ctypes.c_uint),
    ]


# Callback types
PBORCA_LISTPROC = ctypes.CFUNCTYPE(None, ctypes.POINTER(PBORCA_DIRENTRY), ctypes.c_void_p)
PBORCA_ERRPROC = ctypes.CFUNCTYPE(None, ctypes.POINTER(PBORCA_COMPERR), ctypes.c_void_p)


# ──────────────────────────────────────────────
# ORCA DLL class
# ──────────────────────────────────────────────

class OrcaDLL:
    """Wrapper around pborc.dll."""

    def __init__(self, ide_path: str, runtime_path: str, pb_version: str = "25"):
        self._pb_version = pb_version

        # PB10 uses pborc100.dll, PB25 uses pborc.dll
        dll_name = "pborc100.dll" if pb_version == "10" else "pborc.dll"
        dll_path = os.path.join(ide_path, dll_name)
        if not os.path.exists(dll_path):
            alt = "pborc.dll" if pb_version == "10" else "pborc100.dll"
            alt_path = os.path.join(ide_path, alt)
            if os.path.exists(alt_path):
                dll_path = alt_path

        # Add DLL search paths
        os.environ["PATH"] = f"{ide_path};{runtime_path};" + os.environ.get("PATH", "")
        for path in (ide_path, runtime_path):
            try:
                os.add_dll_directory(path)
            except Exception:
                pass

        self._lib = ctypes.windll.LoadLibrary(dll_path)
        self._hSession = None
        self._setup_functions()

    def _setup_functions(self):
        lib = self._lib

        # SessionOpen
        lib.PBORCA_SessionOpen.argtypes = []
        lib.PBORCA_SessionOpen.restype = ctypes.c_void_p

        # SessionClose
        lib.PBORCA_SessionClose.argtypes = [ctypes.c_void_p]
        lib.PBORCA_SessionClose.restype = None

        # ConfigureSession
        lib.PBORCA_ConfigureSession.argtypes = [ctypes.c_void_p, ctypes.POINTER(PBORCA_CONFIG_SESSION)]
        lib.PBORCA_ConfigureSession.restype = ctypes.c_int

        # SessionSetLibraryList
        lib.PBORCA_SessionSetLibraryList.argtypes = [
            ctypes.c_void_p, ctypes.POINTER(ctypes.c_wchar_p), ctypes.c_int
        ]
        lib.PBORCA_SessionSetLibraryList.restype = ctypes.c_int

        # LibraryDirectory
        lib.PBORCA_LibraryDirectory.argtypes = [
            ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_wchar_p,
            ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p,
        ]
        lib.PBORCA_LibraryDirectory.restype = ctypes.c_int

        # LibraryEntryExport
        lib.PBORCA_LibraryEntryExport.argtypes = [
            ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_wchar_p,
            ctypes.c_int, ctypes.c_wchar_p, ctypes.c_long,
        ]
        lib.PBORCA_LibraryEntryExport.restype = ctypes.c_int

        # LibraryEntryExportEx (returns actual size)
        lib.PBORCA_LibraryEntryExportEx.argtypes = [
            ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_wchar_p,
            ctypes.c_int, ctypes.c_wchar_p, ctypes.c_long,
            ctypes.POINTER(ctypes.c_long),
        ]
        lib.PBORCA_LibraryEntryExportEx.restype = ctypes.c_int

        # SessionGetError
        lib.PBORCA_SessionGetError.argtypes = [
            ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int
        ]
        lib.PBORCA_SessionGetError.restype = None

        # SessionSetCurrentAppl
        lib.PBORCA_SessionSetCurrentAppl.argtypes = [
            ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_wchar_p
        ]
        lib.PBORCA_SessionSetCurrentAppl.restype = ctypes.c_int

        # CompileEntryImport
        lib.PBORCA_CompileEntryImport.argtypes = [
            ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_wchar_p,
            ctypes.c_int, ctypes.c_wchar_p, ctypes.c_wchar_p,
            ctypes.c_long, ctypes.c_void_p, ctypes.c_void_p,
        ]
        lib.PBORCA_CompileEntryImport.restype = ctypes.c_int

        # CompileEntryImportList (batch)
        lib.PBORCA_CompileEntryImportList.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_wchar_p),
            ctypes.POINTER(ctypes.c_wchar_p),
            ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_wchar_p),
            ctypes.POINTER(ctypes.c_wchar_p),
            ctypes.POINTER(ctypes.c_long),
            ctypes.c_int,
            ctypes.c_void_p,
            ctypes.c_void_p,
        ]
        lib.PBORCA_CompileEntryImportList.restype = ctypes.c_int

        # LibraryEntryInformation
        lib.PBORCA_LibraryEntryInformation.argtypes = [
            ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_wchar_p,
            ctypes.c_int, ctypes.c_void_p,
        ]
        lib.PBORCA_LibraryEntryInformation.restype = ctypes.c_int

        # LibraryCreate
        lib.PBORCA_LibraryCreate.argtypes = [
            ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_wchar_p,
        ]
        lib.PBORCA_LibraryCreate.restype = ctypes.c_int

    def open_session(self) -> ctypes.c_void_p:
        self._hSession = self._lib.PBORCA_SessionOpen()
        return self._hSession

    def close_session(self):
        if self._hSession:
            self._lib.PBORCA_SessionClose(self._hSession)
            self._hSession = None

    def configure_session(self, config: PBORCA_CONFIG_SESSION) -> int:
        return self._lib.PBORCA_ConfigureSession(self._hSession, ctypes.byref(config))

    def set_library_list(self, libs: list[str]) -> int:
        # Keep both the array AND individual c_wchar_p objects alive.
        # ctypes array reads auto-convert to str, so we store originals separately.
        self._lib_list_wchars = [ctypes.c_wchar_p(lib) for lib in libs]
        self._lib_list_arr = (ctypes.c_wchar_p * len(libs))(*self._lib_list_wchars)
        return self._lib.PBORCA_SessionSetLibraryList(
            self._hSession, self._lib_list_arr, len(libs))

    def set_current_appl(self, lib_path: str, app_name: str) -> int:
        return self._lib.PBORCA_SessionSetCurrentAppl(self._hSession, lib_path, app_name)

    def library_directory(self, lib_path: str, callback) -> int:
        """callback must already be a PBORCA_LISTPROC instance."""
        self._dir_callback = callback  # keep alive
        cmt_buf = ctypes.create_unicode_buffer(257)
        return self._lib.PBORCA_LibraryDirectory(
            self._hSession, lib_path, cmt_buf, 257, callback, None
        )

    def export_entry(self, lib_path: str, entry_name: str, entry_type: int) -> int:
        """Export one entry. Returns PBORCA_OK on success, or error code.
        When bExportCreateFile=1 in config, ORCA writes directly to export directory.
        """
        return self._lib.PBORCA_LibraryEntryExport(
            self._hSession, lib_path, entry_name, entry_type, None, 0
        )

    def compile_entry_import(self, lib_path: str, entry_name: str, entry_type: int,
                             comments: str, syntax: bytes, err_callback=None) -> int:
        """Import and compile one entry from source bytes.

        Uses UTF-16LE buffer matching ORCA's Unicode expectations.
        lib_path must match the EXACT c_wchar_p pointer passed to set_library_list.
        """
        text = syntax.decode("utf-8-sig")
        buf = ctypes.create_unicode_buffer(text)
        buf_bytes = (len(text) + 1) * 2  # wchar_t = 2 bytes, include null

        # Use the SAME c_wchar_p pointer from the library list
        # (PB10 ORCA may do pointer comparison, not string comparison)
        lib_ptr = lib_path  # fallback
        if hasattr(self, "_lib_list_wchars") and self._lib_list_wchars:
            for wc in self._lib_list_wchars:
                if wc.value == lib_path:
                    lib_ptr = wc
                    break

        return self._lib.PBORCA_CompileEntryImport(
            self._hSession, lib_ptr, entry_name, entry_type,
            comments or " ", buf, buf_bytes,
            err_callback or 0, None
        )

    def get_error(self) -> str:
        buf = ctypes.create_unicode_buffer(512)
        self._lib.PBORCA_SessionGetError(self._hSession, buf, 512)
        return buf.value


# ──────────────────────────────────────────────
# PBT parser (embedded for worker portability)
# ──────────────────────────────────────────────

def _parse_pbt_file(pbt_path: str) -> dict | None:
    """Parse a .pbt file. Returns dict with app_name, app_lib, lib_list or None."""
    import re
    if not os.path.isfile(pbt_path):
        return None
    pbt_dir = os.path.dirname(os.path.abspath(pbt_path))
    info = {"app_name": "", "app_lib": "", "lib_list": []}
    try:
        with open(pbt_path, "r", encoding="utf-8-sig") as f:
            content = f.read()
    except (UnicodeDecodeError, OSError):
        return None

    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        m = re.match(r'AppName\s+"?([^"]*)"?\s*$', line, re.IGNORECASE)
        if m:
            info["app_name"] = m.group(1)
            continue
        m = re.match(r'AppLib\s+"?([^"]*)"?\s*$', line, re.IGNORECASE)
        if m:
            info["app_lib"] = os.path.normpath(os.path.join(pbt_dir, m.group(1)))
            continue
        m = re.match(r'LibList\s+"?([^"]*)"?\s*$', line, re.IGNORECASE)
        if m:
            for lib in m.group(1).split(";"):
                lib = lib.strip()
                if lib:
                    info["lib_list"].append(os.path.normpath(os.path.join(pbt_dir, lib)))
    return info


# ──────────────────────────────────────────────
# JSON-RPC dispatch
# ──────────────────────────────────────────────

def _write_line(data: str):
    """Write a JSON line to stdout with immediate flush, bypassing TextIOWrapper buffering."""
    raw = data.encode("utf-8") + b"\n"
    sys.stdout.buffer.write(raw)
    sys.stdout.buffer.flush()


def _send_response(req_id, result=None, error=None):
    resp = {"id": req_id}
    if error:
        resp["error"] = error
    else:
        resp["result"] = result
    _write_line(json.dumps(resp, ensure_ascii=False))


def _send_progress(current: int, total: int, entry: str = ""):
    msg = {"method": "progress", "params": {"current": current, "total": total, "entry": entry}}
    _write_line(json.dumps(msg, ensure_ascii=False))


def _send_log(level: str, message: str):
    msg = {"method": "log", "params": {"level": level, "message": message}}
    _write_line(json.dumps(msg, ensure_ascii=False))


class OrcaSession:
    """Manages ORCA lifecycle for a set of operations."""

    def __init__(self, orca: OrcaDLL):
        self._orca = orca

    def __enter__(self):
        self._orca.open_session()
        return self

    def __exit__(self, *args):
        self._orca.close_session()


def handle_list_entries(orca: OrcaDLL, params: dict) -> dict:
    """List all objects in a PBL."""
    pbl_path = params["pbl_path"]
    if not os.path.exists(pbl_path):
        return {"error": {"code": -4, "message": f"PBL file not found: {pbl_path}"}}

    entries = []

    def _dir_callback_fn(pentry, _userdata):
        e = pentry.contents
        entries.append({
            "name": e.lpszEntryName,
            "type": int(e.otEntryType),
            "typeLabel": TYPE_LABELS.get(int(e.otEntryType), f"Unknown({int(e.otEntryType)})"),
            "size": e.lEntrySize,
            "mtime": e.lCreateTime,
            "comment": e.szComments,
        })
    _dir_callback = PBORCA_LISTPROC(_dir_callback_fn)

    with OrcaSession(orca):
        # No configure_session — LibraryDirectory doesn't need it
        _send_log("DEBUG", "Session opened, calling set_library_list...")
        ret = orca.set_library_list([pbl_path])
        _send_log("DEBUG", f"set_library_list returned {ret}")
        if ret != PBORCA_OK:
            return {"error": {"code": ret, "message": f"SetLibraryList failed: {orca.get_error()}"}}
        _send_log("DEBUG", "Calling LibraryDirectory...")
        ret = orca.library_directory(pbl_path, _dir_callback)
        _send_log("DEBUG", f"LibraryDirectory returned {ret}, entries={len(entries)}")
        if ret != PBORCA_OK:
            return {"error": {"code": ret, "message": f"LibraryDirectory failed: {orca.get_error()}"}}

    return {"entries": entries, "count": len(entries)}


def handle_export_entries(orca: OrcaDLL, params: dict) -> dict:
    """Export specified entries from a PBL to a directory."""
    pbl_path = params["pbl_path"]
    out_dir = params["out_dir"]
    entries = params.get("entries", [])  # list of {"name": str, "type": int}
    encoding = params.get("encoding", PBORCA_UTF8)
    include_headers = params.get("include_headers", True)
    include_binary = params.get("include_binary", False)

    if not os.path.exists(pbl_path):
        return {"error": {"code": -4, "message": f"PBL file not found: {pbl_path}"}}

    os.makedirs(out_dir, exist_ok=True)

    exported = []
    errors = []
    total = len(entries)

    with OrcaSession(orca):
        config = PBORCA_CONFIG_SESSION()
        config.eClobber = PBORCA_CLOBBER_ALWAYS
        config.eExportEncoding = encoding
        config.bExportHeaders = 1 if include_headers else 0
        config.bExportIncludeBinary = 1 if include_binary else 0
        config.bExportCreateFile = 1  # ORCA writes files directly (avoids encoding issues)
        config.pExportDirectory = out_dir
        orca.configure_session(config)
        ret = orca.set_library_list([pbl_path])
        if ret != PBORCA_OK:
            return {"error": {"code": ret, "message": f"SetLibraryList failed: {orca.get_error()}"}}

        for i, entry in enumerate(entries):
            name = entry["name"]
            etype = entry["type"]
            _send_progress(i + 1, total, name)

            # ORCA writes directly to out_dir because bExportCreateFile=1
            ret = orca.export_entry(pbl_path, name, etype)
            if ret != PBORCA_OK:
                errors.append({"name": name, "type": etype, "error": f"ORCA error {ret}: {orca.get_error()}"})
                continue

            ext = SR_EXTENSIONS.get(etype, ".srx")
            filename = name + ext
            exported.append({"name": name, "type": etype, "file": filename})

    return {"exported": exported, "errors": errors, "total": total}


def handle_create_lib(orca: OrcaDLL, params: dict) -> dict:
    """Create a new empty PBL library."""
    lib_path = params.get("lib_path", "")
    comments = params.get("comments", "")
    if not lib_path:
        return {"error": {"code": -1, "message": "lib_path is required"}}

    with OrcaSession(orca):
        ret = orca._lib.PBORCA_LibraryCreate(orca._hSession, lib_path, comments)
        if ret == PBORCA_OK:
            return {"created": lib_path}
        return {"error": {"code": ret, "message": f"LibraryCreate failed: {orca.get_error()}"}}


def handle_ping(orca: OrcaDLL, params: dict) -> dict:
    """Test the ORCA connection."""
    try:
        with OrcaSession(orca):
            pass
        return {"pong": True, "status": "OK"}
    except Exception as e:
        return {"pong": False, "status": str(e)}


def handle_import_entries(orca: OrcaDLL, params: dict) -> dict:
    """Import SR source files into a PBL.

    Required params: pbl_path, src_dir, entries[]
    Optional: pbt_path (for library list + app), encoding, backup
    """
    pbl_path = params["pbl_path"]
    src_dir = params["src_dir"]
    entries = params.get("entries", [])  # [{"name": str, "type": int, "file": str}, ...]
    encoding = params.get("encoding", PBORCA_UTF8)
    pbt_path = params.get("pbt_path", "")
    do_backup = params.get("backup", True)

    if not os.path.exists(pbl_path):
        return {"error": {"code": -4, "message": f"PBL not found: {pbl_path}"}}

    # Normalize path to absolute with forward slashes
    pbl_path = os.path.abspath(pbl_path).replace("\\", "/")

    # Backup PBL
    if do_backup:
        backup_dir = os.path.join(os.path.dirname(pbl_path) or ".", "import-backup")
        os.makedirs(backup_dir, exist_ok=True)
        import time
        ts = time.strftime("%Y%m%d_%H%M%S")
        backup_name = os.path.basename(pbl_path) + "." + ts
        backup_path = os.path.join(backup_dir, backup_name)
        try:
            import shutil
            shutil.copy2(pbl_path, backup_path)
            _send_log("INFO", f"Backup: {backup_path}")
        except OSError as e:
            _send_log("WARN", f"Backup failed: {e}")

    # Resolve library list and application (normalize to forward slashes)
    lib_list = [pbl_path]
    app_name = ""
    app_lib = pbl_path

    def _norm(p):
        return p.replace("\\", "/")

    if pbt_path and os.path.exists(pbt_path):
        pbt = _parse_pbt_file(pbt_path)
        if pbt and pbt["lib_list"]:
            lib_list = [_norm(p) for p in pbt["lib_list"]]
            app_name = pbt["app_name"]
            app_lib = _norm(pbt["app_lib"])
            _send_log("INFO", f"PBT loaded: {len(lib_list)} libs, app={app_name}")

    imported = []
    compile_errors = []
    errors = []
    total = len(entries)

    # Make compile error callback
    _compile_errors_for_entry = []

    @PBORCA_ERRPROC
    def _err_callback(perr, _userdata):
        e = perr.contents
        _compile_errors_for_entry.append({
            "level": e.iLevel,
            "line": e.iLineNumber,
            "col": e.iColumnNumber,
            "number": e.lpszMessageNumber,
            "text": e.lpszMessageText,
        })

    with OrcaSession(orca):
        # Set library list
        ret = orca.set_library_list(lib_list)
        _send_log("DEBUG", f"Import lib_list={lib_list}, pbl_path={pbl_path}")
        if ret != PBORCA_OK:
            return {"error": {"code": ret, "message": f"SetLibraryList failed: {orca.get_error()}"}}

        # Auto-detect application if not provided
        if not app_name:
            app_entries = []
            @PBORCA_LISTPROC
            def _app_cb(pentry, _userdata):
                e = pentry.contents
                if int(e.otEntryType) == PBORCA_APPLICATION:
                    app_entries.append(e.lpszEntryName)
            orca.library_directory(pbl_path, _app_cb)
            if app_entries:
                app_name = app_entries[0]
                _send_log("INFO", f"Auto-detected app: {app_name}")
            else:
                # No existing app — try to infer from the first APPLICATION import
                for entry in entries:
                    if entry["type"] == PBORCA_APPLICATION:
                        app_name = entry["name"]
                        _send_log("INFO", f"Inferred app from import: {app_name}")
                        break

        # PB10 ORCA REQUIRES SessionSetCurrentAppl before CompileEntryImport.
        # Set it even if the app doesn't exist yet — PB10 records it prospectively.
        if app_name and app_lib:
            ret_app = orca.set_current_appl(app_lib, app_name)
            if ret_app != PBORCA_OK:
                _send_log("WARN", f"SetCurrentAppl returned {ret_app}, continuing anyway")
            else:
                _send_log("INFO", f"Set app: {app_name}")

        for i, entry in enumerate(entries):
            name = entry["name"]
            etype = entry["type"]
            file_name = entry.get("file", "")
            file_path = _norm(os.path.join(src_dir, file_name))
            _send_progress(i + 1, total, name)

            if not os.path.exists(file_path):
                errors.append({"name": name, "type": etype, "error": f"SR file not found: {file_path}"})
                continue

            # Read source file as raw bytes
            try:
                with open(file_path, "rb") as f:
                    syntax = f.read()
            except OSError as e:
                errors.append({"name": name, "type": etype, "error": str(e)})
                continue

            # Extract comments from $PBExportComments$ header line
            comments = ""
            try:
                text = syntax.decode("utf-8-sig", errors="replace")
                for line in text.split("\n"):
                    line = line.strip()
                    if line.startswith("$PBExportComments$"):
                        comments = line[len("$PBExportComments$"):]
                        break
                    if line.startswith("$PBExportHeader$"):
                        continue
                    if line and not line.startswith("$"):
                        break
            except Exception:
                pass

            _compile_errors_for_entry.clear()
            ret = orca.compile_entry_import(
                pbl_path, name, etype, comments, syntax,
                err_callback=_err_callback if _compile_errors_for_entry is not None else None
            )

            if ret == PBORCA_OK:
                if _compile_errors_for_entry:
                    compile_errors.append({
                        "name": name, "type": etype,
                        "diagnostics": list(_compile_errors_for_entry),
                    })
                imported.append({"name": name, "type": etype})
            elif ret == PBORCA_COMPERROR:
                compile_errors.append({
                    "name": name, "type": etype,
                    "diagnostics": list(_compile_errors_for_entry),
                })
                imported.append({"name": name, "type": etype, "status": "imported_with_errors"})
            else:
                errors.append({
                    "name": name, "type": etype,
                    "error": f"ORCA error {ret}: {orca.get_error()}"
                })

    return {
        "imported": imported,
        "compile_errors": compile_errors,
        "errors": errors,
        "total": total,
    }


# ──────────────────────────────────────────────
# Main loop
# ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="ORCA Worker (32-bit)")
    parser.add_argument("--ide", required=True, help="PB IDE/ORCA directory")
    parser.add_argument("--runtime", required=True, help="PB Runtime directory (same as IDE for PB10)")
    parser.add_argument("--pb-version", default="25", choices=["10", "25"],
                        help="PB version: 10 or 25 (default)")
    args = parser.parse_args()

    ide_path = args.ide
    runtime_path = args.runtime
    pb_version = args.pb_version

    # Validate
    dll_name = "pborc100.dll" if pb_version == "10" else "pborc.dll"
    dll_path = os.path.join(ide_path, dll_name)
    if not os.path.exists(dll_path):
        _send_response(0, error={"code": -99, "message": f"{dll_name} not found at {dll_path}"})
        sys.exit(1)

    try:
        orca = OrcaDLL(ide_path, runtime_path, pb_version)
    except Exception as e:
        _send_response(0, error={"code": -99, "message": f"Failed to load {dll_name}: {e}"})
        sys.exit(1)

    # Signal ready (write directly to buffer to avoid TextIOWrapper delay)
    _send_log("INFO", f"Worker started. IDE={ide_path}, Runtime={runtime_path}")

    handlers = {
        "ping": handle_ping,
        "create_lib": handle_create_lib,
        "list_entries": handle_list_entries,
        "export_entries": handle_export_entries,
        "import_entries": handle_import_entries,
    }

    # Read JSON requests line by line from stdin (binary mode to avoid buffering)
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            break
        line = line.decode("utf-8").strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            _send_response(0, error={"code": -99, "message": "Invalid JSON"})
            continue

        req_id = req.get("id", 0)
        method = req.get("method", "")
        params = req.get("params", {})

        if method == "shutdown":
            _send_response(req_id, result={"status": "shutting down"})
            break

        handler = handlers.get(method)
        if handler is None:
            _send_response(req_id, error={"code": -99, "message": f"Unknown method: {method}"})
            continue

        try:
            result = handler(orca, params)
            _send_response(req_id, result=result)
        except Exception as e:
            _send_response(req_id, error={"code": -99, "message": str(e)})

    _send_log("INFO", "Worker shut down.")


if __name__ == "__main__":
    main()
