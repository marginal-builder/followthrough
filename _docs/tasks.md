# Weekly Feedback Tool – Task Backlog

Each task is sized for a single session and written to be self-contained: the assignee only needs `plan.md` (product scope) and `stack.md` (technology choices). Every task ships with passing tests; the project uses pytest throughout.

---

## 1. Project scaffold with passing test
Goal: An empty FastAPI project in Docker Compose with a green test suite.
Description: Set up the repository layout (app package, tests, `requirements.txt`), pin the versions from stack.md (Python 3.14, FastAPI 0.141.x, SQLModel 0.0.42, uvicorn, arq), and create a `docker-compose.yml` with four services: app, arq worker, Valkey (9.x), Postgres (18). Add a trivial `/health` endpoint returning JSON status and one pytest test asserting it responds 200 — running `docker compose up` and then the test must pass. This task defines the project conventions everyone else follows.

## 2. Data model and migrations
Goal: All database tables exist and are created via Alembic.
Description: Define SQLModel entities for User, WeeklyBoard, FeedbackItem, Action, Decision, and Extraction, and wire up Alembic with an initial migration that creates them. User: id, name (unique), is_admin (bool). WeeklyBoard: id, week_start (date, unique), is_archived (bool). FeedbackItem: id, board_id (FK), column ("start"/"stop"/"continue"), body, author_id (nullable FK — null means anonymous), created_at. Action: id, board_id (FK), body, owner_id (nullable FK), status ("todo"/"in_progress"/"done"), due_date (nullable). Decision: id, board_id (FK), body. Extraction: id, board_id (FK), kind ("action"/"decision"), payload (JSON), status ("pending"/"approved"/"discarded"), created_at. Add model-level pytest tests (create, constraints) against the Compose Postgres.

## 3. Settings and configuration
Goal: All configuration comes from environment variables with a documented `.env.example`.
Description: Add a pydantic-settings module exposing DATABASE_URL, VALKEY_URL, TEAM_PASSCODE, SESSION_SECRET, and GROQ_API_KEY, loaded from the environment or a `.env` file. Provide `.env.example` with sensible local defaults, and wire the Compose services to pass these through. Include a test that settings load from a temp `.env` and fail loudly when a required key is missing.

## 4. Team passcode login
Goal: A user can log in by entering the team passcode and picking their name.
Description: Build a simple login page (Jinja2 + Tailwind) that shows the seeded list of user names as a select plus a team passcode field; on success, set a signed session cookie (itsdangerous or similar) and redirect to the boards page. Add an auth dependency that guards all other routes and redirects to the login page when the cookie is missing or invalid, and a logout route. Seed two or three users via a migration or startup seed script, and test the full login → access → logout flow.

## 5. Base layout and styling
Goal: A shared HTML layout that every page extends.
Description: Create a Jinja2 base template with Tailwind 4 (via CDN or build step — builder's choice, documented in the README), a simple header (app name, week navigation placeholder, logged-in name, logout link), and content blocks. Include HTMX 4 and Alpine.js 3 on the page and a smoke test rendering a page that extends the layout. No product features here — just the shell other tasks build pages on.

## 6. Weekly board creation and listing
Goal: Users see the list of boards and can create "Week of [date]" boards.
Description: A boards index page listing WeeklyBoards (newest first, showing week_start and archived status) with a "Create this week's board" button that creates a board for the Monday of the current week (or links to it if it already exists). Only manual creation — no scheduling. Test creation, duplicate-week prevention, and the redirect to the board page.

## 7. Board page with feedback columns
Goal: A board page shows Start / Stop / Continue columns.
Description: Render a board's FeedbackItems grouped into three sections (Start / Stop / Continue), each item showing its body, author display name, or "Anonymous" when author_id is null, and creation time. Include a per-column add form (body text + "Submit anonymously" checkbox) that creates a FeedbackItem for the signed-in user unless anonymous is checked. Use HTMX form submission so the new item appears without a full page reload. Test item creation in each column, attribution, and the anonymous path.

## 8. Feedback item editing and deletion
Goal: Items can be corrected after posting.
Description: On the board page, let the author of an item (or any admin user) edit its body or delete it, via HTMX click-to-edit with a cancel option. Non-authors see no edit controls. Keep the plan's light-permission spirit: everyone can add and view, only authors/admins modify. Test edit, delete, and that a non-author gets a 403.

## 9. Actions list with owner and status
Goal: Each board has a trackable actions list.
Description: Add an Actions section to the board page listing that week's Actions with owner display name, status badge (To Do / In Progress / Done), and optional due date. Provide a small HTMX form to add an action (body, owner select from users, optional due date) and a status dropdown that updates the action in place. Test creation, status transitions between all three states, and rendering of empty due dates.

## 10. Decisions list
Goal: Each board has a simple list of decisions.
Description: Add a Decisions section to the board page showing that week's Decision rows in order, with an HTMX form to add one (body only — no owner or status). Decisions are append-and-edit-simple: any signed-in user can add; authors/admins can edit or delete like feedback items. Test add, edit, and list ordering.

## 11. Recording upload endpoint
Goal: A user can upload an audio or video file for a board.
Description: Add an upload form on the board page that POSTs a multipart file to an endpoint, which writes it to a temp file and enqueues an arq job with the file path and board id, then shows a "processing" indicator (HTMX poll or Alpine state). Reject empty uploads and files above a documented size limit with a clear error. Test the endpoint with a small dummy file: job enqueued, temp file exists, response shows the pending state.

## 12. Transcription worker job
Goal: An uploaded recording becomes a transcript.
Description: In the arq worker, implement the transcription job: read the temp file, call Groq's API with the `whisper-large-v3-turbo` model to transcribe it, store the transcript text on a new Transcript row linked to the board, then delete the temp file — the recording must never outlive the job, including on failure (wrap in try/finally). Handle Groq API errors with retries (arq's retry mechanism) and a terminal failure state surfaced to the board page. Test with a mocked Groq client: happy path stores the transcript and deletes the file; failure path retries and still deletes the file.

## 13. Transcript paste path
Goal: A user can paste a transcript instead of uploading a file.
Description: Next to the upload form, add a "paste transcript" textarea that stores the text directly as a Transcript row and marks it as ready for extraction, bypassing transcription entirely. This is also the manual fallback when automatic transcription fails. Test that pasted text is stored and triggers the same downstream state as a finished transcription.

## 14. Action and decision extraction job
Goal: A finished transcript yields pending action/decision suggestions.
Description: Implement the second arq job: take a board's ready transcript and call Groq's LLM with a structured-output prompt constrained by Pydantic models (a list of actions with suggested body/owner-hint/due-date, and a list of decisions), writing each result as an Extraction row in "pending" status. Validate the LLM response against the models; on validation failure retry once, then mark the extraction run as failed rather than writing garbage. Extract only from the latest transcript if several exist. Test with a mocked LLM returning both valid and invalid JSON.

## 15. Extraction review and approval
Goal: Pending extractions become real actions and decisions after human review.
Description: Add an "AI suggestions" panel on the board page listing pending Extraction rows with their parsed payload, letting a signed-in user edit the fields inline, then Approve (creates/updates a real Action or Decision and marks the extraction approved) or Discard it. Nothing created by the AI is ever live without approval, per plan.md. Test approve-creates-action, approve-creates-decision, discard, and that edited fields are what lands on the board.

## 16. Board history view
Goal: Past weeks remain browsable.
Description: Make archived boards read-only (no new items, actions, or decisions; the UI hides forms and shows an "archived" banner) while keeping everything viewable, and ensure the boards index links to them. A board is marked archived when the next week's board is created — implement that transition in the board-creation flow from task 6. Test that an archived board rejects writes at the endpoint level and that creating a new board archives the previous one.

## 17. README and developer quickstart
Goal: A newcomer can run the project locally in minutes.
Description: Write a README covering: what the tool is (one paragraph from plan.md), prerequisites, `docker compose up` instructions, `.env` setup from `.env.example` (including where to get a Groq API key), how to run the tests, and how to seed the team users. Verify the instructions by following them in a clean checkout — the definition of done is a colleague completing onboarding using only this document.
