# Goodwill Pricing Management System — Module 1

## What is implemented

- Parameterized queries against the original 11-table G3 MySQL schema (no migration required)
- Login using `USER_ACCOUNT.User_Username` and bcrypt-verified `User_Password_Hash`
- Rejects inactive accounts and users missing the matching `ADMINISTRATOR` or `STORE_STAFF` record
- Admin and employee home pages with role checks
- Employee branch shown from `STORE_STAFF` / `BRANCH`
- Logout and automatic re-check of account status and role on every Streamlit rerun
- Secure, command-line-only creation of the first administrator/employee account

## Prerequisites

Python 3.11+; MySQL server containing the G3 schema (database `Fall2026BIS698TueG3s`).

## Setup (macOS Terminal)

```bash
cd goodwill_module1
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

Edit `.streamlit/secrets.toml` with your **real** MySQL host, port, username and password. Do not share the file or commit it to Git. The user must have SELECT access to the four auth tables and INSERT access when provisioning users.

> The existing SQL file creates tables but does not insert the first user. Run its `CREATE TABLE` statements in MySQL Workbench **once** before provisioning an account. Do not rerun the `DROP TABLE` section on a database containing data.

## Verify connection

```bash
python -m scripts.check_connection
```

This checks that the MySQL database and four Module 1 tables are accessible. If counts are zero, create an initial user next.

## Create first administrator (once)

```bash
python -m scripts.create_user \
  --user-id 1 \
  --username admin1 \
  --first-name Demo \
  --last-name Admin \
  --email admin1@example.com \
  --role Administrator
```

The script securely prompts twice for a password; it stores only a salted bcrypt hash, and inserts `USER_ACCOUNT` and `ADMINISTRATOR` together in one transaction. Replace the sample email/user names with real values.

## Optional: create an employee account for testing

An employee needs an existing `BRANCH` row first. Add one in Workbench with real information, then:

```bash
python -m scripts.create_user \
  --user-id 2 \
  --username employee1 \
  --first-name Demo \
  --last-name Employee \
  --email employee1@example.com \
  --role Employee \
  --branch-id 1
```

Use an existing `Branch_Id`, not necessarily `1`.

## Run the app

```bash
streamlit run app.py
```

Streamlit opens a local browser page, generally `http://localhost:8501`. After login, administrators see the administrator dashboard; employees see the employee dashboard and their assigned branch.

## Run local unit tests (no live database required)

```bash
python -m unittest discover -s tests -v
```

## File structure

```
goodwill_module1/
├── app.py                    # Streamlit login and role-based landing pages
├── auth.py                   # Auth queries and server-side authorization helper
├── database.py               # MySQL connection
├── scripts/
│   ├── create_user.py        # One-time secure account provisioning
│   └── check_connection.py   # Read-only connection check
├── .streamlit/
│   └── secrets.toml.example  # Template (no real passwords)
├── tests/
│   └── test_auth.py          # Tests for role and password validation
├── requirements.txt
└── .gitignore
```

## Security notes and current limits

1. **No plaintext login passwords:** Existing accounts will only log in if their `User_Password_Hash` is a valid bcrypt hash. Do not insert plaintext passwords into the database.
2. **Server-side authorization:** Every future administrator-only backend action must call `require_role(user, {"Administrator"})`, even if the page is hidden from employees. A hidden button alone is not authorization.
3. **ID handling:** The existing schema has no `AUTO_INCREMENT`. `--user-id` must be unique, and later management features must handle IDs consistently.
4. **Account changes:** The app re-checks the account record and role every Streamlit rerun; this is appropriate for the demo, but production deployment should also use HTTPS, centralized rate limiting, audit logs, stricter DB privilege separation, and session timeouts.
5. **No live server test:** Local code syntax can be validated without database credentials, but actual connection/authentication requires your MySQL host and test account.

## Quick troubleshooting

- `Missing MySQL settings`: `.streamlit/secrets.toml` is missing or incomplete.
- `Access denied`: Check MySQL username/password and permissions; do not confuse the MySQL account with an app user in `USER_ACCOUNT`.
- `Unknown database`: Check the database name (`Fall2026BIS698TueG3s`) and whether the G3 script ran on that server.
- `Invalid username or password...`: Check bcrypt hash, account active flag, `User_Type` and matching role table row.
- Employee cannot be provisioned: Add a real row to `BRANCH` first.
