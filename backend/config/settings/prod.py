from .base import *

db_url = os.getenv("DATABASE_URL", 'sqlite:///db.sqlite3')


DATABASES = {
    'default': db_url
}