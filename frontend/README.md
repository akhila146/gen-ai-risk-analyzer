# React + Vite

## Page layout

The page and sidebar show **Analyze files**, **Reports**, then **Overview**, with
Analyze files selected initially. The upload area has no extra visible assessment
heading. Reports use a single "Application results" heading, and the dashboard
appears afterward without a separate visible overview heading. Accessible page,
upload-section, and overview headings remain available to screen readers.

## Read-only assistant

The assistant supports general conversation without selecting an application or
uploading a file. General is the only UI mode: it combines portfolio questions
about up to the 50 most recent records with document-grounded answers for an
optionally selected application. Portfolio information stays available when an
application is selected, and changing the selection keeps the conversation. Empty or
missing records do not block general chat; unavailable facts must be identified
as unavailable.

Chat uses fixed read queries only and provides no action tools to the model.
Requests to change application data must be refused. The shared system policy
also covers safe responses, uncertainty, and protection of internal information.
These model instructions are not a guarantee of factual accuracy or moderation.

**New chat** starts an empty conversation and clears its application selection
without deleting previous conversations. **Recent chats** lists conversations
newest-first by last message sent, using the first question as the title.
Reopening one restores its messages, optional application selection, and the last
six successful turns used for follow-up context. Replies still go to the original
conversation if another chat is opened while a response is pending.

The delete icon beside a recent chat removes that conversation from browser
history. Deleting the open chat selects the most recent remaining conversation,
or starts a fresh one if none remain. Pending browser requests for the deleted
chat are cancelled so late replies do not restore it. Application records are
not affected.

### English voice chat

Use the microphone immediately to the left of Send to dictate an English message.
Allow microphone access, then stop recording and review/edit the transcript before
sending. Speech is never submitted automatically. Voice recognition uses English
(India), and voice-message replies use an installed English browser/system voice.
**Stop audio** appears only during playback and stops it. There is no language
selector, manual read-aloud button, or default speech helper text. If playback is
blocked or unavailable, an error is shown and the written reply remains available.

Both typed and voice questions request English replies. Multilingual response
selection and language hints are not supported. The existing factual and
read-only policies remain unchanged.

## Local demo access

The workspace opens directly without login, signup, session checks, or logout.
Legacy `/login` and `/signup` browser URLs also render the workspace. All workspace
APIs are accessible without credentials; the former `/api/auth/*` routes are removed.
Existing application records and browser chat history are unchanged. Existing
account/session database collections are not deleted, but are no longer used.

**Local/demo use only:** anyone who can reach the backend can read application
data, upload files, download reports, and invoke AI services. Bind both servers
to localhost; do not expose this version to a shared network or production
without an approved access-control layer.

Configure `MONGODB_URL` and `DATABASE_NAME` in `backend/.env`.
Copy `frontend/.env.example` to `frontend/.env` and set `VITE_API_URL` when the
backend origin differs from `http://localhost:8000`. Authentication cookie
configuration is no longer used.

### Direct-access test steps

1. Start MongoDB and run the backend with `uvicorn main:app --host 127.0.0.1 --port 8000`
   from the backend directory. Run `npm run dev -- --host 127.0.0.1` from the frontend.
2. Open `/` in a fresh browser session. Verify Analyze files, Reports, and Overview
   appear immediately, without an account screen or a logout control.
3. Refresh `/dashboard`, `/`, `/login`, and `/signup`; each should show the same
   workspace with `/dashboard` as the URL path, without adding a browser history
   entry. The obsolete `#main-content` fragment is removed; other section links
   and query parameters are preserved. Hosts must serve the frontend entry page
   for `/dashboard` (Vite's development and preview servers support this).
4. Verify `/api/dashboard` works without a session cookie. Upload a test file,
   download its report, and send a chat message to confirm existing workflows.
5. Backend regression checks: from the backend directory, run
   `python -m unittest discover -s tests -p "test_direct_access.py"`.

Browser speech recognition requires HTTPS or localhost, microphone permission,
and a compatible browser with English recognition and playback support.
Missing English voices, permission failures, and speech-service errors are shown in the chat;
typing and written replies remain available. Audio may be processed remotely by
the browser's speech provider. This application does not record or store audio;
only reviewed message text is sent to the existing chat API and saved in history.
Changing/closing chats stops capture and playback, and late replies from earlier
chat contexts are not read aloud.

Conversations are stored in this browser profile's local storage, including after
refreshing or reopening the browser. They are not synchronized across devices or
saved to the application database. Anyone using the same browser profile can
access them; avoid saving sensitive information on a shared device. Clearing this
site's browser data removes the saved history. Private browsing or browser storage
policies may limit persistence. Storage errors are displayed rather than silently
discarding saved chats, and no automatic history pruning is performed.

Legacy API scopes remain supported, but the UI always sends `general`. Chat does
not save history or retrieval metrics to the database. Existing upload/analysis
actions remain unchanged.

Chat errors are reported without exposing provider or database error details.
Frontend checks are available through `npm run lint` and `npm run build`.
Microphone permission, recognition quality, voice availability, and playback
require a manual browser check on the target device.

This template provides a minimal setup to get React working in Vite with HMR and some Oxlint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Oxc](https://oxc.rs)
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/)

## React Compiler

The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## Expanding the Oxlint configuration

If you are developing a production application, we recommend using TypeScript with type-aware lint rules enabled. Check out the [TS template](https://github.com/vitejs/vite/tree/main/packages/create-vite/template-react-ts) for information on how to integrate TypeScript and Oxlint's TypeScript related rules in your project.
