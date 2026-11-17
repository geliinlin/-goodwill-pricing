# Goodwill Pricing Management System — Modules 1 & 2

Aiven deployment edition: start with [DEPLOY_AIVEN_CN.md](DEPLOY_AIVEN_CN.md). Includes Dockerfile, .dockerignore and MYSQL_* environment variable support with verified TLS. Add your Aiven CA certificate as `ca.pem` before deploying. This package has not been deployed to Aiven.

The original Streamlit/MySQL login module plus administrator pricing guideline management, built against the existing 11-table G3 schema.

中文安装步骤、逐文件更新清单和验证步骤：[START_HERE_CN.md](START_HERE_CN.md).
Original login/setup instructions: [README_MODULE1.md](README_MODULE1.md).

## Included

- Username/bcrypt login, role-based pages, employee branch display and logout.
- Administrator guideline list, text search, Active/Inactive filters and summary counts.
- Dropdowns loaded from CATEGORY, BRAND, ITEM_CONDITION and ITEM_TYPE.
- Create, edit, deactivate and reactivate guidelines.
- Decimal price validation; one active guideline per four-attribute combination through app writes.
- Fresh database authorization on every service call, parameterized values, transactional writes and stale-edit detection.
- Automatic integer ID allocation under a database-scoped advisory lock.
- Price/attribute edits retire the old guideline and insert a replacement atomically, preserving values referenced by existing pricing decisions.

## Upgrade an existing Module 1 installation

Replace `app.py`; add `guidelines.py`, `guideline_page.py`, `scripts/check_module2.py` and the two new test files at matching paths. Optionally copy `.streamlit/config.toml`. Keep your configured `.streamlit/secrets.toml`, `auth.py` and `database.py`.

From your existing project directory and Python environment:

```bash
python -m pip install -r requirements.txt
python -m scripts.check_module2
python -m streamlit run app.py
```

No migration or data reset is required. Do not rerun the destructive DROP/CREATE portion of the original SQL script.

## Fresh local folder

Requires Python 3.11+ and the existing MySQL G3 database. From this folder:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Copy the working `.streamlit/secrets.toml` from your original project, or copy the included example and configure it locally. Then run the check and Streamlit commands above. Use an existing app administrator username to log in. Initial account provisioning remains available as described in README_MODULE1.md.

MySQL account privileges: SELECT on auth and lookup tables and PRICING_GUIDELINE; INSERT and UPDATE on PRICING_GUIDELINE. All relevant tables must use InnoDB. No DROP, ALTER, DELETE or CREATE privilege is required for this module.

## Validation

```bash
python -m unittest discover -s tests -v
```

35 local tests passed on Python 3.12, Streamlit 1.67.0, mysql-connector-python 9.7.0 and bcrypt 4.3.0, including 7 cloud-configuration tests. These exercise auth, service validation/transaction calls with a mocked MySQL driver, and real Streamlit widget interactions via AppTest with mocked services. No live MySQL server was used, and SQL execution, actual transactions and multi-session contention still need verification on a test MySQL database. Docker build and Aiven deployment have not been run.

`scripts.check_module2` is read-only: it verifies expected column names, InnoDB engines and existing duplicate active combinations. It does not verify write privileges.

## Data behavior and limits

- Status-only changes keep the ID. Price/attribute edits create a new ID and mark the old row inactive, even if it has no pricing decisions yet.
- Guideline_Id is allocated as MAX+1 while every application writer holds the same database-scoped GET_LOCK. Direct SQL or another application that does not acquire that lock can bypass conflict checks. This is not a substitute for a database unique constraint or a production ID design.
- The current schema does not provide a full audit log or explicit version lineage. Price/attribute values are retained, but status changes do not track individual actors.
- A stale record is checked against all displayed stored fields. No version-number column was added.
- Amounts are displayed in USD; timestamps use the MySQL server session time zone.
- Catalog tables must already contain data. Catalog, user/branch management, item entry, employee price matching, decisions, barcodes and reports are not implemented in this release.
- Streamlit may emit `use_container_width` deprecation notices on recent versions; the current syntax retains compatibility with the Module 1 dependency range.

Reference documentation used: [MySQL named locks](https://dev.mysql.com/doc/refman/8.0/en/locking-functions.html), [Streamlit forms](https://docs.streamlit.io/develop/concepts/architecture/forms), [Streamlit app testing](https://docs.streamlit.io/develop/concepts/app-testing/get-started).
