from .base import *

DEBUG = True
SECRET_KEY = "django-insecure-zrpm8kjx(6v#krft77fzoa9@l9vjftbgt%h*^zk=l3^#ax#gnh"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}
