# CareLens AI - Security and privacy notes

## What is protected
| Area | Protection |
|---|---|
| Passwords | Salted hashes; common passwords and password = login ID are rejected; per-IP and per-account throttling |
| Sessions | SameSite=Strict cookie, 60-minute idle timeout (`CARELENS_IDLE_MINUTES`), 7-day absolute limit, "sign out of all devices" |
| Requests | Host allowlist (anti DNS-rebinding), strict Origin and Sec-Fetch-Site checks, 256 KB JSON limit, rate limits |
| Browser | CSP, frame deny, nosniff, no-referrer, Permissions-Policy, `Cache-Control: no-store` on API responses, HSTS over HTTPS |
| Documents | Encrypted at rest; PDFs with scripts/launch/embedded files are refused; image and page caps; sandboxed image serving |
| AI assistant | Server-side safety guard before any provider call; blocked text is not stored; output guard; shared-document injection detector |
| AI privacy | Only relevant records are sent; phone, email, Aadhaar/PAN-style IDs and card numbers are removed from the outgoing copy (`CARELENS_REDACT=0` turns this off) |
| Audit | `security_events` table (no health data, no message text), visible to you in Settings -> Security |

## Encryption key - back it up
Documents and the saved AI key are encrypted with a key in `backend/instance/data_key` (or `CARELENS_DATA_KEY`).
**Copy that file somewhere safe.** If it is lost, encrypted documents cannot be recovered. Do not store it next to the database backup.

To encrypt documents uploaded before this version (stop the backend first, and back up `backend/instance`):

    cd backend
    python encrypt_existing.py --check    # shows what would change
    python encrypt_existing.py            # encrypts, verifies by decrypting, then swaps each file atomically

Original files are left untouched if verification fails. Nothing in the database changes.

## Settings (all optional, see `backend/.env.example`)
`CARELENS_DATA_KEY`, `CARELENS_IDLE_MINUTES`, `CARELENS_ALLOWED_HOSTS`, `CARELENS_ALLOWED_ORIGINS`, `FAMILY_COOKIE_SECURE=1` (when served over HTTPS), `CARELENS_REDACT`, `CARELENS_SEED_DEMO`.

## Known limits (please read)
- **Database text is not encrypted** (names, medicines, notes, extracted document text). Turn on full-disk encryption (BitLocker on Windows, FileVault on Mac, LUKS on Linux) and keep the computer locked.
- **AI prompts leave your computer** when an AI key is set: relevant record text goes to the provider you chose (Gemini, Anthropic or OpenAI) under that provider's terms. Identifiers are stripped, but health details in the text are still sent. Without a key the assistant works offline and nothing is sent.
- Redaction is pattern-based and cannot catch every personal detail (for example a name written inside a sentence).
- Run the app on `127.0.0.1` for one computer. If you expose it on a network, put it behind HTTPS and set the allowed hosts and origins.
- The safety guard is keyword-based and deterministic. It blocks clear cases in 7 languages; it is a safety net, not a guarantee.
