## Project Context

FastAPI project with a generative AI chat agent that can find related animals for a user's query

## Tech Stack

- **Language:** Python 3.12+
- **Package Manager:** uv
- **Framework:** FastAPI / Pydantic v2
- **Database / ORM:** SQLAlchemy with PostgreSQL
- **Logging:** logging module with logfire
- **Testing:** Pytest

### Development & Environments

- Run dev server: `uv run uvicorn animal_finder.main:app --reload` (from `backend/`; `uv sync` installs the `animal_finder` package into the venv)

### Github Commits

Remove the Co-Authored-By line on generated commits.
