"""Encryption at rest for the two most sensitive files: uploaded documents and the saved AI key.

* Algorithm: Fernet (AES-128-CBC + HMAC-SHA256) from the `cryptography` package.
* Key: CARELENS_DATA_KEY (urlsafe-base64, 32 bytes) if set, otherwise a random key created once in
  instance/data_key (owner-only permissions). Keep a backup of that key: without it encrypted files
  cannot be opened. For the strongest setup keep the key outside the data folder (set the env variable).
* Backward compatible: files written before this version are plain bytes and are still read as they are.
  Encrypted files start with MAGIC, so the two kinds are told apart without guessing.
* If `cryptography` is not installed the app keeps working exactly as before (files stay plain) and
  says so in the log; it never refuses to start because of this.
"""
import contextlib
import logging
import os
import shutil
import tempfile
from pathlib import Path

from flask import current_app

log = logging.getLogger("carelens.crypto")

MAGIC = b"CLENC1\n"

try:  # optional dependency
    from cryptography.fernet import Fernet, InvalidToken
except ImportError:  # pragma: no cover - depends on the machine
    Fernet = None

    class InvalidToken(Exception):
        pass


class DecryptionError(Exception):
    """An encrypted file could not be opened (missing library, wrong key or damaged file)."""


_cache = {}


def available():
    return Fernet is not None


def _key_path():
    return Path(current_app.instance_path) / "data_key"


def _load_key():
    env = os.environ.get("CARELENS_DATA_KEY", "").strip()
    if env:
        return env.encode()
    path = _key_path()
    if path.exists():
        return path.read_text().strip().encode()
    key = Fernet.generate_key()
    path.parent.mkdir(parents=True, exist_ok=True)
    # create exclusively so two processes cannot overwrite each other's key
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as fh:
            fh.write(key)
    except FileExistsError:
        return path.read_text().strip().encode()
    return key


def _fernet():
    if Fernet is None:
        raise DecryptionError("The 'cryptography' package is not installed.")
    ident = (os.environ.get("CARELENS_DATA_KEY", ""), str(_key_path()))
    f = _cache.get(ident)
    if f is None:
        try:
            f = Fernet(_load_key())
        except (ValueError, TypeError) as exc:
            raise DecryptionError("The data key is not valid.") from exc
        _cache.clear()
        _cache[ident] = f
    return f


def is_encrypted(blob):
    return blob.startswith(MAGIC)


def encrypt_bytes(data):
    """Encrypt when possible; otherwise return the data unchanged (see module docstring)."""
    if Fernet is None:
        log.warning("cryptography is not installed: data is stored without encryption. Run: pip install cryptography")
        return data
    return MAGIC + _fernet().encrypt(data)


def decrypt_bytes(blob):
    """Plain bytes for either kind of file."""
    if not is_encrypted(blob):
        return blob
    try:
        return _fernet().decrypt(blob[len(MAGIC):])
    except InvalidToken as exc:
        raise DecryptionError("This file can't be decrypted with the current key.") from exc


def read_file(path):
    return decrypt_bytes(Path(path).read_bytes())


def write_file_atomic(path, data, mode=0o600):
    """Write bytes via a temp file in the same folder, then swap it in. Never leaves a half-written file."""
    path = Path(path)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        with contextlib.suppress(OSError):
            os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


@contextlib.contextmanager
def plain_path(path):
    """A filesystem path holding the decrypted bytes (for libraries that need a real file).

    Plain legacy files are yielded as they are; encrypted ones are decrypted into a private temp folder that is
    removed afterwards."""
    path = Path(path)
    with open(path, "rb") as fh:
        head = fh.read(len(MAGIC))
    if head != MAGIC:
        yield path
        return
    tmp = Path(tempfile.mkdtemp(prefix="carelens-"))
    try:
        out = tmp / ("file" + path.suffix)
        out.write_bytes(decrypt_bytes(path.read_bytes()))
        yield out
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
