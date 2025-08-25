# OpenUpgrade API

This project provides a complete toolset to download, parse, and serve data about Odoo version changes from the [OCA/OpenUpgrade](https://github.com/OCA/OpenUpgrade) GitHub repository. It creates version-specific SQLite databases and exposes the data through a flexible REST API.

## Features

  - **Automated Data Sync:** Fetches upgrade scripts directly from multiple branches (16.0, 17.0, 18.0, etc.) of the official OCA repository.
  - **Version-Specific Parsing:** Processes data into separate, self-contained databases for each major Odoo version (e.g., `upgrade_18.db`, `upgrade_17.db`).
  - **Robust Data Modeling:** Utilizes Pydantic for strong data validation and clear, self-documenting data structures.
  - **Flexible REST API:** Built with Flask-RESTful to query changes with multiple optional filters like `module`, `model`, and `version`.
  - **Professional Architecture:** Designed with a clean, maintainable project structure that separates concerns (data processing, API, models).

## Project Structure

```
openupgrade-api/
├── .gitignore
├── README.md
├── requirements.txt
├── config.py                   # Configuration file
├── server.py                   # The core Flask API server
├── manage.py                   # CLI tool for data synchronization and parsing
│
├── templates/
│   └── index.html              # API documentation homepage
│
└── upgrade_analysis_parser/
    ├── __init__.py
    ├── models.py               # Pydantic data models
    └── processing/
        ├── __init__.py
        ├── db.py               # Database interaction functions
        ├── parser.py           # File parsing logic
        ├── get.py              # CLI helpers to generate YAML (removed models/fields)
        └── sync.py             # GitHub synchronization logic
```

## Setup and Installation

1.  **Clone the project:**

    ```bash
    git clone git@gitlab.trobz.com:services/openupgrade-api.git
    cd openupgrade-api
    ```

2.  **Create and activate a virtual environment:**

    ```bash
    # Create the environment
    pew new openupgrade-api
    ```

3.  **Install the required dependencies:**

    ```bash
    pip install -r requirements.txt
    ```

## Workflow

The process involves two main steps executed via the `manage.py` script, followed by running the API server.

### Step 1: Sync Data from GitHub

Use the `manage.py sync` command to download the `scripts` directories from the specified OpenUpgrade branches. This will populate the `data_sources/` directory.

```bash
# Sync default versions (16.0, 17.0, 18.0)
python manage.py sync

# Or, sync a specific list of versions
python manage.py sync --versions 18.0 17.0
```

### Step 2: Parse Data into Databases

Use the `manage.py parse` command to process the downloaded files for a specific version and create its corresponding SQLite database in the `databases/` directory.

Run this command for each version you have synced.

```bash
# Parse data default versions (16.0, 17.0, 18.0)
python manage.py parse

# Or, sync a specific list of versions
python manage.py parse --versions 17.0 18.0
```

### Step 3: Generate YAML for Removed Objects (optional)

Use the `manage.py get` command to export removed models and removed fields in a format compatible with the odoo-module-migrator.

Prerequisites: You must have already run `sync` and `parse` for the target versions (so the SQLite DBs exist).

Examples:

```bash
# Removed models for 18.0
python manage.py get --object-type removed --object models --versions 18 --output-directory output

# Removed fields for 18.0
python manage.py get --object-type removed --object fields --versions 18 --output-directory output

# Multiple versions
python manage.py get --object-type removed --object fields --versions 17 18 --output-directory output
```

Output layout:

- Removed models: `{output_dir}/removed_models/migrate_170_180/removed_models.yaml`
- Removed fields: `{output_dir}/removed_fields/migrate_170_180/{module}.yaml`

Notes:

- The migration folder name uses the convention `migrate_<from_version_no_dot>_<to_version_no_dot>` (e.g., `migrate_170_180`).
- If a database is missing for a version, the command will instruct you to run `python manage.py parse --versions <version>`.

### Step 4: Run the API Server

Once the databases are created, start the Flask server.

```bash
python server.py
```

The API server will be running at `http://127.0.0.1:5000`.

## API Documentation

The API provides one main endpoint for querying changes.

### Endpoint

`GET /<major_version>/changes`

  - **`<major_version>`** (float): The major Odoo version to query (e.g., `18.0`).

### Query Parameters

A request **must include at least one** of the following query parameters:

  - `module` (string): Filter changes by a specific module name (e.g., `account`).
  - `model` (string): Filter changes by a specific model name (e.g., `res.partner`).
  - `version` (string): Filter by a specific version string. This uses a "starts with" match, so `?version=18.0.1` will match `18.0.1.3`, etc.

### Usage Examples

#### 1\. Get all changes for the `account` module in version 18.0

```bash
curl "http://127.0.0.1:5000/18.0/changes?module=account"
```

#### 2\. Get all changes for the `res.partner` model in version 17.0

```bash
curl "http://127.0.0.1:5000/17.0/changes?model=res.partner"
```

#### 3\. Combine filters to get changes for `account.account` in the `18.0.1.3` release

```bash
curl "http://127.0.0.1:5000/18.0/changes?model=account.account&version=18.0.1.3"
```