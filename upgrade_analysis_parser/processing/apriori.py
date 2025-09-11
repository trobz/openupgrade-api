# Copyright 2025 Trobz
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl)

import requests, os, csv
from .db import sqlite_db
from config import APRIORI_VERSIONS, APRIORI_INTERNAL_DOCUMENT_PATH, APRIORI_INTERNAL_DOCUMENT_NAME, APRIORI_INTERNAL_DOCUMENT_URL

def _fetch_apriori_from_db(cursor, table, key_col, value_col, filter_col, filter_val):
    rows = cursor.execute(
        f"SELECT {key_col}, {value_col} FROM {table} WHERE {filter_col} = ?", (filter_val,)
    ).fetchall()
    return dict(rows)

def _fetch_apriori_from_csv(path, version=None, query=None):
    results = {}
    with open(path, "r", newline="", encoding="utf-8") as file:
        csv_file = csv.reader(file)
        for row in csv_file:
            module_name, repo, raw_version, status, detail, references = row[:6] if len(row) > 5 else None
            norm_version = normalize_version(raw_version)

            if version:
                if norm_version != version:
                    continue
                if status == "not needed anymore":
                    results.setdefault("not_needed", {})[module_name] = (detail, references)
                elif status == "moved to different repo":
                    results.setdefault("moved_modules", {})[module_name] = detail
            
            elif query:
                if module_name != query:
                    continue
                ver_dict = results.setdefault(norm_version, {})
                if status == "not needed anymore":
                    ver_dict.setdefault("not_needed", {})[module_name] = "odoo"
                elif status == "moved to different repo":
                    ver_dict.setdefault("moved_modules", {})[module_name] = detail
    return results

def get_apriori(version, only_table = None):
    apriori = {}
    with sqlite_db('apriori') as cursor:
        if only_table in (None, "renamed_modules"):
            apriori["renamed_modules"] = _fetch_apriori_from_db(cursor, "renamed_modules", "old_name", "new_name", "version", version)

        if only_table in (None, "merged_modules"):
            apriori["merged_modules"] = _fetch_apriori_from_db(cursor, "merged_modules", "from_name", "to_name", "version", version)
    
    if APRIORI_INTERNAL_DOCUMENT_NAME:
        path = os.path.join(APRIORI_INTERNAL_DOCUMENT_PATH, APRIORI_INTERNAL_DOCUMENT_NAME)
        apriori.update(_fetch_apriori_from_csv(path, version=version))

    return apriori

def query_apriori(query, only_table = None):
    apriori = {}
    with sqlite_db('apriori') as cursor:
        if only_table in (None, "renamed_modules"):
            apriori["renamed_modules"] = _fetch_apriori_from_db(cursor, "renamed_modules", "version", "new_name", "old_name", query)

        if only_table in (None, "merged_modules"):
            apriori["merged_modules"] = _fetch_apriori_from_db(cursor, "merged_modules", "version", "to_name", "from_name", query)
    if APRIORI_INTERNAL_DOCUMENT_NAME:
        path = os.path.join(APRIORI_INTERNAL_DOCUMENT_PATH, APRIORI_INTERNAL_DOCUMENT_NAME)
        apriori.update(_fetch_apriori_from_csv(path, query=query))

    return apriori

def parse_apriori():
    versions = APRIORI_VERSIONS.split(',')
    with sqlite_db('apriori', clean=True) as cursor:
        # After clean, we need to create schema
        make_schema(cursor)

        for version in versions:
            version = version.strip()
            try:
                url = get_url(version)
            except ValueError:
                continue
            r = requests.get(url)
            r.raise_for_status()
            _globals = {}
            _locals = {}
            exec(r.text, _globals, _locals)
            for old_name, new_name in _locals["renamed_modules"].items():
                cursor.execute(
                    'INSERT INTO renamed_modules (version, old_name, new_name) VALUES (?, ?, ?)',
                    (version, old_name, new_name)
                )
            for from_name, to_name in _locals["merged_modules"].items():
                cursor.execute(
                    'INSERT INTO merged_modules (version, from_name, to_name) VALUES (?, ?, ?)',
                    (version, from_name, to_name)
                )

        if APRIORI_INTERNAL_DOCUMENT_PATH and APRIORI_INTERNAL_DOCUMENT_NAME and APRIORI_INTERNAL_DOCUMENT_URL:
            csv_path = os.path.join(APRIORI_INTERNAL_DOCUMENT_PATH, APRIORI_INTERNAL_DOCUMENT_NAME)
            download(csv_path, APRIORI_INTERNAL_DOCUMENT_URL)
            
def get_url(version):
    compare_version = ('0' if len(version) < 4 else '') + version
    if compare_version <= '09.0':
        raise ValueError(f"Version {version} is not supported")
    elif compare_version <= '13.0':
        return f'https://github.com/OCA/OpenUpgrade/raw/refs/heads/{version}/odoo/addons/openupgrade_records/lib/apriori.py'
    else:
        return f'https://github.com/oca/OpenUpgrade/raw/refs/heads/{version}/openupgrade_scripts/apriori.py'

def make_schema(db):
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS renamed_modules (
            id INTEGER PRIMARY KEY,
            version TEXT,
            old_name TEXT,
            new_name TEXT,
            UNIQUE(version, old_name)
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS merged_modules (
            id INTEGER PRIMARY KEY,
            version TEXT,
            from_name TEXT,
            to_name TEXT,
            UNIQUE(version, from_name)
        )
        """
    )

def normalize_version(version):
    parts = version.split('.')
    if len(parts) == 1:
        return f'{version}.0'
    else:
        return version

def download(path, url):
    response = requests.get(url)
    response.raise_for_status()
    with open(path, "wb") as f:
        f.write(response.content)