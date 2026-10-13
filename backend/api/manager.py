from django.db import models


class TenanatQuerySet(models.QuerySet):
    def for_organization(self, org):
        return self.filter(organization=org)
