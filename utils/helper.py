import base64

# Encode/Decode Base64
def encode_base64(data: str) -> str:
    """Encodes a string to Base64."""
    return base64.b64encode(data.encode(encoding="utf-8")).decode(encoding="utf-8")

def decode_base64(data: str) -> str:
    """Decodes a Base64 encoded string."""
    return base64.b64decode(data.encode(encoding="utf-8")).decode(encoding="utf-8")

from typing import Any, Dict
import re
# Builder
_PY_TYPES = {
    "str": str, "string": str,
    "int": int, "integer": int,
    "float": float, "number": float,
    "bool": bool, "boolean": bool,
    "dict": dict, "list": list,
}

def to_py_type(t: Any) -> type:
    """
    Convert a type specification to a Python type.
    """
    if isinstance(t, type):
        return t
    if isinstance(t, str):
        return _PY_TYPES.get(t.lower(), str)
    return str

def _spec_get(spec: Any, key: str, default: Any = None):
    # supports both dict-like and attr-like specs
    if isinstance(spec, dict):
        return spec.get(key, default)
    return getattr(spec, key, default)

def _sanitize_name(name: str) -> str:
    """Sanitize name to match the required pattern ^[^\\s<|\\\\/>]+$"""
    # Replace spaces and invalid characters with underscores
    sanitized = re.sub(r'[\s<|\\/>]+', '_', name)
    # Remove any remaining invalid characters and ensure it's not empty
    sanitized = re.sub(r'[^\w\-_]', '', sanitized)
    # Ensure it doesn't start or end with underscore and has content
    sanitized = sanitized.strip('_')
    return sanitized if sanitized else 'unnamed_tool'