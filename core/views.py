import csv
from datetime import datetime

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView

from .access import AaekRequiredMixin, OfficerRequiredMixin, is_aaek, officer_programmes
from .forms import StepNewForm, StepOutcomeForm, StepProfileForm
from .models import DECLARABLE_LEVELS, AgeGroup, Declaration, District, Period, PreventionLevel, Programme
from .stats import HIDDEN, age_breakdown, suppress, totals

STEPS = 4
DRAFT_TTL_SECONDS = 2 * 60 * 60  # πάνω από 2 ώρες ο χρόνος συμπλήρωσης δεν μετρά (ξεχασμένη καρτέλα)


def home(request):
    if not request.user.is_authenticated:
        return redirect("login")
    if is_aaek(request.user):
        return redirect("aaek_dashboard")
    return redirect("programme_list")


def _status(programme, period):
    d = programme.declaration_for(period)
    return {"declaration": d, "submitted": d is not None}


# ---------------------------------------------------------------- Φορέας

class ProgrammeListView(OfficerRequiredMixin, TemplateView):
    """«Ποιο πρόγραμμα διαχειρίζεστε;»"""

    template_name = "core/programme_list.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        period = Period.to_declare()
        progs = list(officer_programmes(self.request.user))
        ctx["period"] = period
        ctx["items"] = [{"p": p, **_status(p, period)} for p in progs]
        return ctx


class ProgrammeHomeView(OfficerRequiredMixin, TemplateView):
    template_name = "core/programme_home.html"

    def get_context_data(self, pk, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # Πρόγραμμα που δεν έχει ανατεθεί στον χρήστη → 404, ώστε να μη φαίνεται καν ότι υπάρχει.
        p = get_object_or_404(officer_programmes(self.request.user).prefetch_related("age_groups"), pk=pk)
        period = Period.to_declare()
        current = p.declaration_for(period)
        history = []
        for per in Period.recent(3):
            history.append({"period": per, "d": p.declaration_for(per), "expected": p.expected_in(per)})
        last = p.declarations.select_related("period").order_by("-period__year", "-period__part").first()
        ctx.update(p=p, period=period, current=current, history=history, last=last,
                   can_declare=p.is_declarable and p.expected_in(period),
                   can_edit=current is None or period.is_open_for_edits())
        return ctx


class DeclarationView(OfficerRequiredMixin, View):
    """Δήλωση τετραμηνίας σε 4 βήματα. Το πρόχειρο κρατιέται στη συνεδρία μέχρι την υποβολή."""

    template_name = "core/declaration.html"

    def setup_ctx(self, request, pk, step):
        self.p = get_object_or_404(officer_programmes(request.user).prefetch_related("age_groups"), pk=pk)
        self.period = Period.to_declare()
        if not (self.p.is_declarable and self.p.expected_in(self.period)):
            raise Http404
        self.existing = self.p.declaration_for(self.period)
        if self.existing and not self.period.is_open_for_edits():
            messages.info(request, f"Η προθεσμία διόρθωσης ({self.period.deadline:%d/%m/%Y}) πέρασε.")
            return redirect("programme_home", pk=pk)
        if not 1 <= step <= STEPS:
            raise Http404
        prev = self.p.previous_declaration(self.period)
        # Χωρίς προηγούμενη δήλωση, οι ανοικτές περιπτώσεις αρχής δεν είναι γνωστές: τις ζητάμε.
        self.first = prev is None
        self.key = f"draft:{self.p.pk}:{self.period.pk}"
        self.draft = request.session.get(self.key)
        if self.draft is None or self.draft_expired():
            self.draft = self.initial_draft(prev)
            request.session[self.key] = self.draft
        return None

    def draft_expired(self):
        try:
            started = datetime.fromisoformat(self.draft["started"])
        except (KeyError, ValueError):
            return True
        return (timezone.now() - started).total_seconds() > DRAFT_TTL_SECONDS

    def initial_draft(self, prev):
        d = self.existing
        draft = {"started": timezone.now().isoformat(), "open_start": prev.open_end if prev else None}
        if d:
            draft.update(open_start=d.open_start, new=d.new, completed=d.completed, withdrawn=d.withdrawn,
                         sex=d.sex, ages=d.ages, note=d.note)
        return draft

    @property
    def age_split(self):
        targets = list(self.p.age_groups.all())
        others = [a for a in AgeGroup.objects.all() if a not in targets]
        return targets, others

    def months(self):
        a, b, _ = Period.PARTS[self.period.part]
        names = {1: "Ιανουάριο", 5: "Μάιο", 9: "Σεπτέμβριο", 4: "Απρίλιο", 8: "Αύγουστο", 12: "Δεκέμβριο"}
        return f"{names[a]} μέχρι {names[b]}"

    def make_form(self, step, data=None):
        d = self.draft
        if step == 1:
            init = {"new": d.get("new"), "open_start": d.get("open_start")}
            return StepNewForm(data, initial=init, first_declaration=self.first, months=self.months())
        if step == 2:
            served = (d.get("open_start") or 0) + (d.get("new") or 0)
            return StepOutcomeForm(data, initial={"completed": d.get("completed"), "withdrawn": d.get("withdrawn")},
                                   served=served)
        if step == 3:
            targets, others = self.age_split
            init = {"note": d.get("note", "")}
            if d.get("sex"):
                init.update(dict(zip(["sex_male", "sex_female", "sex_other"], d["sex"])))
            for k, v in (d.get("ages") or {}).items():
                init[f"age_{k}"] = v
            return StepProfileForm(data, initial=init, new=d.get("new") or 0, target_ages=targets, other_ages=others)
        return None

    def missing_step(self):
        """Το πρώτο βήμα που δεν έχει συμπληρωθεί (π.χ. αν κάποιος γράψει το URL του βήματος 3)."""
        d = self.draft
        if d.get("new") is None or d.get("open_start") is None:
            return 1
        if d.get("completed") is None or d.get("withdrawn") is None:
            return 2
        return None

    def render_step(self, request, step, form=None):
        d = self.draft
        targets, others = self.age_split
        served = (d.get("open_start") or 0) + (d.get("new") or 0)
        ctx = {
            "p": self.p, "period": self.period, "step": step, "steps": range(1, STEPS + 1), "form": form,
            "draft": d, "first": self.first, "served": served, "existing": self.existing,
            "open_end": served - (d.get("completed") or 0) - (d.get("withdrawn") or 0),
            "age_names": {str(a.pk): a.name for a in targets + others},
        }
        return render(request, self.template_name, ctx)

    def get(self, request, pk, step=1):
        if (r := self.setup_ctx(request, pk, step)) is not None:
            return r
        missing = self.missing_step()
        if missing and step > missing:
            return redirect("declaration", pk=pk, step=missing)
        return self.render_step(request, step, self.make_form(step))

    def post(self, request, pk, step=1):
        if (r := self.setup_ctx(request, pk, step)) is not None:
            return r
        if request.POST.get("back"):
            return redirect("declaration", pk=pk, step=step - 1) if step > 1 else redirect("programme_home", pk=pk)
        missing = self.missing_step()
        if missing and step > missing:
            return redirect("declaration", pk=pk, step=missing)
        if step < STEPS:
            form = self.make_form(step, request.POST)
            if not form.is_valid():
                return self.render_step(request, step, form)
            if step == 3:
                self.draft.update(form.to_draft())
            else:
                self.draft.update(form.cleaned_data)
                if step == 1:
                    # Αλλαγή νέων ακυρώνει φύλο/ηλικία που αθροίζονταν στον παλιό αριθμό.
                    sex = self.draft.get("sex")
                    if sex is not None and sum(sex) != self.draft["new"]:
                        self.draft["sex"] = None
                    ages = self.draft.get("ages")
                    if ages is not None and sum(ages.values()) != self.draft["new"]:
                        self.draft["ages"] = None
            request.session[self.key] = self.draft
            return redirect("declaration", pk=pk, step=step + 1)
        return self.submit(request)

    def submit(self, request):
        d = self.draft
        # Επανέλεγχος όλων στον server: το πρόχειρο μπορεί να είναι παλιό.
        if d["completed"] + d["withdrawn"] > d["open_start"] + d["new"]:
            return redirect("declaration", pk=self.p.pk, step=2)
        sex = d.get("sex")
        fields = dict(
            open_start=d["open_start"], new=d["new"], completed=d["completed"], withdrawn=d["withdrawn"],
            sex_male=sex[0] if sex else None, sex_female=sex[1] if sex else None, sex_other=sex[2] if sex else None,
            ages=d.get("ages"), note=d.get("note", ""), submitted_by=request.user,
        )
        try:
            with transaction.atomic():
                if self.existing:
                    for k, v in fields.items():
                        setattr(self.existing, k, v)
                    self.existing.revisions += 1
                    self.existing.save()
                else:
                    seconds = None
                    try:
                        seconds = int((timezone.now() - datetime.fromisoformat(d["started"])).total_seconds())
                    except (KeyError, ValueError):
                        pass
                    if seconds is not None and not 0 <= seconds <= DRAFT_TTL_SECONDS:
                        seconds = None
                    Declaration.objects.create(programme=self.p, period=self.period, fill_seconds=seconds, **fields)
        except IntegrityError:
            # Δύο καρτέλες υπέβαλαν ταυτόχρονα. Η πρώτη κέρδισε.
            messages.info(request, "Η δήλωση είχε ήδη υποβληθεί. Ελέγξτε τα στοιχεία και διορθώστε αν χρειάζεται.")
            return redirect("programme_home", pk=self.p.pk)
        request.session.pop(self.key, None)
        messages.success(request, "Η δήλωση υποβλήθηκε. Η ΑΑΕΚ βλέπει πλέον τα νέα σύνολα.")
        return redirect("programme_home", pk=self.p.pk)


# ---------------------------------------------------------------- ΑΑΕΚ

SEX_LABELS = ["Αγόρια / άνδρες", "Κορίτσια / γυναίκες", "Άλλο / δεν δηλώθηκε"]


def sex_rows(shown):
    """Γραμμές για το γράφημα φύλου. Αν κάτι κρύφτηκε, δεν δείχνουμε ποσοστά (θα το αποκάλυπταν)."""
    if shown is None:
        return None
    total = sum(v for v in shown if v != HIDDEN)
    clean = HIDDEN not in shown and total > 0
    return [{"label": l, "v": v, "pct": round(v * 100 / total) if clean else None, "c": f"var(--c{i + 1})"}
            for i, (l, v) in enumerate(zip(SEX_LABELS, shown))]


def age_rows(breakdown, targets=()):
    if breakdown is None:
        return None
    top = max([v for _, v in breakdown if v != HIDDEN] + [1])
    return [{"label": a.name, "v": v, "w": 0 if v == HIDDEN else round(v * 100 / top),
             "outside": bool(targets) and a.pk not in targets} for a, v in breakdown]


def _cell(v):
    """Προστασία από εκτέλεση τύπων στο Excel (CSV injection)."""
    v = "" if v is None else v
    return "'" + v if isinstance(v, str) and v[:1] in ("=", "+", "-", "@") else v


def _int(params, name):
    v = params.get(name, "").strip()
    return int(v) if v.isdigit() else None


class AaekDashboardView(AaekRequiredMixin, TemplateView):
    template_name = "core/aaek_dashboard.html"

    def filters(self):
        g = self.request.GET
        periods = Period.recent(3)
        if (pid := _int(g, "per")) is not None:
            extra = Period.objects.filter(pk=pid).first()
            if extra and extra not in periods:
                periods = sorted(periods + [extra], key=lambda x: x.key)
        period = next((x for x in periods if x.pk == pid), periods[-1])
        district = _int(g, "dist")
        level = g.get("lvl") if g.get("lvl") in PreventionLevel.values else ""
        return periods, period, district, level

    def programmes(self, district, level):
        qs = Programme.objects.select_related("organisation", "district", "setting", "officer").prefetch_related("age_groups")
        qs = qs.filter(level__in=DECLARABLE_LEVELS)
        if district:
            qs = qs.filter(district_id=district)
        if level:
            qs = qs.filter(level=level)
        return list(qs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        periods, period, district, level = self.filters()
        progs = self.programmes(district, level)
        decl = {}
        for d in Declaration.objects.filter(programme__in=progs, period__in=periods).select_related("period"):
            decl.setdefault(d.period_id, {})[d.programme_id] = d
        # Ανενεργά προγράμματα χωρίς δήλωση δεν εμφανίζονται.
        progs = [p for p in progs if p.is_active or any(p.pk in v for v in decl.values())]
        cur = decl.get(period.pk, {})
        T = totals(progs, period, cur)
        rows = []
        for p in progs:
            if not (p.expected_in(period) or p.pk in cur):
                continue
            rows.append({"p": p, "d": cur.get(p.pk)})
        sel = _int(self.request.GET, "sel")
        detail = None
        age_groups = list(AgeGroup.objects.all())
        if sel and (sp := next((r["p"] for r in rows if r["p"].pk == sel), None)):
            sd = cur.get(sp.pk)
            detail = {
                "p": sp,
                "history": [{"period": per, "d": decl.get(per.pk, {}).get(sp.pk)} for per in periods],
                "d": sd,
                "sex": sex_rows(suppress(sd.sex)) if sd else None,
                "ages": age_rows(age_breakdown(age_groups, sd.ages), [a.pk for a in sp.age_groups.all()]) if sd else None,
            }
        trend = []
        for per in periods:
            t = totals(progs, per, decl.get(per.pk, {}))
            trend.append({"period": per, "t": t})
        ctx.update(
            periods=periods, period=period, district=district, level=level,
            districts=District.objects.all(), levels=[(v, l) for v, l in PreventionLevel.choices if v in DECLARABLE_LEVELS],
            T=T, rows=rows, detail=detail, sel=sel,
            sex=sex_rows(suppress(T.sex)) if T.sex_reported else None,
            ages=age_rows(age_breakdown(age_groups, T.ages)) if T.ages_reported else None,
            trend=self.trend_chart(trend, T.expected),
            rates=sorted(
                [{"name": r["p"].title, "v": r["d"].completion_rate} for r in rows if r["d"] and r["d"].completion_rate is not None],
                key=lambda x: -x["v"],
            ),
            comments=[r for r in rows if r["d"] and r["d"].note],
            HIDDEN=HIDDEN,
            query=self.request.GET.urlencode(),
        )
        return ctx

    @staticmethod
    def trend_chart(trend, expected):
        """Ομαδοποιημένες στήλες (SVG): εξυπηρετήθηκαν / ολοκλήρωσαν / αποχώρησαν ανά τετραμηνία."""
        W, H, L, R, T, B = 360, 246, 44, 8, 16, 56
        top = max([1] + [x["t"].served for x in trend])
        mag = 10 ** (len(str(top)) - 1)
        nice = next(m * mag for m in (1, 2, 5, 10) if m * mag >= top)
        gw = (W - L - R) / max(1, len(trend))
        bw = gw / 4.2

        def y(v):
            return T + (H - T - B) * (1 - v / nice)

        def n(v):
            # Κείμενο με τελεία: τα ελληνικά θα έγραφαν «190,0» και το SVG χαλάει.
            return f"{v:.1f}"

        series = [("Εξυπηρετήθηκαν", "var(--c1)", "served"), ("Ολοκλήρωσαν", "var(--c4)", "completed"), ("Αποχώρησαν", "var(--c2)", "withdrawn")]
        grid = [{"y": n(y(v)), "ty": n(y(v) + 4), "label": f"{int(v):,}".replace(",", ".")} for v in (0, nice / 2, nice)]
        groups = []
        for i, x in enumerate(trend):
            x0 = L + i * gw + gw / 2 - bw * 1.5
            bars = []
            for k, (name, color, attr) in enumerate(series):
                v = getattr(x["t"], attr)
                bars.append({"x": n(x0 + k * bw), "y": n(y(v)), "w": n(bw - 3),
                             "h": n(max(0, y(0) - y(v))), "color": color, "title": f"{name}: {v}"})
            groups.append({"cx": n(L + i * gw + gw / 2), "period": x["period"], "bars": bars,
                           "n": x["t"].submitted, "of": x["t"].expected})
        return {"W": W, "H": H, "L": L, "R": R, "x2": W - R, "grid": grid, "groups": groups, "series": series,
                "label_y": H - B + 18, "label_y2": H - B + 34,
                "incomplete": any(g["n"] < g["of"] for g in groups)}


class AaekExportView(AaekDashboardView):
    """CSV για Excel/Power BI. Ίδια απόκρυψη με την οθόνη."""

    def get(self, request, *args, **kwargs):
        periods, period, district, level = self.filters()
        progs = [p for p in self.programmes(district, level)]
        decl = {d.programme_id: d for d in Declaration.objects.filter(programme__in=progs, period=period)}
        age_groups = list(AgeGroup.objects.all())
        resp = HttpResponse(content_type="text/csv; charset=utf-8")
        resp["Content-Disposition"] = f'attachment; filename="atlas_{period.year}_{period.part}.csv"'
        resp.write("﻿")  # BOM: το Excel ανοίγει σωστά τα ελληνικά
        w = csv.writer(resp, delimiter=";")
        w.writerow(["Τετραμηνία", "Πρόγραμμα", "Φορέας", "Επίπεδο", "Επαρχία", "Πλαίσιο", "Υποβλήθηκε",
                    "Ανοικτές αρχής", "Νέοι", "Εξυπηρετήθηκαν", "Ολοκλήρωσαν", "Αποχώρησαν", "Ανοικτές τέλους",
                    "Ποσοστό ολοκλήρωσης %", "Αγόρια/άνδρες", "Κορίτσια/γυναίκες", "Άλλο"]
                   + [f"Ηλικία {a.name}" for a in age_groups])
        for p in progs:
            d = decl.get(p.pk)
            if not (p.expected_in(period) or d):
                continue
            base = [_cell(x) for x in (period.label, p.title, p.organisation.name, p.get_level_display(),
                                       p.district.name, p.setting.name)]
            if not d:
                w.writerow(base + ["Όχι"] + [""] * (10 + len(age_groups)))
                continue
            sex = suppress(d.sex) or ["", "", ""]
            ages = dict((str(a.pk), v) for a, v in (age_breakdown(age_groups, d.ages) or []))
            w.writerow(base + ["Ναι", d.open_start, d.new, d.served, d.completed, d.withdrawn, d.open_end,
                               "" if d.completion_rate is None else d.completion_rate] + sex
                       + [ages.get(str(a.pk), "") for a in age_groups])
        return resp
