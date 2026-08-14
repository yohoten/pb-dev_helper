"""High-level operations built on top of OrcaRpcClient."""

from orca.rpc_client import OrcaRpcClient


class OrcaSession:
    """Convenience wrapper with typed methods for common ORCA operations."""

    def __init__(self, client: OrcaRpcClient):
        self._client = client

    def ping(self) -> dict:
        return self._client.call("ping", {})

    def create_lib(self, lib_path: str, comments: str = "") -> dict:
        """Create a new empty PBL library.
        Returns: {"created": path} or {"error": ...}
        """
        return self._client.call("create_lib", {
            "lib_path": lib_path,
            "comments": comments,
        })

    def list_entries(self, pbl_path: str) -> dict:
        """Get all entries from a PBL file.
        Returns: {"entries": [{name, type, typeLabel, size, mtime, comment}, ...], "count": N}
        """
        return self._client.call("list_entries", {"pbl_path": pbl_path})

    def export_entries(self, pbl_path: str, out_dir: str, entries: list[dict],
                       encoding: int = 1, include_headers: bool = True,
                       include_binary: bool = False) -> dict:
        """Export entries to SR files.
        Returns: {"exported": [{name, type, file}, ...], "errors": [...], "total": N}
        """
        return self._client.call("export_entries", {
            "pbl_path": pbl_path,
            "out_dir": out_dir,
            "entries": entries,
            "encoding": encoding,
            "include_headers": include_headers,
            "include_binary": include_binary,
        })

    def import_entries(self, pbl_path: str, src_dir: str, entries: list[dict],
                       encoding: int = 1, pbt_path: str = "",
                       backup: bool = True) -> dict:
        """Import SR source files into a PBL.
        Returns: {"imported": [...], "compile_errors": [...], "errors": [...], "total": N}
        """
        return self._client.call("import_entries", {
            "pbl_path": pbl_path,
            "src_dir": src_dir,
            "entries": entries,
            "encoding": encoding,
            "pbt_path": pbt_path,
            "backup": backup,
        })
