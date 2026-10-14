class TenantScopedViewMixin:
    def get_queryset(self):
        qs = super().get_queryset()
        org = self.request.user.organization
        return qs.none() if org is None else qs.for_organization(org)
