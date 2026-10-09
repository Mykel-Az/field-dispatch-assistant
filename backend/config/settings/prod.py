import dj_database_url

from .base import *
from dotenv import load_dotenv

load_dotenv()

db_url = os.getenv("DATABASE_URL", "sqlite:///db.sqlite3")

DEBUG = False


SECRET_KEY = os.getenv("SECRET_KEY")
DATABASES = {
    "default": dj_database_url.config(db_url, conn_max_age=600, ssl_require=True)
}
