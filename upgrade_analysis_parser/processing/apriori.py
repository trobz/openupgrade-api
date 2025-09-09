import requests
from .db import sqlite_db
from config import APRIORI_VERSIONS

def get_apriori(version, only_table = None):
    apriori = {}
    with sqlite_db('apriori') as cursor:
        if only_table in (None, "renamed_modules"):
            renamed_modules = cursor.execute(
                'SELECT old_name , new_name FROM renamed_modules '
                'WHERE version = ?', (version,)
            ).fetchall()
            apriori["renamed_modules"] = dict([(k, v) for k, v in renamed_modules])

        if only_table in (None, "merged_modules"):
            merged_modules = cursor.execute(
                'SELECT from_name, to_name FROM merged_modules '
                'WHERE version = ?', (version,)
            ).fetchall()
            apriori["merged_modules"] = dict([(k, v) for k, v in merged_modules])
    
    return apriori

def query_apriori(query, only_table = None):
    apriori = {}
    with sqlite_db('apriori') as cursor:
        if only_table in (None, "renamed_modules"):
            renamed_modules = cursor.execute(
                'SELECT version , new_name FROM renamed_modules '
                'WHERE old_name = ?', (query,)
            ).fetchall()
            apriori["renamed_modules"] = dict([(k, v) for k, v in renamed_modules])

        if only_table in (None, "merged_modules"):
            merged_modules = cursor.execute(
                'SELECT version, to_name FROM merged_modules '
                'WHERE from_name = ?', (query,)
            ).fetchall()
            apriori["merged_modules"] = dict([(k, v) for k, v in merged_modules])
    
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
