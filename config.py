import os
from dotenv import load_dotenv

load_dotenv()

FLASK_HOST = os.environ.get("FLASK_HOST", "localhost")
FLASK_PORT = int(os.environ.get("FLASK_PORT", 5000))
DEBUG = os.environ.get("DEBUG", False)
LOG_PATH = os.environ.get("LOG_PATH", "./logs")
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
CORS_ALLOW = os.environ.get("CORS_ALLOW", "http://localhost:5001")

DB_PATH = os.environ.get("DB_PATH", "./databases")
OPENUPGRADE_REPO_URL = os.environ.get("OPENUPGRADE_REPO_URL", "https://github.com/OCA/OpenUpgrade.git")
OPENUPGRADE_REPO_PATH = os.environ.get("OPENUPGRADE_REPO_PATH", "./OpenUpgrade_Repo")
OPENUPGRADE_SCRIPTS_SOURCES_PATH = os.environ.get("OPENUPGRADE_SCRIPTS_SOURCES_PATH", "./data_sources")

# Google Analytics
GOOGLE_ANALYTICS_ID = os.environ.get("GOOGLE_ANALYTICS_ID", "")

# APRIORI
APRIORI_VERSIONS = os.environ.get("APRIORI_VERSIONS", "12.0,13.0,14.0,15.0,16.0,17.0,18.0")
APRIORI_INTERNAL_DOCUMENT_PATH = os.environ.get("APRIORI_INTERNAL_DOCUMENT_PATH", "./databases")
APRIORI_INTERNAL_DOCUMENT_NAME = os.environ.get("APRIORI_INTERNAL_DOCUMENT_NAME", "")
APRIORI_INTERNAL_DOCUMENT_URL = os.environ.get("APRIORI_INTERNAL_DOCUMENT_URL", "")