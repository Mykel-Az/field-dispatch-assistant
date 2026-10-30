"""Fill a development database with demo data, so the dispatcher UI has something to show.

    python manage.py seed_demo                 # one organization, ~25 jobs, every status
    python manage.py seed_demo --bulk 70       # plus 70 more jobs, to try pagination (50 per page)
    python manage.py seed_demo --reset         # wipe the demo organizations first, then seed

Everything goes through the real services (create_job, transition), so every job has a
genuine status history. Dates are relative to today, so the date filter always has data.
Hours are the organization's local clock (Central), the same clock the app shows.

Refuses to run unless DEBUG is on (so it can never fill production), unless --force.
Geocoding always uses the fake geocoder: no network, and two addresses are rigged to fail
so the "location needs attention" flag has something to show.
"""

import datetime
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.test import override_settings
from django.utils import timezone

from api.models import (
    CustomUser,
    Job,
    JobStatusHistory,
    Organization,
    Skill,
    Technician,
)
from api.services import jobs as svc

PASSWORD = "Demo-Passw0rd!"
CENTRAL = ZoneInfo("America/Chicago")
ORG_NAME = "Brightline Service Co."
OTHER_ORG_NAME = "Northwind Repairs (other organization)"

# (email, full name, role, skills)
STAFF = [
    ("head@demo.example", "Priya Nair", "head_dispatcher", None),
    ("dispatcher@demo.example", "Alex Morgan", "dispatcher", None),
    ("dana@demo.example", "Dana Reyes", "technician", ["HVAC", "Electrical"]),
    ("tomas@demo.example", "Tomás Silva", "technician", ["Appliance Repair"]),
    ("aisha@demo.example", "Aisha Bello", "technician", ["Electrical", "HVAC"]),
    (
        "marcus@demo.example",
        "Marcus Chen",
        "technician",
        ["HVAC", "Electrical", "Appliance Repair"],
    ),
]

# Paths a job walks through. "assigned" needs a technician; the others may carry ":reason".
UNASSIGNED, ASSIGNED = [], ["assigned"]
ONGOING = ["assigned", "ongoing"]
COMPLETED = ["assigned", "ongoing", "completed"]
CANCEL_QUEUED = ["canceled:Customer rescheduled"]

# day offset, title, customer, category, address, zip, start hour (UTC), hours, urgent,
# technician key, path, phone, description
JOBS = [
    # yesterday: finished work, for the history
    (
        -1,
        "Replace condenser fan motor",
        "Harper Row Lofts",
        "hvac",
        "510 E 6th St",
        "78701",
        8,
        2,
        False,
        "dana",
        COMPLETED,
        "512-555-0141",
        "Fan motor seized. Part ordered and on the truck.",
    ),
    (
        -1,
        "Outlet sparking in kitchen",
        "Joy Mensah",
        "electrical",
        "2301 Rio Grande St",
        "78705",
        9,
        2,
        False,
        "aisha",
        COMPLETED,
        "512-555-0178",
        "",
    ),
    (
        -1,
        "Washer not draining",
        "Carl Nguyen",
        "appliance",
        "4410 Duval St",
        "78751",
        10,
        2,
        False,
        "tomas",
        ASSIGNED + ["ongoing", "failed:Customer not home, no answer after 20 minutes"],
        None,
        "",
    ),
    (
        -1,
        "Install ceiling fans (3)",
        "Lakeview Dental",
        "electrical",
        "1200 Barton Springs Rd",
        "78704",
        13,
        3,
        False,
        "marcus",
        ASSIGNED + ["ongoing", "incomplete:Needs a taller ladder, returning tomorrow"],
        "512-555-0112",
        "Three fans, 12 ft ceilings.",
    ),
    (
        -1,
        "Furnace tune-up",
        "Ruth Adler",
        "hvac",
        "9 Mesa Dr",
        "78731",
        14,
        1,
        False,
        None,
        CANCEL_QUEUED,
        None,
        "",
    ),
    # today: a busy board
    (
        0,
        "AC not cooling",
        "Maya Okafor",
        "hvac",
        "1204 Congress Ave",
        "78701",
        9,
        2,
        True,
        None,
        UNASSIGNED,
        "512-555-0190",
        "Unit blowing warm air since last night. Elderly resident at home.",
    ),
    (
        0,
        "Dishwasher leaking",
        "Ben Alvarez",
        "appliance",
        "17 Oak Hollow Ln",
        "78745",
        8,
        2,
        False,
        "tomas",
        ONGOING,
        "512-555-0123",
        "",
    ),
    (
        0,
        "Replace main service panel and relocate meter base",
        "Lone Star Dental",
        "electrical",
        "88 Barton Springs Rd",
        "78704",
        8,
        4,
        False,
        "marcus",
        ONGOING,
        "512-555-0166",
        "200A upgrade. Utility has already scheduled the disconnect for 8:00.\nParking behind the building.",
    ),
    (
        0,
        "Thermostat replacement",
        "Harper Row Lofts",
        "hvac",
        "510 E 6th St",
        "78701",
        11,
        1,
        False,
        "dana",
        ASSIGNED,
        None,
        "",
    ),
    (
        0,
        "Refrigerator not cooling",
        "Mei Tanaka",
        "appliance",
        "301 W 2nd St",
        "78701",
        13,
        2,
        False,
        "tomas",
        ASSIGNED,
        "512-555-0155",
        "",
    ),
    (
        0,
        "Breaker keeps tripping",
        "Okonkwo Residence",
        "electrical",
        "2214 Pecan Ct",
        "78702",
        14,
        2,
        False,
        "aisha",
        ASSIGNED,
        "512-555-0132",
        "",
    ),
    (
        0,
        "Gas smell near furnace",
        "Birch Way Apartments",
        "hvac",
        "3 Birch Way",
        "78756",
        0,
        0,
        True,
        "dana",
        ASSIGNED,
        "512-555-0100",
        "Tenant reports gas smell. Shut off supply if confirmed.",
    ),
    (
        0,
        "Ice maker repair",
        "Tulip Bakery",
        "appliance",
        "812 Lavaca St",
        "78701",
        16,
        1,
        False,
        None,
        UNASSIGNED,
        None,
        "",
    ),
    (
        0,
        "Window AC install",
        "Pecan Court 4B",
        "hvac",
        "Unit 4B, Pecan Court (unfindable)",
        "78702",
        15,
        1,
        False,
        None,
        UNASSIGNED,
        None,
        "Rigged to fail geocoding: shows the location flag.",
    ),
    (
        0,
        "Water heater flush",
        "Rosa Delgado",
        "appliance",
        "55 Cedar Ln",
        "78703",
        10,
        1,
        False,
        None,
        ["canceled:Customer found another provider"],
        None,
        "",
    ),
    (
        0,
        "Garage outlet install",
        "Samir Haddad",
        "electrical",
        "92 Oak St",
        "78704",
        15,
        1,
        False,
        "aisha",
        ASSIGNED + ["canceled:Job no longer needed"],
        None,
        "",
    ),
    # tomorrow and the day after: mostly unplanned
    (
        1,
        "Annual HVAC inspection (5 units)",
        "Greenway Offices",
        "hvac",
        "700 Lavaca St",
        "78701",
        9,
        4,
        False,
        None,
        UNASSIGNED,
        "512-555-0107",
        "Five rooftop units. Access via the loading dock.",
    ),
    (
        1,
        "EV charger circuit",
        "Chen Residence",
        "electrical",
        "5 Elm St",
        "78703",
        10,
        2,
        False,
        "marcus",
        ASSIGNED,
        "512-555-0149",
        "",
    ),
    (
        1,
        "Oven won't heat",
        "Julia Park",
        "appliance",
        "22 Rainey St",
        "78701",
        9,
        1,
        False,
        "tomas",
        ASSIGNED,
        None,
        "",
    ),
    (
        1,
        "Mini-split install",
        "Santos Residence",
        "hvac",
        "1500 S Lamar Blvd",
        "78704",
        13,
        4,
        False,
        None,
        UNASSIGNED,
        "512-555-0181",
        "",
    ),
    (
        1,
        "Replace living room light fixtures",
        "Wilshire Rentals",
        "electrical",
        "31 Wilshire Blvd",
        "78722",
        15,
        1,
        False,
        None,
        UNASSIGNED,
        None,
        "",
    ),
    (
        1,
        "Cedar Lane service call",
        "Cedar Lane HOA",
        "electrical",
        "17 Cedar Ln (boom)",
        "78703",
        11,
        1,
        False,
        None,
        UNASSIGNED,
        None,
        "Rigged so the geocoder errors: shows the location flag.",
    ),
    (
        2,
        "Duct cleaning",
        "Mesa Drive Homes",
        "hvac",
        "8 Mesa Dr",
        "78731",
        9,
        3,
        False,
        None,
        UNASSIGNED,
        None,
        "",
    ),
    (
        2,
        "Dryer vent clearing",
        "Ola Bello",
        "appliance",
        "1011 E 11th St",
        "78702",
        10,
        1,
        False,
        None,
        UNASSIGNED,
        "512-555-0162",
        "",
    ),
    (
        2,
        "Smoke detector replacement",
        "Westcampus Co-op",
        "electrical",
        "600 W 28th St",
        "78705",
        14,
        1,
        False,
        None,
        UNASSIGNED,
        None,
        "",
    ),
]

BULK_TITLES = [
    ("Service call", "hvac"), ("Wiring inspection", "electrical"), ("Appliance repair", "appliance"),
    ("Filter replacement", "hvac"), ("Fuse box check", "electrical"), ("Stove igniter", "appliance"),
]  # fmt: skip
BULK_STREETS = [
    "Oak St",
    "Elm St",
    "Pecan Ct",
    "Cedar Ln",
    "Birch Way",
    "Mesa Dr",
    "Lamar Blvd",
]


class Command(BaseCommand):
    help = "Create demo organizations, staff and jobs for trying out the dispatcher UI."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset", action="store_true", help="delete the demo organizations first"
        )
        parser.add_argument(
            "--bulk",
            type=int,
            default=0,
            metavar="N",
            help="also create N extra unassigned jobs",
        )
        parser.add_argument(
            "--force", action="store_true", help="run even when DEBUG is off"
        )

    def handle(self, *args, **options):
        if not settings.DEBUG and not options["force"]:
            raise CommandError(
                "seed_demo only runs with DEBUG on (use --force if you are sure)."
            )

        with override_settings(GEOCODER_CLASS="geocoding.fake.FakeGeocoder"):
            if options["reset"]:
                self._reset()
            elif Organization.objects.filter(name=ORG_NAME).exists():
                self.stdout.write(
                    "Demo data already exists. Use --reset to rebuild it."
                )
                self._print_logins()
                return
            org, users = self._create_organization()
            self._create_jobs(org, users)
            if options["bulk"]:
                self._create_bulk(org, users, options["bulk"])
            self._create_other_organization()

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {Job.objects.filter(organization=org).count()} jobs."
            )
        )
        self._print_logins()

    # ---- building blocks ----------------------------------------------------
    def _reset(self):
        ids = list(
            Organization.objects.filter(
                name__in=[ORG_NAME, OTHER_ORG_NAME]
            ).values_list("pk", flat=True)
        )
        if not ids:
            return
        # History is append-only: its queryset refuses delete(), so wipe it at SQL level.
        # Development databases only; this is why the command refuses to run without DEBUG.
        JobStatusHistory.objects.filter(organization_id__in=ids)._raw_delete(
            using="default"
        )
        Job.objects.filter(organization_id__in=ids).delete()
        CustomUser.objects.filter(
            organization_id__in=ids
        ).delete()  # technician profiles cascade
        Organization.objects.filter(pk__in=ids).delete()
        self.stdout.write("Removed the previous demo data.")

    def _create_organization(self):
        org = Organization.objects.create(
            name=ORG_NAME, email="office@brightline.example", phone="512-555-0100",
            address="100 Congress Ave", postal_code="78701", lat=30.2655, lng=-97.7431,
            geocode_status="ok", location_label="100 Congress Ave, Austin, TX 78701",
            work_start=datetime.time(7), work_end=datetime.time(18),
            timezone="America/Chicago",
        )  # fmt: skip
        users = {}
        for email, name, role, skill_names in STAFF:
            user = CustomUser.objects.create_user(
                email=email,
                password=PASSWORD,
                full_name=name,
                role=role,
                organization=org,
            )
            users[email.split("@")[0]] = user
            if role == "technician":
                profile = Technician.objects.create(
                    user=user, organization=org, phone="512-555-0100",
                    shift_start=datetime.time(8), shift_end=datetime.time(17),
                )  # fmt: skip
                profile.skills.set(Skill.objects.filter(name__in=skill_names))
        return org, users

    def _create_jobs(self, org, users):
        today = timezone.now().astimezone(CENTRAL).date()
        actor = users["dispatcher"]
        for (
            offset,
            title,
            customer,
            category,
            address,
            zip_code,
            hour,
            hours,
            urgent,
            tech,
            path,
            phone,
            notes,
        ) in JOBS:
            day = today + datetime.timedelta(days=offset)
            fields = {
                "title": title, "customer_name": customer, "customer_phone": phone,
                "description": notes, "category": category, "address": address,
                "postal_code": zip_code, "is_urgent": urgent, "scheduled_date": day,
                "estimated_duration_minutes": max(hours, 1) * 60,
            }  # fmt: skip
            if not urgent:
                start = datetime.datetime.combine(
                    day, datetime.time(hour), tzinfo=CENTRAL
                )
                fields.update(
                    slot_start=start, slot_end=start + datetime.timedelta(hours=hours)
                )
            job = svc.create_job(
                organization=org,
                actor=actor,
                skills=svc.default_skills_for(category),
                **fields,
            )
            self._walk(job, path, users, tech)

    def _walk(self, job, path, users, tech_key):
        for step in path:
            to, _, reason = step.partition(":")
            if to == "assigned":
                technician = Technician.objects.get(user=users[tech_key])
                job = svc.transition(
                    job, to, users["dispatcher"], technician=technician
                )
            elif to == "canceled":
                job = svc.cancel_job(job=job, actor=users["head"], reason=reason)
            else:
                job = svc.transition(job, to, users["dispatcher"], reason)

    def _create_bulk(self, org, users, count):
        today = timezone.now().astimezone(CENTRAL).date()
        for i in range(count):
            title, category = BULK_TITLES[i % len(BULK_TITLES)]
            day = today + datetime.timedelta(days=i % 5)
            start = datetime.datetime.combine(
                day, datetime.time(8 + i % 8), tzinfo=CENTRAL
            )
            svc.create_job(
                organization=org, actor=users["dispatcher"], skills=svc.default_skills_for(category),
                title=f"{title} #{i + 1}", customer_name=f"Customer {i + 1}", category=category,
                address=f"{100 + i} {BULK_STREETS[i % len(BULK_STREETS)]}", postal_code=f"787{i % 40:02d}",
                scheduled_date=day, slot_start=start, slot_end=start + datetime.timedelta(hours=1),
            )  # fmt: skip

    def _create_other_organization(self):
        """A second tenant, so you can check by eye that its jobs never show up."""
        org = Organization.objects.create(name=OTHER_ORG_NAME)
        head = CustomUser.objects.create_user(
            email="head@other.example", password=PASSWORD, full_name="Olivia Stone",
            role="head_dispatcher", organization=org,
        )  # fmt: skip
        start = datetime.datetime.combine(
            timezone.now().astimezone(CENTRAL).date(), datetime.time(10), tzinfo=CENTRAL
        )
        svc.create_job(
            organization=org, actor=head, skills=svc.default_skills_for("hvac"),
            title="SECRET: other organization's job", customer_name="Nobody You Should See",
            category="hvac", address="1 Hidden Rd", postal_code="78701",
            scheduled_date=start.date(), slot_start=start, slot_end=start + datetime.timedelta(hours=1),
        )  # fmt: skip

    def _print_logins(self):
        self.stdout.write(f"\nSign in with password {PASSWORD}")
        for email, name, role, _ in STAFF:
            self.stdout.write(f"  {role:16s} {email:26s} {name}")
        self.stdout.write(
            "  other tenant     head@other.example         (should see none of the jobs above)"
        )
