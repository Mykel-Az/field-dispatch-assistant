from django.db import migrations

# category -> skill name. Skills come from 0002_seed_skills.
RULES = {
    "hvac": "HVAC",
    "electrical": "Electrical",
    "appliance": "Appliance Repair",
}


def seed_rules(apps, schema_editor):
    Skill = apps.get_model("api", "Skill")
    Rule = apps.get_model("api", "CandidateSkillRule")
    for category, skill_name in RULES.items():
        skill, _ = Skill.objects.get_or_create(name=skill_name)
        Rule.objects.get_or_create(category=category, skill=skill)


def unseed_rules(apps, schema_editor):
    Rule = apps.get_model("api", "CandidateSkillRule")
    for category, skill_name in RULES.items():
        Rule.objects.filter(category=category, skill__name=skill_name).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0005_job_jobstatushistory_candidateskillrule_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_rules, unseed_rules),
    ]
