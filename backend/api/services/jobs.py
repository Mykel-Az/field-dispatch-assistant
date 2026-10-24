from django.db import transaction

transaction.atomic()


def transition(job, to, actor, reason=""):
    pass
