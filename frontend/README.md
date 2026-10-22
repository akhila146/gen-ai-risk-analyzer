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

## Authentication

The workspace is protected by server-side MongoDB sessions stored in an
HttpOnly cookie. Create an account at `/signup` and sign in at `/login`.
Passwords are hashed with scrypt, and all workspace API endpoints require an
authenticated session.

Copy `backend/.env.example` to `backend/.env` and configure MongoDB.
For local HTTP development, `AUTH_COOKIE_SECURE=false`; set it to `true` for
HTTPS deployments. Copy `frontend/.env.example` to `frontend/.env` and set
`VITE_API_URL` to the backend origin when it differs from `http://localhost:8000`.

Application analysis data remains shared among authenticated accounts, matching
the existing shared MongoDB workspace model.

### Authentication test steps

1. Start MongoDB, configure the backend environment, then start the backend and frontend as usual.
2. Visit `/signup` and create an account with a valid name, email, and matching
   passwords of at least 12 characters. Verify the app returns to `/login` and
   reusing the email is rejected.
3. Sign in, open the profile menu in the sidebar, and choose **Log out**. Sign
   in again and refresh the page to verify the session persists.
4. Open `/` while logged out and call a protected `/api/*` endpoint without the
   session cookie; the browser redirects to login and the API returns 401.

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
