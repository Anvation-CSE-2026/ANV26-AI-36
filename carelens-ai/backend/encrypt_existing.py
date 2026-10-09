"""Encrypt documents that were uploaded before encryption at rest was added. Safe to run more than once.

    python encrypt_existing.py            # encrypt every plain file in backend/instance/uploads
    python encrypt_existing.py --check    # only report what would change

For each plain file the script encrypts it, DECRYPTS the result and compares it with the original, and only then
swaps it in (atomically). If anything differs the original file is left untouched. Nothing in the database changes.
Stop the backend first, and keep a copy of backend/instance/data_key (or your CARELENS_DATA_KEY): without it
encrypted documents cannot be opened.
"""
import sys
from pathlib import Path

from app import create_app
import crypto


def main(check_only):
    if not crypto.available():
        print("The 'cryptography' package is missing. Run: pip install -r requirements.txt")
        return 1
    app = create_app()
    root = Path(app.config["UPLOAD_DIR"])
    done = skipped = failed = 0
    with app.app_context():
        for f in sorted(p for p in root.rglob("*") if p.is_file() and not p.name.startswith(".tmp-")):
            raw = f.read_bytes()
            if crypto.is_encrypted(raw):
                skipped += 1
                continue
            if check_only:
                print("would encrypt", f.relative_to(root))
                done += 1
                continue
            blob = crypto.encrypt_bytes(raw)
            if crypto.decrypt_bytes(blob) != raw:
                print("VERIFY FAILED, left unchanged:", f.relative_to(root))
                failed += 1
                continue
            crypto.write_file_atomic(f, blob)
            done += 1
    verb = "to encrypt" if check_only else "encrypted"
    print(f"{done} file(s) {verb}, {skipped} already encrypted, {failed} failed.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main("--check" in sys.argv))
