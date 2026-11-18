"""Watch the planner think: run it for one day, print every decision, then undo it.

    python manage.py plan_trace --email dispatcher@demo.example --date 2026-11-20

Nothing is saved: the run happens inside a transaction that is rolled back, so the
jobs stay unassigned and can be planned again from the app. The trail comes from the
planner's own log (`dispatch_engine.assign`), turned up to DEBUG for this command:
for each job, who was feasible, who was rejected and why, how they ranked, and who
got it. The table at the end uses job titles because this is a developer's console;
the log itself carries ids and numbers only.
"""

import datetime
import logging
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from api.models import CustomUser, Job, Technician
from api.services.scheduling import generate_schedule

LOGGERS = ("dispatch_engine", "api.services.scheduling")


class _Rollback(Exception):
    """Raised inside the transaction so the dry run is never saved."""


class Command(BaseCommand):
    help = "Run the planner for one day, print how it decided, and save nothing."

    def add_arguments(self, parser):
        parser.add_argument(
            "--email", required=True, help="a dispatcher in the organization"
        )
        parser.add_argument(
            "--date", help="YYYY-MM-DD in the organization's time zone (default: today)"
        )

    def handle(self, *args, email, date=None, **options):
        try:
            actor = CustomUser.objects.select_related("organization").get(email=email)
        except CustomUser.DoesNotExist:
            raise CommandError(f"no user with the email {email!r}") from None
        if actor.organization is None:
            raise CommandError("that user has no organization")
        try:
            plan_date = datetime.date.fromisoformat(date) if date else None
        except ValueError:
            raise CommandError("--date must look like 2026-11-20") from None

        handler = logging.StreamHandler(self.stdout)
        handler.setFormatter(logging.Formatter("%(name)s: %(message)s"))
        saved = {}
        for name in LOGGERS:
            logger = logging.getLogger(name)
            saved[name] = (logger.level, logger.propagate)
            logger.setLevel(logging.DEBUG)
            logger.propagate = False  # print once, not again through the root handler
            logger.addHandler(handler)

        result = None
        try:
            with transaction.atomic():
                result = generate_schedule(
                    organization=actor.organization, actor=actor, plan_date=plan_date
                )
                self._print_table(result, ZoneInfo(actor.organization.timezone))
                raise _Rollback
        except _Rollback:
            pass
        finally:
            for name in LOGGERS:
                logger = logging.getLogger(name)
                logger.removeHandler(handler)
                logger.setLevel(saved[name][0])
                logger.propagate = saved[name][1]
        self.stdout.write(self.style.WARNING("Dry run: nothing was saved."))

    def _print_table(self, result, tz):
        titles = dict(
            Job.objects.filter(
                pk__in=[p.job_id for p in result.assigned]
                + [u.job_id for u in result.unassigned]
            ).values_list("pk", "title")
        )
        names = {
            t.pk: t.user.full_name
            for t in Technician.objects.select_related("user").all()
        }
        self.stdout.write(
            f"\nPlan for {result.plan_date} (times in the organization's time zone)"
        )
        for p in sorted(
            result.assigned, key=lambda p: (p.technician_id, p.estimated_arrival)
        ):
            self.stdout.write(
                f"  {names.get(p.technician_id, p.technician_id):<16} "
                f"{p.estimated_arrival.astimezone(tz):%H:%M}  {titles[p.job_id]}  "
                f"[{p.sla_label}, slack {p.slack_minutes:.0f} min]"
            )
        for u in result.unassigned:
            self.stdout.write(f"  unassigned: {titles[u.job_id]}")
        for s in result.skipped:
            self.stdout.write(f"  skipped: job {s.job_id} ({s.code})")
