# React + Vite

## Page layout

The page and sidebar show **Analyze files**, **Reports**, then **Overview**, with
Analyze files selected initially. The upload area has no extra visible assessment
heading. Reports use a single "Application results" heading, and the dashboard
appears afterward without a separate visible overview heading. Accessible page,
upload-section, and overview headings remain available to screen readers.

## Document-analysis latency

Document embeddings use batches of up to 32 chunks instead of one network call
per chunk. Each chunk is a separate Gemini `Content`, so Gemini Embedding 2 does
not aggregate the entire batch into one vector. Chunk size, prompts, model
selection, analysis results, and the awaited indexing flow are unchanged.

A complete matching Chroma index is reused when the chunk content, embedding
model, and embedding-input format are unchanged. Metadata-only changes update
metadata without generating embeddings. Legacy, incomplete, or changed indexes
are rebuilt on the next upload. Gemini document analysis still runs for every
upload; previously generated credit-risk assessments are not cached.

All new vectors are validated before the index is updated. Existing vectors are
not deleted when embedding generation fails. Stale chunks are removed only after
the replacement vectors have been upserted. Indexing errors remain explicitly
logged; the existing best-effort analysis response and chat fallback are retained.
Retrieval matches the current document hash when available, so retained vectors
from a previous document version do not become evidence for the replacement.

Blocking parsing, Gemini calls/retries, and Chroma operations run in worker
threads rather than blocking FastAPI's event loop. This improves responsiveness
under concurrent use; it does not make an individual Gemini generation faster.
Bulk documents remain sequential to preserve existing update ordering.

The backend console logs `analysis_timing` (parse, Gemini, database, indexing,
total milliseconds) and `index_timing` (chunk count, embedding batch count,
cache hit, and embedding/indexing time). These logs contain no document content,
credentials, or filenames. Compare timings on representative uploads to measure
actual latency: provider delays and retries can still dominate total time.
Chroma remains cloud-hosted; no data migration or background indexing was added.

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

## Okta sign-in

The sign-in screen uses a frosted-glass card, a subtle grid, and brighter mint,
blue, and gold aurora ribbons against a deep teal background. The ribbons sweep
into place on page entry and settle within 4.5 seconds; there is no continuous
decorative animation or pause/play button. Reduced-motion preferences disable
animations and hover movement. Only transforms and opacity are animated;
no JavaScript animation loop or animation library is used. The screen supports narrow viewports,
visible keyboard focus, and forced-colors mode. The wider, compact sign-in card
reduces text wrapping and vertical scrolling on laptop screens, while retaining
natural scrolling for smaller viewports, zoom, and long error messages.
Browsers without backdrop-filter
support receive an opaque card. Styling uses CSS and existing icons only, with no
additional animation libraries or image downloads. The Okta authentication flow
and configuration/error messages are unchanged.

Sign-in uses Okta's hosted page with OIDC Authorization Code + PKCE. The app
never collects a password or uses a client secret. All five backend APIs require
a signed access token; the backend checks RS256, issuer, audience, expiration,
subject, SPA client ID, and the configured API scope. ID tokens cannot authorize
API calls. Missing backend settings fail startup rather than enabling anonymous
access. API documentation endpoints are disabled.

**Access model:** users assigned to this Okta app and granted the API scope share
the existing application records, analysis, reports, and assistant. This does not
add record ownership, group-specific roles, or tenant isolation. Configure Okta
assignments and authorization-server access policies accordingly.

### Configure Okta

1. In Okta Admin, create an **OIDC / Single-Page Application** with the
   **Authorization Code** and **Refresh Token** grants. Do not select a confidential web application or
   add a client secret to frontend configuration.
2. Register `http://localhost:5173/login/callback` as a sign-in redirect URI and
   `http://localhost:5173` as a sign-out redirect URI. Add the frontend origin to
   Okta Trusted Origins for CORS/redirects where required. Use exactly the same
   hostname when browsing; `127.0.0.1` and `localhost` are different origins.
3. Use a **custom authorization server**, such as
   `https://your-org.okta.com/oauth2/default`, with audience `api://default`.
   The bare Okta organization issuer is not suitable for this API. A production
   subscription may require Okta API Access Management.
4. Create an API scope `risk.read` and an access policy/rule granting it to this
   SPA and the intended assigned users. Here this scope grants the entire shared
   workspace, including uploads and AI requests, not only read operations.
5. Assign permitted users/groups to the app. MFA and account recovery remain
   managed by Okta policy.
6. In the app's **General > Refresh Token** settings, select **Rotate token after
   every use**. In the authorization server's access-policy rule, allow
   **Authorization Code** and **Refresh Token**, and allow these requested scopes:
   `openid`, `profile`, `email`, `offline_access`, `risk.read`.
   `offline_access` is a standard scope; do not create a custom scope with that name.
7. Set lifetimes according to organization policy. A starting point is a
   **15-minute access token**, **8-hour maximum refresh-token lifetime**, and
   **1-hour refresh-token idle expiry**. These are Okta settings, not app-enforced
   durations. Save the settings, then sign out and sign in again to obtain a
   refresh token; existing sessions without one require a fresh sign-in.

### Configure and run the application

- Copy [the frontend example](.env.example) to `frontend/.env`. Set
  `VITE_OKTA_ISSUER`, `VITE_OKTA_CLIENT_ID`, and `VITE_OKTA_SCOPE`; set `VITE_API_URL`
  if the backend differs from `http://localhost:8000`.
- Merge [the backend example](../backend/.env.example) into your existing
  `backend/.env` without overwriting MongoDB or AI-provider settings. Set
  `OKTA_ISSUER`, `OKTA_CLIENT_ID`, `OKTA_AUDIENCE`, `OKTA_REQUIRED_SCOPE`, and
  `FRONTEND_URL`. Both sides must use the same issuer, SPA client ID, and scope.
- Run `npm install` in the frontend and
  `.\venv\Scripts\python.exe -m pip install -r requirements.txt` in the backend.
  If the virtual environment does not exist, create it first with `python -m venv venv`.
- Start MongoDB, then
  `.\venv\Scripts\python.exe -m uvicorn main:app --reload --host 127.0.0.1 --port 8000` in the
  backend and `npm run dev -- --host localhost` in the frontend.
- On Windows, use the explicit virtual-environment interpreter above rather than
  bare `uvicorn`, which may resolve to a global installation without the project's
  dependencies. If you see `ModuleNotFoundError: No module named 'jwt'`, stop the
  failed reloader with Ctrl+C and restart with the command above. The package that
  supplies `jwt` is `PyJWT[crypto]`, already listed in the backend requirements.
- Open `http://localhost:5173`. Environment changes require restarting the backend
  and restarting/rebuilding the frontend. Never commit actual environment secrets.

Tokens are stored in tab-scoped session storage with no local-storage/cookie
fallback. Refresh retains the tab's login. The app requests `offline_access` and
uses the SDK to renew expiring access tokens before API calls and during session
checks. Concurrent renewals share the SDK's in-flight request, and rotated tokens
are saved by the SDK. There is no continuous background renewal in idle tabs, so
idle expiry remains meaningful and unnecessary network requests are avoided.
Expired/revoked refresh tokens, failed renewal, or an API 401 return to sign-in.
API requests are not automatically replayed, avoiding duplicate uploads or AI calls.
Refresh tokens are sent only to Okta, never to the backend API.
Sign out clears local tokens, requests access/refresh-token revocation, and
requests Okta session logout; remote logout failure
is shown explicitly. A 403 indicates that the user lacks the configured scope;
a 503 can indicate that Okta signing keys are temporarily unreachable.
JWT verification is local: previously issued tokens can remain valid until
expiry after assignment changes or revocation. Use short access-token lifetimes;
immediate revocation enforcement would require an additional introspection policy.

Report downloads use authorized requests, never tokens in query strings.
API responses include no-store, nosniff, anti-framing, and no-referrer headers.
In production serve both apps over HTTPS, restrict CORS to deployed origins,
and configure the frontend host/reverse proxy with HSTS, CSP (including the
specific Okta/API connections), frame-ancestors, and other required security
headers. Serve the SPA entry point for `/login/callback` and `/dashboard`.

### Authentication checks

1. Without signing in, `/`, `/dashboard`, `/login`, and `/signup` show sign-in,
   not workspace data. Direct calls to each `/api/*` endpoint return 401.
2. Sign in with an assigned Okta user. Confirm dashboard, uploads, chat, and PDF
   downloads work; refresh the page and confirm the callback is not repeated.
3. Sign out and confirm protected content disappears. A different user must not
   see the previous user's browser chat history. Legacy anonymous history is
   left untouched but is not loaded into any signed-in account.
4. Let the access token expire, then load dashboard/chat/download a report.
   Verify Okta receives a refresh-token grant and the API receives the new access
   token without a login redirect. Check idle/max refresh expiry, revoked refresh
   tokens, and a failed refresh request: each must return to sign-in without
   replaying an upload or chat request. Also check denied/cancelled login, missing scope,
   and an incorrectly configured issuer/audience. Tokens must never be logged.
5. Frontend checks: `npm run lint` and `npm run build`. Automated test files
   are not included; use the manual regression checks above when changing authentication.

Live redirect, rotation, expiry-policy, MFA, and remote logout checks require a configured Okta tenant;
build checks do not certify its policies or credentials.

Browser speech recognition requires HTTPS or localhost, microphone permission,
and a compatible browser with English recognition and playback support.
Missing English voices, permission failures, and speech-service errors are shown in the chat;
typing and written replies remain available. Audio may be processed remotely by
the browser's speech provider. This application does not record or store audio;
only reviewed message text is sent to the existing chat API and saved in history.
Changing/closing chats stops capture and playback, and late replies from earlier
chat contexts are not read aloud.

Conversations are stored per Okta issuer and user in this browser profile's local storage, including after
refreshing or reopening the browser. They are not synchronized across devices or
saved to the application database. Anyone using the same browser profile can
inspect them through browser tools; account-scoped keys are not encryption.
Avoid saving sensitive information on a shared device. Clearing this
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
