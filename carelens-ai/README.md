# CareLens AI

**Turning health information into smarter, safer family care.**

CareLens AI is a private, family-first health organiser. Keep medical documents, medicines, reminders and emergency details in one place, share only what you choose with family members, and ask an AI assistant to explain your own records in plain language, in your own language.

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3-000000?logo=flask)
![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)
![Vite](https://img.shields.io/badge/Vite-frontend-646CFF?logo=vite&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-database-003B57?logo=sqlite&logoColor=white)
![Tests](https://img.shields.io/badge/tests-98%20passing-brightgreen)
![Privacy](https://img.shields.io/badge/privacy-local--first-blue)

> **Not medical advice.** CareLens AI explains and organises information you give it. It does not diagnose, predict disease, or change medicines. Always talk to a doctor or pharmacist about medical decisions.

---

## Table of contents

1. [Why CareLens AI](#why-carelens-ai)
2. [Features](#features)
3. [Privacy and security at a glance](#privacy-and-security-at-a-glance)
4. [Tech stack](#tech-stack)
5. [Architecture](#architecture)
6. [Quick start](#quick-start)
7. [Free demo deployment](#free-demo-deployment-render)
8. [Configuration](#configuration)
9. [AI assistant setup](#ai-assistant-setup)
10. [How the assistant stays safe](#how-the-assistant-stays-safe)
11. [Encryption and key backup](#encryption-and-key-backup)
12. [Sharing model](#sharing-model)
13. [API overview](#api-overview)
14. [Project structure](#project-structure)
15. [Testing](#testing)
16. [Upgrading an existing installation](#upgrading-an-existing-installation)
17. [Known limitations](#known-limitations)
18. [Roadmap](#roadmap)
19. [Contributing](#contributing)
20. [Reporting a vulnerability](#reporting-a-vulnerability)
21. [License](#license)

---

## Why CareLens AI

Families often manage health records across paper files, photos, WhatsApp forwards and memory. That is hard to search, easy to lose, and risky to share. CareLens AI is built around three ideas:

- **One organised place** for reports, prescriptions, medicines, reminders and emergency information.
- **Privacy by default.** Every record belongs to one person. Family membership alone grants nothing; access exists only when its owner explicitly shares it, and can be revoked any time.
- **A careful assistant.** The AI answers only from the user's own records, explains in simple words, refuses requests that could harm a patient, and never receives more personal data than it needs.

---

## Features

### Records and documents
- Upload **PDF, JPG and PNG** documents with automatic **text extraction and OCR** for scans.
- Structured findings and medicine extraction. Extracted medicines stay *unverified* until you confirm them.
- Search across your documents and records.
- Timeline view of your health history.

### Medicines and reminders
- Medicine list with dosage details and active/inactive status.
- Reminders for medicines, appointments and follow-ups.

### Health profile and emergency
- Health profile (blood group, allergies, conditions, history).
- Emergency information and emergency contacts.

### Family accounts
- Create a family with a primary member and additional members, each with their own login.
- **Sharing with grants:** share a document, medicines, health profile or emergency info with chosen members, for a chosen duration, and stop any time.

### AI assistant
- Works with **Google Gemini, Anthropic Claude or OpenAI** (you bring your own key).
- Floating **voice assistant** on every signed-in page, plus a full Assistant page.
- Summarise or read a report aloud, in plain language.
- Answers grounded in your own records, with the sources it used.
- **Offline mode** when no key is set: shows matching text from your own records, nothing leaves your computer.

### Diet and wellness
- Diet guidance and a **Wellness and Therapies plan** from your own goals and confirmed facts.
- Facts are quote-checked against your document text; plan items are labelled as AI suggestions and are editable.
- Replies that claim a cure, change medicines or contain a recorded allergen are dropped by the server.

### Languages
- Full interface in **English, Hindi and Kannada**.
- AI answers, explanations and spoken output in **8 languages**: English, Hindi, Kannada, Tamil, Telugu, Malayalam, Marathi and Bengali.

---

## Privacy and security at a glance

| Area | What CareLens does |
|---|---|
| **Ownership** | Every record has an `owner_id`. `/api/me/*` endpoints only touch the signed-in user's rows. |
| **Sharing** | Cross-member access only through an active, unexpired, unrevoked grant, checked on every request (`access.py`), same family only. |
| **Passwords** | Salted hashes; common passwords and "password equals login ID" are rejected. |
| **Login protection** | Per-IP and per-account throttling (across IPs); events recorded. |
| **Sessions** | `SameSite=Strict` cookie, 60-minute idle timeout (configurable), 7-day absolute limit, **Sign out of all devices**. |
| **Request hardening** | Host-header allowlist (anti DNS-rebinding), strict `Origin` and `Sec-Fetch-Site` checks, 256 KB JSON limit, per-user/IP rate limits. |
| **Browser hardening** | CSP, `X-Frame-Options` deny, `nosniff`, `Referrer-Policy: no-referrer`, Permissions-Policy, `Cache-Control: no-store` on API responses, HSTS over HTTPS. |
| **Uploads** | PDFs containing JavaScript, launch actions, embedded files, rich media or XFA are refused; image pixel cap; PDF page cap; limited processing workers; images served with a sandbox CSP. |
| **Encryption at rest** | Uploaded documents and the saved AI key are encrypted with Fernet (AES-based, authenticated). |
| **AI data minimisation** | Only records relevant to the question are sent. Phone numbers, emails, Aadhaar/PAN-style IDs and card numbers are removed from the outgoing copy. Stored data is never altered. |
| **Assistant safety** | Server-side guard blocks harmful requests before any provider call; blocked text is not stored. |
| **Audit** | `security_events` table (no health data, no message text) shown to you in **Settings → Security**. |
| **Safe defaults** | Debug mode removed; owner-only file permissions; no demo account unless you ask for one. |

See [`SECURITY.md`](SECURITY.md) for details and limits.

---

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | React 18, Vite |
| Backend | Python, Flask 3 |
| Database | SQLite with versioned, additive migrations |
| Encryption | `cryptography` (Fernet) |
| Document processing | PDF text extraction, Tesseract OCR and Poppler (optional, for scans) |
| AI providers | Google Gemini, Anthropic Claude, OpenAI (user-supplied key) |
| Voice | Browser built-in speech recognition and speech synthesis |

---

## Architecture

```text
┌────────────────────────┐        ┌──────────────────────────────────────────┐
│  Browser (React + Vite)│  HTTPS │  Flask backend (127.0.0.1:5000)          │
│  • Pages / components  │◄──────►│  security.py  Host/Origin checks, headers│
│  • Floating assistant  │  JSON  │  auth.py      sessions, idle timeout     │
│  • Browser TTS / STT   │        │  access.py    ownership + share grants   │
└────────────────────────┘        │  routes/      auth, care, health, docs,  │
                                  │               sharing, ai, wellness      │
                                  │  safety.py    request guard + redaction  │
                                  │  crypto.py    encryption at rest         │
                                  │  services/    extraction, ai, wellness   │
                                  └───────┬───────────────┬─────────────────┘
                                          │               │
                              ┌───────────▼──┐   ┌────────▼─────────┐
                              │ SQLite (db)  │   │ Encrypted uploads│
                              └──────────────┘   └──────────────────┘
                                          │ (only if a key is set)
                                          ▼
                              Gemini / Anthropic / OpenAI
                              (guarded and redacted copy of
                               relevant record text only)
```

**Assistant request flow**

1. The request passes Host, Origin and rate-limit checks.
2. `safety.py` screens the message (self-harm, harm to others or a patient, privacy attacks, prompt injection).
3. If blocked: a fixed reply is returned, the text is not stored, and nothing reaches the provider.
4. Otherwise relevant records are retrieved (only the user's own, or one explicitly shared document).
5. Context is neutralised, identifiers are redacted, and the copy is sent to the provider.
6. The reply passes an output guard before it is stored and shown.

---

## Quick start

### Requirements

- Python 3.10 or newer (tested on 3.12)
- Node.js 18 or newer
- Optional, for scanned documents: [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) (Windows: UB-Mannheim build) and Poppler (`pdftoppm`) on your `PATH`

### One-step start

```bash
# Mac / Linux
./start.sh

# Windows: double-click start.bat
```

Open <http://localhost:5173> and choose **Register** to create your family.

No sample account is created automatically (it would have a known password). For a demo with fake data only:

```bash
CARELENS_SEED_DEMO=1 ./start.sh        # Windows: set CARELENS_SEED_DEMO=1 then run start.bat
# demo login: meena / sample-pass-1  (never store real information in the demo)
```

### Run manually

```bash
# Backend
cd backend
pip install -r requirements.txt
python app.py                      # http://127.0.0.1:5000

# Frontend (second terminal)
cd frontend
npm install
npm run dev                        # http://localhost:5173
```

### Single-process (production-style) mode

```bash
cd frontend && npm install && npm run build
cd ../backend && python app.py     # serves the built app on http://127.0.0.1:5000
```

> After pulling changes that touch `frontend/src`, rebuild with `npm run build` so the served app includes them (for example the Security panel).

---

## Free demo deployment (Render)

The repository-root `render.yaml` configures a free Render web service. Push the repository to GitHub, then in Render choose **New → Blueprint Instance** and select the repository and branch.

Free services sleep when idle and use ephemeral storage. The local SQLite database, uploaded documents, encryption keys and saved AI settings can be lost on spin-down, restart or redeploy. Use fictional demo data only; this setup is not suitable for real health records or production. Persistent storage requires a paid service with a persistent disk; keep disk-backed encryption keys safe.

---

## Configuration

Copy `backend/.env.example` to `backend/.env` (the start scripts do this for you). All settings are optional.

| Variable | Purpose | Default |
|---|---|---|
| `GEMINI_API_KEY` / `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` | Enable the AI assistant (or set the key in the app) | none (offline mode) |
| `CARELENS_PROVIDER` | Force a provider: `gemini`, `anthropic`, `openai` | auto |
| `CARELENS_MODEL` | Force a model name | auto |
| `CARELENS_DATA_KEY` | Your own Fernet key for encryption at rest | auto-created in `instance/data_key` |
| `CARELENS_IDLE_MINUTES` | Inactivity before sign-out (`0` = never) | `60` |
| `CARELENS_ALLOWED_HOSTS` | Extra hostnames allowed (comma-separated) | `localhost`, `127.0.0.1` |
| `CARELENS_ALLOWED_ORIGINS` | Extra browser origins allowed (comma-separated) | local origins |
| `FAMILY_COOKIE_SECURE` | Set to `1` when served over HTTPS | off |
| `CARELENS_REDACT` | Strip identifiers from text sent to the AI (`0` = send as is) | `1` |
| `CARELENS_SEED_DEMO` | Create the sample family in the start scripts | off |

Generate your own encryption key:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

---

## AI assistant setup

1. Sign in as the **primary member**.
2. Go to **Settings → AI assistant**.
3. Choose a provider (Gemini has a free tier), paste the key and click **Save and test**.

It works immediately, with no restart. The key is stored **encrypted** in `backend/instance/ai_config.json`; only its last four characters are ever shown back to you. Leave **Model** empty and CareLens picks a working Gemini model automatically.

Without a key the assistant runs in a clearly labelled **offline mode**: it shows matching passages from your own records and sends nothing anywhere. Report explanations, diet guidance and wellness plans need a key.

---

## How the assistant stays safe

The guard in `backend/safety.py` is deterministic (no AI call needed) and runs on the server before anything reaches a provider.

| Category | Examples of what is stopped | What the user sees |
|---|---|---|
| Self-harm | Requests for methods or lethal amounts | A supportive message with **Tele-MANAS 14416** and **112** |
| Harm to others or a patient | Secretly giving medicine, poisoning, withholding care | "This request has been abandoned." |
| Privacy attacks | Reading another member's records, bypassing sharing, stealing passwords or keys | "This request has been abandoned." |
| Prompt injection | "Ignore previous instructions", revealing the system prompt | "This request has been abandoned." |

Details:

- Text is normalised first (Unicode look-alikes, zero-width characters, spaced-out letters) so simple evasion does not work.
- Keywords cover English, Hindi, Kannada, Tamil, Telugu, Malayalam and Bengali.
- Normal safety questions still work, for example "What is the maximum daily dose of paracetamol?" or "How do I stop taking my tablets safely?".
- Blocked messages are **not stored**.
- Shared documents written by someone else are scanned for instructions aimed at the assistant; if found, the document is withheld from the assistant.
- An output guard checks replies before they are saved.

The guard is a safety net, not a guarantee. See [Known limitations](#known-limitations).

---

## Encryption and key backup

Uploaded documents and the saved AI key are encrypted at rest. The key lives in `backend/instance/data_key` (or `CARELENS_DATA_KEY`).

> **Back up `data_key` somewhere safe and separate from your database backups.** If it is lost, encrypted documents cannot be recovered.

Existing plain files keep working. To encrypt documents uploaded before encryption existed:

```bash
# Stop the backend first and back up backend/instance
cd backend
python encrypt_existing.py --check    # report only
python encrypt_existing.py            # encrypt, verify by decrypting, swap atomically
```

If verification fails for any file, that original file is left untouched. The database is not modified.

---

## Sharing model

- Every record has an owner. Nobody else can read it by default, including family members.
- A share is a **grant** with a resource, a grantee and an optional expiry. Grants can be revoked at any time.
- Each request re-checks the grant: active, unexpired, unrevoked, same family.
- People you share a document with can ask the assistant about it or get an explanation in their own language.
- Anything shared with the assistant from another person's document is scanned for injected instructions first.

---

## API overview

All endpoints are under `/api`. Authentication uses a session cookie; state-changing requests must pass Origin checks.

| Area | Examples |
|---|---|
| Auth | `POST /api/families`, `POST /api/auth/login`, `GET /api/auth/me` |
| Documents | `/api/me/documents` (upload, list, details, delete) |
| Health | `/api/me/health`, `/api/me/health/records`, `/api/me/emergency` |
| Medicines and reminders | `/api/me/medicines`, `/api/me/reminders` |
| Diet and wellness | `/api/me/diet`, `/api/me/wellness` |
| Sharing | `/api/sharing` |
| Assistant | `POST /api/ai/chat` |
| Security | `GET /api/me/security`, `POST /api/me/security/sign-out-everywhere` |

Errors are returned as JSON with `error.code` and `error.message`; validation errors include per-field messages.

---

## Project structure

```text
carelens-ai/
├── start.sh / start.bat          # one-step launchers
├── SECURITY.md                   # security and privacy notes
├── backend/
│   ├── app.py                    # app factory, cookies, blueprints
│   ├── db.py                     # SQLite + additive migrations
│   ├── auth.py                   # sessions, idle timeout
│   ├── access.py                 # ownership and share-grant checks
│   ├── security.py               # headers, Host/Origin checks, rate limits, audit events
│   ├── safety.py                 # assistant guard, injection detection, redaction
│   ├── crypto.py                 # encryption at rest
│   ├── encrypt_existing.py       # opt-in encryption of older uploads
│   ├── seed_demo.py              # optional sample family
│   ├── routes/                   # auth, care, family, health, personal, search, sharing, ai, wellness
│   ├── services/                 # extraction, structured, documents, ai, wellness, samplepdf
│   └── tests/                    # 98 tests
└── frontend/
    └── src/                      # api/, auth/, components/, layouts/, pages/, i18n.js, voice.js
```

---

## Testing

```bash
cd backend
pip install -r requirements.txt
python -m unittest discover -s tests -t .
```

The suite (98 tests) covers the API, documents and extraction, reminders and medicines, wellness, voice, seeded data, and the security layer: the assistant guard (including multilingual and obfuscated input), request checks, headers, encryption, sessions, rate limits, identifier redaction, and a migration test proving an older database upgrades without losing data.

---

## Upgrading an existing installation

CareLens is designed so upgrades never harm existing data:

- Database changes are **additive** migrations; existing tables and rows are not rewritten.
- Plain files uploaded earlier still open; encryption of old files is opt-in and verified.
- A previously saved plain `ai_config.json` is upgraded to an encrypted one automatically.

Before upgrading, copy `backend/instance/` somewhere safe.

---

## Known limitations

- **Database text is not encrypted** (names, medicines, notes, extracted document text). Turn on full-disk encryption such as BitLocker, FileVault or LUKS.
- **When an AI key is set, record text leaves your computer** and goes to the provider you chose, under that provider's terms. Identifiers are removed, but health details in the text are still sent. Without a key, nothing is sent.
- Redaction is pattern-based and cannot catch every personal detail, such as a name inside a sentence.
- The safety guard is keyword-based and may miss unusual phrasing or block rare legitimate ones.
- Designed for a single computer or a trusted home network. If you expose it more widely, use HTTPS, set `FAMILY_COOKIE_SECURE=1`, and configure allowed hosts and origins.
- Voice quality depends on your browser's built-in voices (Chrome or Edge work best).

---

## Roadmap

- Optional encryption of sensitive database fields
- Export and backup of a person's own data
- Two-factor authentication
- More interface languages beyond Hindi and Kannada
- Automated frontend tests

---

## Contributing

Contributions are welcome.

1. Fork the repository and create a branch.
2. Keep database changes **additive** (new migration, never edit an old one).
3. Add or update tests, and run the full suite before opening a pull request.
4. Never commit `backend/instance/`, `.env`, or any real health data.

---

## Reporting a vulnerability

Please **do not** open a public issue for security problems. Report privately to the repository owner (use GitHub's *Report a vulnerability* feature or the contact listed on the profile) with steps to reproduce.

---

## License

Add a `LICENSE` file before publishing (for example MIT or Apache-2.0) and name it here.

---

*CareLens AI organises and explains health information. It is not a medical device and does not replace professional care.*
