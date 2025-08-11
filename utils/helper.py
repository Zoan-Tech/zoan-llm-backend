import base64
from cryptography.fernet import Fernet

# Encode/Decode Base64
def encode_base64(data: str) -> str:
    """Encodes a string to Base64."""
    return base64.b64encode(data.encode(encoding="utf-8")).decode(encoding="utf-8")

def decode_base64(data: str) -> str:
    """Decodes a Base64 encoded string."""
    return base64.b64decode(data.encode(encoding="utf-8")).decode(encoding="utf-8")

def decrypt_token(encrypted_token: str, key: str) -> str:
    """Decrypts an encrypted token using the provided key."""
    f = Fernet(key.encode())
    return f.decrypt(encrypted_token.encode()).decode()

from typing import Any, Dict
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