from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from .access import OrganisationUserRequiredMixin, can_create_programme, can_edit_programme, visible_programmes
from .forms import ProgrammeForm
from .models import District, Organisation, PreventionLevel, Setting


def home(request):
    if not request.user.is_authenticated:
        return redirect("login")
    return redirect("programme_list")


class ProgrammeListView(LoginRequiredMixin, ListView):
    template_name = "core/programme_list.html"
    context_object_name = "programmes"

    def get_queryset(self):
        qs = visible_programmes(self.request.user).prefetch_related("districts", "settings")
        if self.request.user.is_aaek_user:
            g = self.request.GET
            if g.get("organisation"):
                qs = qs.filter(organisation_id=g["organisation"])
            if g.get("level"):
                qs = qs.filter(level=g["level"])
            if g.get("district"):
                qs = qs.filter(districts__id=g["district"])
            if g.get("setting"):
                qs = qs.filter(settings__id=g["setting"])
            qs = qs.distinct()
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["can_create"] = can_create_programme(self.request.user)
        if self.request.user.is_aaek_user:
            ctx["filters"] = {
                "organisations": Organisation.objects.filter(is_active=True),
                "levels": PreventionLevel.choices,
                "districts": District.objects.all(),
                "settings": Setting.objects.all(),
                "current": self.request.GET,
            }
        return ctx


class ProgrammeDetailView(LoginRequiredMixin, DetailView):
    template_name = "core/programme_detail.html"
    context_object_name = "programme"

    def get_queryset(self):
        # Πρόγραμμα άλλου φορέα → 404, ώστε να μη φαίνεται καν ότι υπάρχει.
        return visible_programmes(self.request.user).prefetch_related("districts", "settings", "vulnerable_groups")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["can_edit"] = can_edit_programme(self.request.user, self.object)
        return ctx


class ProgrammeCreateView(OrganisationUserRequiredMixin, CreateView):
    form_class = ProgrammeForm
    template_name = "core/programme_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["organisation"] = self.request.user.organisation
        return kwargs

    def form_valid(self, form):
        form.instance.organisation = self.request.user.organisation
        form.instance.created_by = self.request.user
        messages.success(self.request, "Το προφίλ του προγράμματος αποθηκεύτηκε.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("programme_detail", args=[self.object.pk])


class ProgrammeUpdateView(OrganisationUserRequiredMixin, UpdateView):
    form_class = ProgrammeForm
    template_name = "core/programme_form.html"

    def get_queryset(self):
        return visible_programmes(self.request.user)

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        if not can_edit_programme(self.request.user, obj):
            raise PermissionDenied
        return obj

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["organisation"] = self.request.user.organisation
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, "Οι αλλαγές αποθηκεύτηκαν.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("programme_detail", args=[self.object.pk])
