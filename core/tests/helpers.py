"""Κοινά δεδομένα για τους ελέγχους."""
from accounts.models import Role, User
from core.models import AgeGroup, Declaration, District, Organisation, Period, PreventionLevel, Programme, Setting

PASSWORD = "x-Long-pass-123"


def make_org(code, active=True):
    return Organisation.objects.create(name=f"Φορέας {code}", code=code, is_active=active)


def make_user(username, org=None, aaek=False):
    if aaek:
        return User.objects.create_user(username, password=PASSWORD, role=Role.AAEK)
    return User.objects.create_user(username, password=PASSWORD, role=Role.ORGANISATION, organisation=org)


def make_programme(org, title, officer=None, level=PreventionLevel.UNIVERSAL, district=None, ages=("13–15",)):
    p = Programme.objects.create(
        organisation=org, title=title, level=level, officer=officer,
        district=district or District.objects.get(name="Λευκωσία"), setting=Setting.objects.get(name="Σχολείο"),
    )
    p.age_groups.set(AgeGroup.objects.filter(name__in=ages))
    return p


def declare(programme, period=None, open_start=10, new=20, completed=15, withdrawn=5, **kw):
    return Declaration.objects.create(
        programme=programme, period=period or Period.to_declare(), open_start=open_start, new=new,
        completed=completed, withdrawn=withdrawn, **kw,
    )


def age(name):
    return AgeGroup.objects.get(name=name)
