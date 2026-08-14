"""PowerBuilder ORCA API enumerations and type mappings."""

import enum


class PBORCA_TYPE(enum.IntEnum):
    """Object type enumerations matching pborca.h."""
    APPLICATION = 0
    DATAWINDOW = 1
    FUNCTION = 2
    MENU = 3
    QUERY = 4
    STRUCTURE = 5
    USEROBJECT = 6
    WINDOW = 7
    PIPELINE = 8
    PROJECT = 9
    PROXYOBJECT = 10
    BINARY = 11


class PBORCA_ENCODING(enum.IntEnum):
    """Export/Import encoding options."""
    UNICODE = 0
    UTF8 = 1
    HEXASCII = 2
    ANSI_DBCS = 3


class PBORCA_CLOBBER(enum.IntEnum):
    """File overwrite behaviour."""
    NOCLOBBER = 0
    CLOBBER = 1
    CLOBBER_ALWAYS = 2
    DECIDED_BY_SYSTEM = 3


# SR file extension for each object type
SR_EXTENSIONS = {
    PBORCA_TYPE.APPLICATION:  ".sra",
    PBORCA_TYPE.DATAWINDOW:   ".srd",
    PBORCA_TYPE.FUNCTION:     ".srf",
    PBORCA_TYPE.MENU:         ".srm",
    PBORCA_TYPE.QUERY:        ".srq",
    PBORCA_TYPE.STRUCTURE:    ".srs",
    PBORCA_TYPE.USEROBJECT:   ".sru",
    PBORCA_TYPE.WINDOW:       ".srw",
    PBORCA_TYPE.PIPELINE:     ".srp",
    PBORCA_TYPE.PROJECT:      ".srj",
    PBORCA_TYPE.PROXYOBJECT:  ".srx",
    PBORCA_TYPE.BINARY:       ".bin",
}

# Human-readable labels for each type
TYPE_LABELS = {
    PBORCA_TYPE.APPLICATION:  "Application",
    PBORCA_TYPE.DATAWINDOW:   "DataWindow",
    PBORCA_TYPE.FUNCTION:     "Function",
    PBORCA_TYPE.MENU:         "Menu",
    PBORCA_TYPE.QUERY:        "Query",
    PBORCA_TYPE.STRUCTURE:    "Structure",
    PBORCA_TYPE.USEROBJECT:   "UserObject",
    PBORCA_TYPE.WINDOW:       "Window",
    PBORCA_TYPE.PIPELINE:     "Pipeline",
    PBORCA_TYPE.PROJECT:      "Project",
    PBORCA_TYPE.PROXYOBJECT:  "ProxyObject",
    PBORCA_TYPE.BINARY:       "Binary",
}

# Shared encoding name → int mapping (used by Browse/Import/Settings tabs)
ENC_MAP = {"UTF8": 1, "UNICODE": 0, "ANSI_DBCS": 3, "HEXASCII": 2}

# ORCA error codes
ORCA_ERRORS = {
    0:    "PBORCA_OK",
    -1:   "PBORCA_INVALIDPARMS",
    -2:   "PBORCA_DUPOPERATION",
    -3:   "PBORCA_OBJNOTFOUND",
    -4:   "PBORCA_BADLIBRARY",
    -5:   "PBORCA_LIBLISTNOTSET",
    -6:   "PBORCA_LIBNOTINLIST",
    -7:   "PBORCA_LIBIOERROR",
    -8:   "PBORCA_OBJEXISTS",
    -9:   "PBORCA_INVALIDNAME",
    -10:  "PBORCA_BUFFERTOOSMALL",
    -11:  "PBORCA_COMPERROR",
    -12:  "PBORCA_LINKERROR",
    -13:  "PBORCA_CURRAPPLNOTSET",
    -14:  "PBORCA_OBJHASNOANCS",
    -15:  "PBORCA_OBJHASNOREFS",
    -16:  "PBORCA_PBDCOUNTERROR",
    -17:  "PBORCA_PBDCREATERROR",
}


def get_extension(obj_type: PBORCA_TYPE) -> str:
    """Get the SR file extension for an object type."""
    return SR_EXTENSIONS.get(obj_type, ".srx")


def get_type_label(obj_type: PBORCA_TYPE) -> str:
    """Get a human-readable label for an object type."""
    return TYPE_LABELS.get(obj_type, f"Unknown({int(obj_type)})")


def get_orca_error_name(code: int) -> str:
    """Get the symbolic name for an ORCA error code."""
    return ORCA_ERRORS.get(code, f"UNKNOWN({code})")
