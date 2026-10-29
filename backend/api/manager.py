from django.db import models


class TenantQuerySet(models.QuerySet):
    """Adds .for_organization(org) to any manager built from it."""

    def for_organization(self, org):
        return self.filter(organization=org)


class TenantScopedModel(models.Model):
    """Abstract base for every model that belongs to exactly one organization."""

    organization = models.ForeignKey(
        "Organization", on_delete=models.PROTECT, related_name="%(class)ss"
    )

    objects = TenantQuerySet.as_manager()

    class Meta:
        abstract = True


class AppendOnlyQuerySet(TenantQuerySet):
    """Blocks bulk UPDATE and DELETE; used by the append-only history table."""

    def update(self, **kwargs):
        raise ValueError("history rows are append-only")

    def delete(self):
        raise ValueError("history rows are append-only")
