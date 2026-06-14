# Architecture Review & Explanation: Testing Infrastructure

## What This Plan Is For

The testing infrastructure is already fully implemented. This document reviews whether
the architecture is correct and explains every concept involved — written for someone
who has never used these tools before.

---

## Part 1: Is the Architecture Correct?

**Yes.** The structure follows industry-standard conventions exactly. Here is the file
tree with a note on why each piece lives where it does:

```
cns-tools/
│
├── backend/
│   ├── requirements-dev.txt        ← test-only deps, separate from runtime
│   ├── pyproject.toml              ← pytest + ruff config (single source of truth)
│   └── tests/
│       ├── conftest.py             ← shared fixtures available to ALL tests
│       ├── factories.py            ← helper functions to create DB rows in tests
│       ├── docx_utils.py           ← helpers for reading/writing .docx in tests
│       ├── unit/                   ← tests with NO database, NO network
│       │   ├── test_utils_auth.py
│       │   ├── test_field_enrichment.py
│       │   ├── test_renderers.py
│       │   └── test_letter_config.py
│       └── integration/            ← tests that call real API routes + DB
│           ├── test_auth_routes.py
│           ├── test_user_routes.py
│           ├── test_association_routes.py
│           ├── test_template_routes.py
│           └── test_audit_routes.py
│
├── frontend/
│   ├── vitest.config.ts            ← tells Vitest how to run frontend tests
│   └── src/
│       ├── test/
│       │   └── setup.ts            ← runs before every test (clean-up helpers)
│       ├── utils/auth.test.ts      ← co-located with the code it tests
│       ├── hooks/useApi.test.ts
│       ├── context/AuthContext.test.tsx
│       ├── routes/ProtectedRoute.test.tsx
│       ├── pages/settings/ChangePasswordSection.test.tsx
│       └── components/letters/ProxyVoteEditor.test.tsx
│
├── .pre-commit-config.yaml         ← defines local git hooks (one file, both languages)
├── scripts/eslint-staged.sh        ← helper script called by the pre-commit hook
├── .github/workflows/ci.yml        ← GitHub Actions: runs tests on every push/PR
├── TESTING.md                      ← human-readable guide for developers
└── makefile                        ← `make test` runs everything
```

### Why unit/ and integration/ are separate folders

`unit/` tests run in ~2.7 seconds with no Docker, no database, no network — just Python.
`integration/` tests need Postgres and MinIO running. Keeping them in separate folders
lets you run `pytest -m unit` for a fast sanity check without starting any services,
and `pytest -m integration` when you need the full picture. The CI pipeline runs both.

### Why test files live next to their source (frontend)

In the frontend, `auth.test.ts` lives right next to `auth.ts`. This is the React/JS
community convention — it makes it obvious which file each test covers, and you never
lose a test file when you move a component. The backend follows Python's convention of
a top-level `tests/` folder (mirrors how pytest discovers tests by default).

### Why `conftest.py` (not individual test files) holds the database setup

`conftest.py` is pytest's special "shared fixtures" file. Anything defined in it is
automatically available to every test in the same folder and all subfolders — no import
needed. The database engine, the test session, the HTTP client, and the `as_user`
factory are all defined there so every test file can use them without boilerplate.

---

## Part 2: Concept Glossary — Everything Explained From Scratch

---

### What is a "test"?

A test is a small program that calls a piece of your code and checks that the output
matches what you expected. If it doesn't match, the test "fails" — which means you broke
something. Example:

```python
def test_hash_is_not_plaintext():
    hashed = hash_password("CorrectHorse1!")
    assert hashed != "CorrectHorse1!"   # the hash must look different from the input
```

If `hash_password` accidentally returned the password unchanged, this test would catch
it and alert you immediately rather than letting a security bug ship.

---

### What is pytest?

**pytest** is the standard Python test runner. You run `pytest` on the command line,
it finds every file named `test_*.py`, runs every function starting with `test_`, and
prints a pass/fail summary. It also collects "fixtures" (reusable setup/teardown logic)
and handles parametrize (running the same test with many inputs automatically).

The config in [backend/pyproject.toml](backend/pyproject.toml) tells pytest:
- Where to look for tests (`testpaths = ["tests"]`)
- That `.` (the backend folder) is on the Python path so `from app.X import Y` works
- That tests can be tagged as `unit` or `integration` with `@pytest.mark.unit`

---

### What is Vitest?

**Vitest** is the JavaScript equivalent of pytest — it finds files named `*.test.ts`
or `*.test.tsx`, runs functions that call `it(...)` or `test(...)`, and prints pass/fail.
It is built into the Vite ecosystem (the same tool used to build the React app) so it
shares the same TypeScript and JSX configuration. Config lives in
[frontend/vitest.config.ts](frontend/vitest.config.ts).

---

### What is React Testing Library (RTL)?

RTL is a library that simulates a user interacting with a React component. It renders
the component into a fake browser (called jsdom) and gives you tools to find elements
the same way a user would — by text content, by label, by role (button, textbox,
checkbox). Example from [frontend/src/context/AuthContext.test.tsx](frontend/src/context/AuthContext.test.tsx):

```typescript
// Render the AuthProvider like a user would see it.
const { result } = renderHook(() => useAuth(), { wrapper: AuthProvider })
// Wait for the loading spinner to go away.
await waitFor(() => expect(result.current.loading).toBe(false))
// Now assert that no user is logged in (no token in localStorage).
expect(result.current.user).toBeNull()
```

This test checks `AuthContext` without ever opening a real browser.

---

### Unit tests vs. integration tests — what is the difference?

**Unit test:** Tests one small, isolated function with no database and no network.
Fast (milliseconds). Example: does `_ordinal_number(11)` return `"11th"`? See
[backend/tests/unit/test_field_enrichment.py](backend/tests/unit/test_field_enrichment.py).

**Integration test:** Tests that multiple real pieces work together — routes, database,
auth. Slower (hundreds of milliseconds each). Example: does `POST /api/auth/login` with
a wrong password return HTTP 401 AND write an `auth.login_failed` audit row to the DB?
See [backend/tests/integration/test_auth_routes.py](backend/tests/integration/test_auth_routes.py).

The rule of thumb: start with unit tests (fast, catches logic bugs), add integration
tests for the paths that actually matter (auth, money, data integrity).

---

### How does a test talk to the FastAPI backend without a running server?

FastAPI ships with `TestClient`. It wraps your app in a fake HTTP connection — no port,
no real network, no `curl` required. The fixture in
[backend/tests/conftest.py](backend/tests/conftest.py) sets it up:

```python
@pytest.fixture
def client(app_instance, db_session):
    app_instance.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app_instance) as c:
        yield c   # ← tests receive this and call client.post(...), client.get(...)
```

`dependency_overrides` is the key part: FastAPI's `Depends(get_db)` normally returns
a real production database session. The test swaps it out for a controlled test session
so routes write to the test DB instead of the real one.

---

### How does database isolation work? (The savepoint trick)

The problem: if Test A creates a user row and Test B reads it, Test B gets false results.
Each test must see a clean database.

The solution used here (from [conftest.py:80-95](backend/tests/conftest.py)):
1. Before each test, open a database transaction.
2. Create a "savepoint" inside it (like a bookmark).
3. Run the test. Even if the route code calls `db.commit()`, that commit only releases
   the savepoint — it is still inside the outer transaction.
4. After the test, roll back the outer transaction. Every row created during the test
   disappears instantly.

This is what `join_transaction_mode="create_savepoint"` does in SQLAlchemy 2.0.
The result: 91 tests sharing one database, zero row leakage, no `DROP TABLE` between runs.

---

### What is a "fixture"?

A pytest fixture is a reusable piece of setup/teardown code. Instead of copying
database setup into every test, you write it once as a `@pytest.fixture` function and
pytest injects it wherever a test parameter has the same name:

```python
def test_valid_login(client, db_session):
    #              ↑         ↑
    # pytest sees these names, finds matching fixtures in conftest.py,
    # runs the fixture functions, and passes the results in.
```

Fixtures can depend on other fixtures (`client` depends on `db_session`, which depends
on `engine`). Pytest builds the dependency graph automatically.

---

### What is a "factory" (factories.py)?

A factory is a helper function that creates a valid database row for use in tests.
Without factories, every test would need to manually build a `User` object with all
required fields — email, name, hashed password, role, etc. — which is repetitive
and brittle. Instead:

```python
user = factories.create_user(db_session, role=UserRole.admin)
```

The factory provides sensible defaults; tests only specify what matters for that
particular test. Key detail: factories call `db.flush()` (write to memory) not
`db.commit()` (write to disk), so they participate in the per-test rollback.

---

### What is `freezegun`?

Your code calls `date.today()` in `field_enrichment.py` to compute notice deadlines.
In a test, `today` changes every day — making the test output unpredictable.
`freezegun` lets you "freeze" the clock at any date:

```python
with freeze_time("2026-01-01 00:00:00"):
    token = create_token(...)   # minted at midnight
with freeze_time("2026-01-01 09:00:01"):
    decode_token(token)         # 9 hours later — expired
```

Without this, a test for token expiry would be flaky: it works if run at 11 PM but
fails at 11:01 PM.

---

### What is `vi.mock`?

In the frontend tests, components make HTTP calls via `apiClient` (the axios instance).
Tests should not make real HTTP calls — they'd be slow, need a running server, and
have unpredictable results. `vi.mock` replaces the entire module with a fake:

```typescript
vi.mock('../api/client', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}))
```

Now `apiClient.post(...)` is a "mock function" that you control. You tell it what to
return, and later assert it was called with the right arguments.

---

### What is Lint?

**Linting** is automated code style and quality checking. A linter reads your source
files and flags problems — not "is this code correct" (that's tests) but "is this code
well-written":
- Unused imports
- Variables declared but never used
- Inconsistent formatting (tabs vs spaces, trailing commas)
- Dangerous patterns (unused exception variables, shadowed names)

**Ruff** is the Python linter used here. **ESLint** is the JavaScript linter.

A linter gives you feedback instantly (milliseconds) compared to running tests
(seconds or minutes). It is the first line of defense — it catches sloppiness before
tests even run.

Config in [backend/pyproject.toml](backend/pyproject.toml):
```toml
[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]
# E = PEP8 style, F = pyflakes (undefined/unused), I = import sorting,
# UP = upgrade old Python patterns, B = bugbear (common bugs)
```

---

### What is "staged" in git?

Git has three zones:

```
Working directory  →  Staging area (index)  →  Committed history
 (your edits)          (git add)               (git commit)
```

When you edit a file, it is "unstaged" — changed on disk but not queued for the
next commit. When you run `git add myfile.py`, that file becomes "staged" — it is
now in the staging area, waiting to be committed. You can stage some files while
leaving others unstaged.

This matters for the pre-commit hooks: running lint on your *entire* codebase would
be slow (thousands of files) and would flag problems in files you didn't touch. The
hooks are configured to run only on **staged files** — the specific files you changed
for this commit. This keeps the hook fast and non-disruptive.

---

### What are Pre-commit Hooks?

A **git hook** is a script that runs automatically at a specific point in the git
workflow. The `pre-commit` hook runs just before `git commit` finalizes.

The **pre-commit framework** (not to be confused with the git hook itself) is a tool
that manages multiple hooks in a `.pre-commit-config.yaml` file. Instead of writing
raw bash scripts in `.git/hooks/`, you declare what you want in YAML and the framework
handles installation, file filtering, and running things in the right order.

Config in [.pre-commit-config.yaml](.pre-commit-config.yaml):
```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.8.6
    hooks:
      - id: ruff        # lint staged Python files, auto-fix what it can
        args: [--fix]
        files: ^backend/.*\.py$
      - id: ruff-format # auto-format staged Python files
        files: ^backend/.*\.py$

  - repo: local
    hooks:
      - id: frontend-eslint
        language: system
        entry: scripts/eslint-staged.sh   # our custom wrapper script
        files: ^frontend/src/.*\.(ts|tsx)$
```

**What happens when you run `git commit`:**
1. You type `git commit -m "add feature"`
2. Git pauses and runs the pre-commit hook first
3. The hook finds which files you staged (`git add`'d)
4. It runs ruff on staged `.py` files and eslint on staged `.ts/.tsx` files
5. If there are auto-fixable issues, it fixes them and re-stages the files
6. If there are unfixable errors, the commit is **blocked** until you fix them
7. Once everything passes, git proceeds with the commit

This means bad code literally cannot enter the repository if the commit was rejected.
The helper script [scripts/eslint-staged.sh](scripts/eslint-staged.sh) does one
extra thing: it strips the `frontend/` prefix from the file paths before passing
them to ESLint (because the pre-commit framework gives absolute paths but ESLint
expects relative paths from within the `frontend/` directory).

**To activate the hooks** (only needed once per developer machine):
```bash
pip install -r backend/requirements-dev.txt  # installs pre-commit
pre-commit install                           # wires it into .git/hooks/
```

---

### What is CI/CD and what does the CI pipeline do?

**CI (Continuous Integration)** means: every time code is pushed to GitHub, an
automated system runs your tests and blocks merging if they fail. This catches bugs
that a developer forgot to test locally. The config is at
[.github/workflows/ci.yml](.github/workflows/ci.yml).

**What runs on every push/PR:**

Frontend job (no Docker needed):
1. Install Node.js and `npm install`
2. Build the production bundle (catches import errors)
3. Run TypeScript type checking (`tsc`) — catches type mismatches
4. Run all tests with coverage (`vitest run --coverage`)

Backend job (spins up real Postgres + MinIO in Docker):
1. Install Python 3.11 and all dependencies
2. Wait for Postgres to be ready
3. Run Alembic migrations to build the schema
4. Check that the app imports without errors
5. Run ruff lint on the test files
6. Run all pytest tests with coverage

If any step fails, the PR shows a red X and cannot be merged until fixed.

---

### What is Coverage?

Coverage measures "what percentage of your code ran during tests." If you have 100
lines of code and your tests execute 83 of them, you have 83% coverage. Lines that
were never executed are "uncovered" — meaning you have no test for those code paths.

Run with:
```bash
# Backend
pytest --cov=app --cov-report=term-missing

# Frontend
npm run test:coverage
```

Coverage is a useful signal but not a target: 83% coverage on the right code is better
than 100% coverage on trivial getters. The goal is coverage on your most important
business logic (auth, letter generation, password policies).

---

## Part 3: Summary of What Was Built

| Layer | Tool | What it does |
|---|---|---|
| Backend test runner | pytest 8.3.4 | Finds and runs all `test_*.py` files |
| Backend HTTP testing | FastAPI TestClient + httpx | Simulates real API calls without a server |
| Backend DB isolation | SQLAlchemy 2.0 savepoint rollback | Each test gets a clean database |
| Backend date control | freezegun | Freeze `date.today()` for predictable tests |
| Backend storage mocking | monkeypatch on storage_service | Tests letter gen without real S3/MinIO |
| Backend lint + format | ruff | Auto-fixes style + catches bugs |
| Frontend test runner | Vitest | Finds and runs all `*.test.ts(x)` files |
| Frontend UI testing | React Testing Library | Renders components, simulates user interaction |
| Frontend API mocking | vi.mock | Replaces axios with controllable fakes |
| Frontend fake browser | jsdom | Simulates `document`, `window`, `localStorage` |
| Local quality gate | pre-commit | Runs lint automatically before every commit |
| Remote quality gate | GitHub Actions CI | Runs all tests on every push and PR |

**Test counts (verified green):**
- Backend: 91 tests across 10 files
- Frontend: 31 tests across 6 files

---

## Verification Commands

```bash
# Backend (needs Docker services)
make dev                     # start Postgres + MinIO
cd backend
venv/bin/python -m pytest -m unit          # fast, no services needed
venv/bin/python -m pytest -m integration   # full route tests
venv/bin/python -m pytest --cov=app        # with coverage report

# Frontend (no services needed)
cd frontend
npm test                     # run once
npm run test:coverage        # with coverage report
npm run typecheck            # TypeScript type check

# Pre-commit (run once to install, then automatic)
pre-commit install
pre-commit run --all-files   # dry run against all files

# Everything at once
make test
```
