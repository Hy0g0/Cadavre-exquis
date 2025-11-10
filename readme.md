## Collective Storyteller

### Overview
- One-page web app where visitors read the latest sentence in a collaborative story and add the next line.
- Backend exposes simple JSON API and persists contributions in a local SQLite database.
- Each visitor (tracked via browser cookie) can contribute once per day to keep the flow balanced.
- Use the special tester name `Z3US` (without anonymity) to bypass the daily limit during demos.

### Project Structure
- `app.py`: Python HTTP server with REST endpoints.
- `static/`: Frontend assets served as the public site.
- `data/`: SQLite database file (`sentences.sqlite3`) created automatically on first run.

### Prerequisites
- Python `>= 3.10` (tested with Python 3.14)

### Setup & Run
- Install dependencies (standard library only; no external packages required).
- Start the server:
  ```bash
  cd /Users/hugo.vincent/github/cada-exquis
  python3 app.py
  ```
- Open the site: `http://localhost:8000`

### API
- `GET /api/sentence`: returns the latest stored sentence.
- `POST /api/sentence`: accepts JSON payload `{ sentence, name, anonymous }`, rate-limits to one submission per visitor per day, except when the name is exactly `Z3US`.

### Development Tips
- Edit files inside `static/` for UI changes.
- Delete `data/sentences.sqlite3` to reset the story.
