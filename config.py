import os
from dotenv import load_dotenv

load_dotenv()

FLASK_HOST = os.environ.get("FLASK_HOST", "localhost")
FLASK_PORT = int(os.environ.get("FLASK_PORT", 5000))
DEBUG = os.environ.get("DEBUG", False)
DB_PATH = os.environ.get("DB_PATH", "./databases")
LOG_PATH = os.environ.get("LOG_PATH", "./logs")
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
CORS_ALLOW = os.environ.get("CORS_ALLOW", "http://localhost:5000")
