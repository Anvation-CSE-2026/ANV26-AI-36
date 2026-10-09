# CareLens AI
Turning health information into smarter family care. React (Vite) + Flask + SQLite.

## Quick start
Windows: double-click `start.bat`. Mac/Linux: `./start.sh`. Then open http://localhost:5173 and choose **Register** to create your family. (A sample family is only created if you ask: `CARELENS_SEED_DEMO=1 ./start.sh`; never store real information in it.)

## AI setup (in the app, no file editing)
Sign in as the primary member -> **Settings -> AI assistant** -> choose a provider (Gemini has a free tier; Anthropic and OpenAI also work), paste the API key, click **Save and test**. It works immediately, no restart. The key is stored encrypted in `backend/instance/ai_config.json`.
(Alternative: put a key in `backend/.env`, see `.env.example`.)
Leave **Model** empty: CareLens tries current Gemini models and picks one that works for your key (Google retires old names such as `gemini-2.0-flash`).
No key = the assistant answers in a clearly labelled offline mode; report explanations and diet guidance need a key.

## Languages
Settings -> Language. Hindi and Kannada translate the whole interface; AI explanations, diet guidance and assistant answers are written in the chosen language (also Tamil, Telugu, Malayalam, Marathi, Bengali, with English menus).

## Floating voice assistant
A round **Ask CareLens** button hovers on every signed-in page (bottom-right; above the tab bar on phones). It opens a chat panel that stays with you as you move between pages; on a document page it automatically asks about *that* document.
- **Languages:** switch English / हिन्दी / ಕನ್ನಡ at the top of the panel. Answers, summaries and spoken text follow it. Saying a language in your request ("... in Hindi") switches it too.
- **Summarise / read a report:** tap *Summarise my latest report* or *Read my report aloud*, or just say it. The AI writes the summary / plain-language explanation in the chosen language and the browser reads it aloud. *Listen* on any answer replays it; *Stop* (or saying "stop") silences it.
- **Voice in:** tap the microphone and speak. Spoken requests are answered aloud automatically; *Read replies aloud* does the same for typed ones.
- **Browser notes:** speaking and listening use the browser's built-in voices. Chrome or Edge work best. If your device has no Kannada/Hindi voice, the panel says so (install it in the system language settings). Without an AI key, "read my report" reads the document exactly as written (not translated) and summaries ask you to connect AI.
- The full **Assistant** page is unchanged and still available from the menu.

## Wellness & Therapies plan
Wellness in the menu. Write your goals, press **Create my plan**. Needs the AI key; without it nothing personalised is produced. Facts are quoted from your own documents (quote checked against the document text, with page numbers for PDFs uploaded after this version; re-upload older PDFs to get pages) and must be confirmed by you. Diet, exercise, sleep, therapies, weekly routine and follow-ups are labelled AI suggestions, are editable and saved, and follow-ups can become reminders. Unconfirmed medicines are ignored. Replies that claim a cure, change medicines or contain an allergen are dropped by the server.

## Sharing
Use **Share** on a document, on Medicines, Health, Emergency, or on a family member's card (Family -> View -> Share). Pick one or more members, choose how long, or share everything at once. Shared items show on Home -> "Shared with you" and Sharing -> "Shared with you". People you share a document with can also ask the assistant about it or get an explanation in their own language. Stop sharing any time.

## Run manually
    cd backend && pip install -r requirements.txt && python seed_demo.py && python app.py
    cd frontend && npm install && npm run dev        # http://localhost:5173

`seed_demo.py` (optional, sample data only) creates a clearly-labelled sample family. Sign in as `meena`, `aditya` or `ravi`, password `sample-pass-1`.
Single process: `npm run build` in `frontend/`, then `python app.py` serves everything on http://127.0.0.1:5000.

## Optional components (the app runs without them and says so)
- **AI assistant, explanations, diet guidance**: set `GEMINI_API_KEY` or `ANTHROPIC_API_KEY` (and optionally `CARELENS_MODEL`) before starting the backend.
  PowerShell: `$env:ANTHROPIC_API_KEY="..."; python app.py`. Keys are never stored in the code or database.
- **Reading images / scanned pages (OCR)**: install the Tesseract OCR program (Windows: UB-Mannheim build) and make sure `tesseract` is on PATH.
  Scanned PDFs additionally need Poppler (`pdftoppm`). Text-based PDFs work without either.

## Privacy and security (details in SECURITY.md)
- **Ownership:** every record has an `owner_id`. Endpoints under `/api/me/*` only touch the signed-in user's rows. Another member can read something only through an active, unexpired, unrevoked grant in `sharing_permissions` (checked on every request in `access.py`, same family only). Family membership alone grants nothing.
- **Encrypted at rest:** uploaded documents and the saved AI key are encrypted (Fernet). Back up `backend/instance/data_key`, because without it encrypted files cannot be opened.
- **Minimal data to the AI:** the assistant only sees the records needed for the question, and phone numbers, emails, Aadhaar/PAN-style IDs and card numbers are stripped from what is sent to the AI provider. Your stored records are not changed.
- **Unsafe requests:** requests that could harm the user or a patient, attack another person's privacy, or hijack the assistant are stopped on the server and never reach the AI provider. The reply says the request has been abandoned (self-harm gets a supportive message with helplines).
- **Sessions:** strict cookies, automatic sign-out after inactivity, **Settings -> Security** shows recent activity and can sign out of all devices.

## Tests
    cd backend && python -m unittest discover -s tests -t .

## Layout
    backend/  app.py · db.py (migrations) · auth.py · access.py (permissions) · routes/ · services/ (extraction, structured, ai, documents)
    frontend/src/  api/ · auth/ · components/ · layouts/ · pages/
