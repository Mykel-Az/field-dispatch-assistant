"""The 15 preset trades as skills, and who may do which job (ADR-034).

Renames the three original skills in place, so technicians, jobs and rules that point at
them keep working. The helper mapping below is plain data: edit it here (or in the
admin) to change who may do a minor job; it is not code.
"""

from django.db import migrations

RENAMES = {
    "HVAC": "Heating & Air Conditioning",
    "Electrical": "Electricians",
    "Appliance Repair": "Appliances and Repair",
}

# category -> (specialist skill, helper skills that may do a MINOR job of that category)
HANDY = "Contractors & Handymen"
TRADES = {
    "hvac": ("Heating & Air Conditioning", [HANDY]),
    "electrical": ("Electricians", [HANDY, "Appliances and Repair"]),
    "appliance": ("Appliances and Repair", [HANDY]),
    "handyman": (HANDY, []),
    "plumbing": ("Plumbers", [HANDY]),
    "roofing": ("Roofing", [HANDY]),
    "locksmith": ("Locksmiths", [HANDY]),
    "painting": ("Painters", [HANDY]),
    "landscaping": ("Landscaping", ["Nurseries & Gardening"]),
    "gardening": ("Nurseries & Gardening", ["Landscaping"]),
    "florist": ("Florists", []),
    "tree_service": ("Tree Services", ["Landscaping"]),
    "cleaning": ("Home Cleaning", []),
    "furniture": ("Furniture Stores", ["Movers"]),
    "movers": ("Movers", []),
}


def forwards(apps, schema_editor):
    Skill = apps.get_model("api", "Skill")
    Rule = apps.get_model("api", "CandidateSkillRule")
    for old, new in RENAMES.items():
        Skill.objects.filter(name=old).update(name=new)
    for specialist, helpers in TRADES.values():
        for name in [specialist, *helpers]:
            Skill.objects.get_or_create(name=name)
    for category, (specialist, helpers) in TRADES.items():
        skill = Skill.objects.get(name=specialist)
        Rule.objects.update_or_create(
            category=category, skill=skill, defaults={"minor_only": False}
        )
        for name in helpers:
            Rule.objects.update_or_create(
                category=category,
                skill=Skill.objects.get(name=name),
                defaults={"minor_only": True},
            )


def backwards(apps, schema_editor):
    Skill = apps.get_model("api", "Skill")
    Rule = apps.get_model("api", "CandidateSkillRule")
    Rule.objects.exclude(category__in=["hvac", "electrical", "appliance"]).delete()
    Rule.objects.filter(minor_only=True).delete()
    for old, new in RENAMES.items():
        Skill.objects.filter(name=new).update(name=old)
    originals = set(RENAMES)
    for _, (specialist, helpers) in TRADES.items():
        for name in [specialist, *helpers]:
            if name not in originals and name not in RENAMES.values():
                Skill.objects.filter(
                    name=name, technicians__isnull=True, jobs__isnull=True
                ).delete()


class Migration(migrations.Migration):
    dependencies = [("api", "0013_candidateskillrule_minor_only_job_complexity_and_more")]
    operations = [migrations.RunPython(forwards, backwards)]
