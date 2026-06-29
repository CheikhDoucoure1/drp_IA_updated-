from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.conf import settings
from django.contrib.auth import logout
from django.contrib.auth.views import LoginView
from django.db import transaction
from django.db.models import Count
from django.http import Http404, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    TemplateView,
    UpdateView,
)
from django_ratelimit.decorators import ratelimit

from drp.emailing import send_invitation_email, send_non_selection_email, send_relance_email, send_selection_email
from drp.forms import (
    BuyerLoginForm,
    DRPChangeStatutForm,
    DRPCreateForm,
    DomaineForm,
    DRPForm,
    ExpressionBesoinForm,
    FactureForm,
    FournisseurForm,
    ProformaResponseForm,
    SelectWinnerForm,
)
from drp.mixins import ResponsableAchatRequiredMixin, user_is_responsable_achat
from drp.models import Domaine, DRP, ExpressionBesoin, Facture, Fournisseur, Invitation, Proforma
from drp.services.analyse import analyser_fournisseur_complet, analyser_proforma_pdf, generer_analyse_ia
from drp.services.classement import classement_proformas


def buyer_drp_queryset(user):
    qs = DRP.objects.all()
    if not user.is_superuser:
        qs = qs.filter(created_by=user)
    return qs


class AccueilView(View):
    """Page d'accueil globale — redirige les utilisateurs connectés vers leur espace."""

    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            if request.user.is_superuser:
                return redirect("/admin/")
            if user_is_responsable_achat(request.user):
                return redirect("drp:dashboard")
            return redirect("drp:portail_user")
        return render(request, "drp/accueil.html")


class PortailUserView(View):
    """Portail utilisateur : connexion + formulaire d'expression de besoin."""

    template_name = "drp/portail_user.html"

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, self._context(request))

    def post(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.http import HttpResponseForbidden
            return HttpResponseForbidden()
        form = ExpressionBesoinForm(request.POST)
        if form.is_valid():
            eb = form.save(commit=False)
            eb.created_by = request.user
            eb.save()
            messages.success(request, f"Votre expression de besoin {eb.reference} a été soumise avec succès.")
            return redirect("drp:portail_user")
        ctx = self._context(request)
        ctx["eb_form"] = form
        return render(request, self.template_name, ctx)

    def _context(self, request):
        ctx = {"login_form": BuyerLoginForm()}
        if request.user.is_authenticated:
            ctx["eb_form"] = ExpressionBesoinForm()
            ctx["mes_besoins"] = (
                ExpressionBesoin.objects.filter(created_by=request.user)
                .select_related("domaine")
                .order_by("-created_at")[:5]
            )
        return ctx


class BuyerLoginView(LoginView):
    """Ne redirige vers le tableau de bord que si l'utilisateur a accès acheteur (évite boucle login ↔ 403)."""

    template_name = "drp/login.html"
    form_class = BuyerLoginForm
    redirect_authenticated_user = False

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and user_is_responsable_achat(request.user):
            return HttpResponseRedirect(self.get_success_url())
        return super().dispatch(request, *args, **kwargs)


class BuyerLogoutView(View):
    """GET : page de confirmation ; POST : déconnexion (évite 405 sur /logout/ en navigation directe)."""

    def get(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(settings.LOGIN_URL)
        return render(request, "drp/logout_confirm.html")

    def post(self, request, *args, **kwargs):
        logout(request)
        return redirect(settings.LOGOUT_REDIRECT_URL)


class DomaineListView(LoginRequiredMixin, ResponsableAchatRequiredMixin, ListView):
    model = Domaine
    template_name = "drp/domaine_list.html"
    context_object_name = "domaines"
    queryset = Domaine.objects.all().order_by("nom")


@method_decorator(ratelimit(key="user", rate="60/h", method="POST"), name="post")
class DomaineCreateView(LoginRequiredMixin, ResponsableAchatRequiredMixin, CreateView):
    model = Domaine
    form_class = DomaineForm
    template_name = "drp/domaine_form.html"
    success_url = reverse_lazy("drp:domaine_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_heading"] = "Créer un domaine"
        ctx["submit_label"] = "Créer"
        return ctx

    def form_valid(self, form):
        messages.success(self.request, f"Domaine « {form.instance.nom} » créé.")
        return super().form_valid(form)


@method_decorator(ratelimit(key="user", rate="60/h", method="POST"), name="post")
class DomaineUpdateView(LoginRequiredMixin, ResponsableAchatRequiredMixin, UpdateView):
    model = Domaine
    form_class = DomaineForm
    template_name = "drp/domaine_form.html"
    success_url = reverse_lazy("drp:domaine_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_heading"] = "Modifier le domaine"
        ctx["submit_label"] = "Enregistrer"
        return ctx

    def form_valid(self, form):
        messages.success(self.request, f"Domaine « {form.instance.nom} » mis à jour.")
        return super().form_valid(form)


class DomaineDeleteView(LoginRequiredMixin, ResponsableAchatRequiredMixin, DeleteView):
    model = Domaine
    template_name = "drp/domaine_confirm_delete.html"
    success_url = reverse_lazy("drp:domaine_list")
    context_object_name = "domaine"

    def delete(self, request, *args, **kwargs):
        nom = str(self.get_object())
        result = super().delete(request, *args, **kwargs)
        messages.success(request, f"Le domaine « {nom} » a été supprimé.")
        return result


class FournisseurListView(LoginRequiredMixin, ResponsableAchatRequiredMixin, ListView):
    model = Fournisseur
    template_name = "drp/fournisseur_list.html"
    context_object_name = "fournisseurs"
    queryset = Fournisseur.objects.order_by("nom").prefetch_related("domaines")


@method_decorator(ratelimit(key="user", rate="60/h", method="POST"), name="post")
class FournisseurCreateView(LoginRequiredMixin, ResponsableAchatRequiredMixin, CreateView):
    model = Fournisseur
    form_class = FournisseurForm
    template_name = "drp/fournisseur_form.html"
    success_url = reverse_lazy("drp:fournisseur_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_heading"] = "Nouveau fournisseur"
        ctx["submit_label"] = "Créer"
        return ctx

    def form_valid(self, form):
        messages.success(self.request, f"Fournisseur « {form.instance.nom} » créé.")
        return super().form_valid(form)


@method_decorator(ratelimit(key="user", rate="60/h", method="POST"), name="post")
class FournisseurUpdateView(LoginRequiredMixin, ResponsableAchatRequiredMixin, UpdateView):
    model = Fournisseur
    form_class = FournisseurForm
    template_name = "drp/fournisseur_form.html"
    success_url = reverse_lazy("drp:fournisseur_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_heading"] = "Modifier le fournisseur"
        ctx["submit_label"] = "Enregistrer"
        return ctx

    def form_valid(self, form):
        messages.success(self.request, f"Fournisseur « {form.instance.nom} » mis à jour.")
        return super().form_valid(form)


@method_decorator(ratelimit(key="user", rate="60/h", method="POST"), name="post")
class FournisseurDesactiverView(LoginRequiredMixin, ResponsableAchatRequiredMixin, DetailView):
    """Désactive le fournisseur (plus d’invitations futures) sans supprimer l’historique."""

    model = Fournisseur
    template_name = "drp/fournisseur_confirm_desactiver.html"
    context_object_name = "fournisseur"

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not self.object.actif:
            messages.info(request, "Ce fournisseur est déjà désactivé.")
            return redirect("drp:fournisseur_list")
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not self.object.actif:
            messages.info(request, "Ce fournisseur est déjà désactivé.")
            return redirect("drp:fournisseur_list")
        nom = str(self.object)
        self.object.actif = False
        self.object.save(update_fields=["actif"])
        messages.success(
            request,
            f"Le fournisseur « {nom} » a été désactivé. Les invitations et proformas restent consultables sur les DRP concernés.",
        )
        return redirect("drp:fournisseur_list")


class DashboardView(LoginRequiredMixin, ResponsableAchatRequiredMixin, TemplateView):
    template_name = "drp/dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        base_qs = buyer_drp_queryset(self.request.user)
        ctx["total_drp"] = base_qs.count()
        ctx["drp_en_cours"] = base_qs.filter(statut=DRP.Statut.EN_COURS).count()
        ctx["drp_cloturees"] = base_qs.filter(statut=DRP.Statut.CLOTUREE).count()
        ctx["drp_annulees"] = base_qs.filter(statut=DRP.Statut.ANNULEE).count()

        statut = self.request.GET.get("statut", "")
        valid_statuts = {choice.value for choice in DRP.Statut}
        if statut in valid_statuts:
            ctx["filtre_statut"] = statut
            list_qs = base_qs.filter(statut=statut)
        else:
            ctx["filtre_statut"] = ""
            list_qs = base_qs

        ctx["drps"] = list_qs.annotate(nb_offres=Count("invitations__proforma")).order_by("-created_at")[:50]
        return ctx


@method_decorator(ratelimit(key="user", rate="30/h", method="POST"), name="post")
class DRPCreateView(LoginRequiredMixin, ResponsableAchatRequiredMixin, CreateView):
    model = DRP
    form_class = DRPCreateForm
    template_name = "drp/drp_form.html"

    def get_initial(self):
        initial = super().get_initial()
        titre = self.request.GET.get("titre", "").strip()
        description = self.request.GET.get("description", "").strip()
        if titre:
            initial["titre"] = titre
        if description:
            initial["description"] = description
        return initial

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.setdefault("form_title", "Créer une DRP")
        ctx.setdefault("page_title", "Nouvelle DRP")
        ctx.setdefault("submit_label", "Enregistrer et inviter")
        ctx["cancel_href"] = reverse("drp:dashboard")
        ctx["is_create"] = True
        from django.db.models import Prefetch
        ctx["domaines_fournisseurs"] = (
            Domaine.objects.prefetch_related(
                Prefetch("fournisseurs", queryset=Fournisseur.objects.filter(actif=True).order_by("nom"))
            ).filter(fournisseurs__actif=True).distinct().order_by("nom")
        )
        return ctx

    def form_valid(self, form):
        fournisseurs = form.cleaned_data.get("fournisseurs")

        with transaction.atomic():
            self.object = form.save(commit=False)
            self.object.created_by = self.request.user
            self.object.save()

            # Dériver les domaines depuis les fournisseurs sélectionnés
            domaine_ids = set()
            for f in fournisseurs:
                for d in f.domaines.all():
                    domaine_ids.add(d.pk)
            self.object.domaines.set(domaine_ids)

            expiration = self.object.date_cloture
            envoyes = 0
            for f in fournisseurs:
                inv, created = Invitation.objects.get_or_create(
                    fournisseur=f,
                    drp=self.object,
                    defaults={
                        "expiration": expiration,
                        "statut": Invitation.Statut.ENVOYEE,
                    },
                )
                if created:
                    try:
                        send_invitation_email(inv, self.request)
                        envoyes += 1
                    except Exception as exc:
                        messages.warning(
                            self.request,
                            f"L’invitation pour {f.nom} a été créée mais l’email n’a pas pu être envoyé ({exc}).",
                        )
            if envoyes:
                messages.success(
                    self.request,
                    f"DRP créée. {envoyes} invitation(s) envoyée(s) par email.",
                )
        return redirect("drp:dashboard")

    def form_invalid(self, form):
        import logging
        logging.getLogger(__name__).error("DRPCreateView form_invalid: %s", form.errors.as_json())
        messages.error(self.request, f"Erreur de validation : {form.errors.as_text()}")
        return super().form_invalid(form)


@method_decorator(ratelimit(key="user", rate="30/h", method="POST"), name="post")
class DRPUpdateView(LoginRequiredMixin, ResponsableAchatRequiredMixin, UpdateView):
    model = DRP
    form_class = DRPForm
    template_name = "drp/drp_form.html"
    context_object_name = "drp"

    def get_queryset(self):
        return buyer_drp_queryset(self.request.user).filter(statut=DRP.Statut.EN_COURS)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["form_title"] = "Modifier la DRP"
        ctx["page_title"] = "Modifier la DRP"
        ctx["submit_label"] = "Enregistrer les modifications"
        ctx["cancel_href"] = reverse("drp:drp_detail", kwargs={"pk": self.object.pk})
        return ctx

    def form_valid(self, form):
        with transaction.atomic():
            self.object = form.save()
            Invitation.objects.filter(drp=self.object).update(expiration=self.object.date_cloture)
        messages.success(self.request, "La DRP a été mise à jour.")
        return redirect("drp:drp_detail", pk=self.object.pk)


class DRPDetailView(LoginRequiredMixin, ResponsableAchatRequiredMixin, DetailView):
    model = DRP
    template_name = "drp/drp_detail.html"
    context_object_name = "drp"

    def get_queryset(self):
        return buyer_drp_queryset(self.request.user)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        drp = self.object
        invitations = (
            drp.invitations.select_related("fournisseur")
            .prefetch_related("proforma")
            .order_by("fournisseur__nom")
        )
        ctx["invitations"] = invitations
        proformas_qs = list(
            Proforma.objects.filter(invitation__drp=drp)
            .select_related("invitation", "invitation__fournisseur")
        )
        ctx["proformas_classement"] = classement_proformas(drp, proformas_qs)
        ctx["select_form"] = SelectWinnerForm(drp=drp)
        ctx["statut_form"] = DRPChangeStatutForm(drp=drp)
        ctx["limite_depassee"] = drp.est_limite_reponses_depassee()
        ctx["nb_en_attente"] = invitations.filter(statut=Invitation.Statut.ENVOYEE).count()
        return ctx

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        action = request.POST.get("action")

        if action == "change_statut":
            form = DRPChangeStatutForm(request.POST, drp=self.object)
            if form.is_valid():
                new_statut = form.cleaned_data["statut"]
                self.object.statut = new_statut
                update_fields = ["statut"]
                if new_statut == DRP.Statut.CLOTUREE:
                    # Clôture manuelle : pas de fournisseur retenu par ce flux
                    self.object.selected_invitation = None
                    update_fields.append("selected_invitation")
                elif new_statut in (DRP.Statut.EN_COURS, DRP.Statut.ANNULEE):
                    self.object.selected_invitation = None
                    update_fields.append("selected_invitation")
                self.object.save(update_fields=update_fields)
                messages.success(
                    request,
                    f"Statut mis à jour : « {self.object.get_statut_display()} ».",
                )
            else:
                err = next(iter(form.errors.values()), None)
                messages.error(
                    request,
                    err[0] if err else "Impossible de mettre à jour le statut.",
                )
            return redirect("drp:drp_detail", pk=self.object.pk)

        if action == "select_winner":
            if self.object.statut != DRP.Statut.EN_COURS:
                messages.error(request, "Impossible de retenir un fournisseur : la DRP n’est pas en cours.")
                return redirect("drp:drp_detail", pk=self.object.pk)
            form = SelectWinnerForm(request.POST, drp=self.object)
            if form.is_valid():
                inv = form.cleaned_data["invitation"]
                self.object.selected_invitation = inv
                self.object.statut = DRP.Statut.CLOTUREE
                self.object.save(update_fields=["selected_invitation", "statut"])
                messages.success(
                    request,
                    f"Fournisseur retenu : {inv.fournisseur.nom}. La DRP est clôturée.",
                )
                # Notifier le fournisseur retenu
                try:
                    send_selection_email(inv, request)
                except Exception as exc:
                    messages.warning(request, f"Notification non envoyée à {inv.fournisseur.nom} ({exc}).")
                # Notifier les autres fournisseurs ayant soumis une proforma
                autres = (
                    self.object.invitations
                    .filter(statut=Invitation.Statut.REPONDUE)
                    .exclude(pk=inv.pk)
                    .select_related("fournisseur")
                )
                for autre_inv in autres:
                    try:
                        send_non_selection_email(autre_inv, request)
                    except Exception as exc:
                        messages.warning(request, f"Notification non envoyée à {autre_inv.fournisseur.nom} ({exc}).")
            else:
                messages.error(request, "Choix invalide. Veuillez sélectionner une offre existante.")
            return redirect("drp:drp_detail", pk=self.object.pk)

        if action == "relancer":
            if self.object.statut != DRP.Statut.EN_COURS or self.object.est_limite_reponses_depassee():
                messages.error(request, "Impossible de relancer : la DRP n'est plus ouverte ou la date de clôture est dépassée.")
                return redirect("drp:drp_detail", pk=self.object.pk)
            en_attente = self.object.invitations.filter(statut=Invitation.Statut.ENVOYEE).select_related("fournisseur", "drp")
            if not en_attente.exists():
                messages.info(request, "Tous les fournisseurs ont déjà répondu ou sont expirés.")
                return redirect("drp:drp_detail", pk=self.object.pk)
            envoyes, echecs = 0, 0
            for inv in en_attente:
                try:
                    send_relance_email(inv, request)
                    envoyes += 1
                except Exception as exc:
                    echecs += 1
                    messages.warning(request, f"Relance non envoyée à {inv.fournisseur.nom} ({exc}).")
            if envoyes:
                messages.success(request, f"{envoyes} relance(s) envoyée(s) avec succès.")
            if echecs and not envoyes:
                messages.error(request, "Aucune relance n'a pu être envoyée.")
            return redirect("drp:drp_detail", pk=self.object.pk)

        messages.error(request, "Action non reconnue.")
        return redirect("drp:drp_detail", pk=self.object.pk)


class DRPDeleteView(LoginRequiredMixin, ResponsableAchatRequiredMixin, DeleteView):
    model = DRP
    template_name = "drp/drp_confirm_delete.html"
    success_url = reverse_lazy("drp:dashboard")
    context_object_name = "drp"

    def get_queryset(self):
        return buyer_drp_queryset(self.request.user).filter(
            statut__in=[DRP.Statut.EN_COURS, DRP.Statut.ANNULEE],
        )

    def delete(self, request, *args, **kwargs):
        messages.success(request, "La DRP a été supprimée.")
        return super().delete(request, *args, **kwargs)


@method_decorator(ratelimit(key="user", rate="30/h", method="POST"), name="post")
class FactureCreateView(LoginRequiredMixin, ResponsableAchatRequiredMixin, View):
    """Saisie de la facture réelle pour un fournisseur retenu sur une DRP clôturée."""

    template_name = "drp/facture_form.html"

    def _get_invitation(self, drp_pk):
        drp = get_object_or_404(buyer_drp_queryset(self.request.user), pk=drp_pk)
        if drp.statut != DRP.Statut.CLOTUREE or not drp.selected_invitation:
            raise Http404
        return drp.selected_invitation

    def get(self, request, drp_pk, *args, **kwargs):
        invitation = self._get_invitation(drp_pk)
        try:
            facture_existante = invitation.facture
        except Facture.DoesNotExist:
            facture_existante = None
        form = FactureForm(instance=facture_existante)
        return render(request, self.template_name, {
            "form": form,
            "invitation": invitation,
            "drp": invitation.drp,
            "facture_existante": facture_existante,
        })

    def post(self, request, drp_pk, *args, **kwargs):
        invitation = self._get_invitation(drp_pk)
        try:
            instance = invitation.facture
        except Facture.DoesNotExist:
            instance = None
        form = FactureForm(request.POST, instance=instance)
        if form.is_valid():
            facture = form.save(commit=False)
            facture.invitation = invitation
            facture.created_by = request.user
            facture.save()
            messages.success(request, "Facture enregistrée avec succès.")
            return redirect("drp:drp_detail", pk=invitation.drp_id)
        return render(request, self.template_name, {
            "form": form,
            "invitation": invitation,
            "drp": invitation.drp,
            "facture_existante": instance,
        })


class AnalyseComparativeView(LoginRequiredMixin, ResponsableAchatRequiredMixin, TemplateView):
    """Page d'analyse IA des prix proforma par DRP."""

    template_name = "drp/analyse_comparative.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        drp_qs = buyer_drp_queryset(self.request.user)
        ctx["analyses"] = generer_analyse_ia(drp_qs)
        return ctx


@method_decorator(ratelimit(key="ip", rate="120/h"), name="get")
@method_decorator(ratelimit(key="ip", rate="40/h", method="POST"), name="post")
class SupplierProformaView(DetailView):
    model = Invitation
    template_name = "drp/supplier_proforma.html"
    context_object_name = "invitation"

    def get_object(self, queryset=None):
        token = self.kwargs.get("token")
        if token is None:
            raise Http404
        inv = get_object_or_404(
            Invitation.objects.select_related("drp", "fournisseur"),
            token=token,
        )
        if inv.est_expiree() and inv.statut == Invitation.Statut.ENVOYEE:
            Invitation.objects.filter(pk=inv.pk).update(statut=Invitation.Statut.EXPIREE)
            inv.statut = Invitation.Statut.EXPIREE
        return inv

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        inv = self.object
        readonly = (
            inv.drp.statut != DRP.Statut.EN_COURS
            or inv.statut != Invitation.Statut.ENVOYEE
            or inv.est_expiree()
        )
        ctx["readonly"] = readonly
        ctx["form"] = kwargs.get("form") or ProformaResponseForm()
        try:
            ctx["existing_proforma"] = inv.proforma
        except Proforma.DoesNotExist:
            ctx["existing_proforma"] = None
        return ctx

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        if (
            self.object.drp.statut != DRP.Statut.EN_COURS
            or self.object.statut != Invitation.Statut.ENVOYEE
            or self.object.est_expiree()
        ):
            messages.error(request, "Ce lien n’est plus valable ou a déjà été utilisé.")
            return self.get(request, *args, **kwargs)
        form = ProformaResponseForm(request.POST, request.FILES)
        if form.is_valid():
            proforma = form.save(commit=False)
            proforma.invitation = self.object
            try:
                # Mise à jour d'un proforma existant (cas de réactivation après resoumission)
                existing = self.object.proforma
                existing.prix = proforma.prix
                existing.delai_jours = proforma.delai_jours
                existing.commentaire = proforma.commentaire
                existing.fichier = proforma.fichier
                existing.save()
            except Proforma.DoesNotExist:
                proforma.save()
            Invitation.objects.filter(pk=self.object.pk).update(statut=Invitation.Statut.REPONDUE)
            messages.success(request, "Votre proforma a été enregistrée. Merci.")
            return redirect("drp:supplier_proforma", token=self.object.token)
        return self.render_to_response(self.get_context_data(form=form))


# ── Expressions de besoin ──────────────────────────────────────────────────────

class ExpressionBesoinListView(LoginRequiredMixin, ResponsableAchatRequiredMixin, ListView):
    model = ExpressionBesoin
    template_name = "drp/expression_besoin_list.html"
    context_object_name = "expressions"

    def get_queryset(self):
        qs = ExpressionBesoin.objects.select_related("domaine", "created_by", "drp")
        if not self.request.user.is_superuser:
            qs = qs.filter(created_by=self.request.user)
        statut = self.request.GET.get("statut", "")
        valid_statuts = {choice.value for choice in ExpressionBesoin.Statut}
        if statut in valid_statuts:
            qs = qs.filter(statut=statut)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["filtre_statut"] = self.request.GET.get("statut", "")
        ctx["Statut"] = ExpressionBesoin.Statut
        all_qs = ExpressionBesoin.objects.all()
        if not self.request.user.is_superuser:
            all_qs = all_qs.filter(created_by=self.request.user)
        ctx["total"] = all_qs.count()
        ctx["nb_en_attente"] = all_qs.filter(statut=ExpressionBesoin.Statut.EN_ATTENTE).count()
        ctx["nb_approuvees"] = all_qs.filter(statut=ExpressionBesoin.Statut.APPROUVEE).count()
        ctx["nb_rejetees"] = all_qs.filter(statut=ExpressionBesoin.Statut.REJETEE).count()
        ctx["nb_converties"] = all_qs.filter(statut=ExpressionBesoin.Statut.CONVERTIE).count()
        return ctx


@method_decorator(ratelimit(key="user", rate="60/h", method="POST"), name="post")
class ExpressionBesoinCreateView(LoginRequiredMixin, ResponsableAchatRequiredMixin, CreateView):
    model = ExpressionBesoin
    form_class = ExpressionBesoinForm
    template_name = "drp/expression_besoin_form.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["form_title"] = "Exprimer un besoin"
        ctx["submit_label"] = "Soumettre le besoin"
        ctx["cancel_href"] = reverse("drp:besoin_list")
        return ctx

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        eb = form.save()
        messages.success(self.request, f"Expression de besoin {eb.reference} soumise avec succès.")
        return redirect("drp:besoin_detail", pk=eb.pk)


@method_decorator(ratelimit(key="user", rate="60/h", method="POST"), name="post")
class ExpressionBesoinUpdateView(LoginRequiredMixin, ResponsableAchatRequiredMixin, UpdateView):
    model = ExpressionBesoin
    form_class = ExpressionBesoinForm
    template_name = "drp/expression_besoin_form.html"

    def get_queryset(self):
        qs = ExpressionBesoin.objects.filter(statut=ExpressionBesoin.Statut.EN_ATTENTE)
        if not self.request.user.is_superuser:
            qs = qs.filter(created_by=self.request.user)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["form_title"] = "Modifier l'expression de besoin"
        ctx["submit_label"] = "Enregistrer les modifications"
        ctx["cancel_href"] = reverse("drp:besoin_detail", kwargs={"pk": self.object.pk})
        return ctx

    def form_valid(self, form):
        eb = form.save()
        messages.success(self.request, f"Expression de besoin {eb.reference} mise à jour.")
        return redirect("drp:besoin_detail", pk=eb.pk)


class ExpressionBesoinDetailView(LoginRequiredMixin, ResponsableAchatRequiredMixin, DetailView):
    model = ExpressionBesoin
    template_name = "drp/expression_besoin_detail.html"
    context_object_name = "eb"

    def get_queryset(self):
        qs = ExpressionBesoin.objects.select_related("domaine", "created_by", "drp")
        if not self.request.user.is_superuser:
            qs = qs.filter(created_by=self.request.user)
        return qs

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        action = request.POST.get("action")

        if action == "approuver":
            if self.object.statut != ExpressionBesoin.Statut.EN_ATTENTE:
                messages.error(request, "Seule une expression en attente peut être approuvée.")
            else:
                self.object.statut = ExpressionBesoin.Statut.APPROUVEE
                self.object.save(update_fields=["statut"])
                messages.success(request, f"{self.object.reference} approuvée.")

        elif action == "rejeter":
            if self.object.statut not in (ExpressionBesoin.Statut.EN_ATTENTE, ExpressionBesoin.Statut.APPROUVEE):
                messages.error(request, "Cette expression ne peut pas être rejetée.")
            else:
                self.object.statut = ExpressionBesoin.Statut.REJETEE
                self.object.save(update_fields=["statut"])
                messages.warning(request, f"{self.object.reference} rejetée.")

        elif action == "remettre_en_attente":
            if self.object.statut not in (ExpressionBesoin.Statut.APPROUVEE, ExpressionBesoin.Statut.REJETEE):
                messages.error(request, "Cette expression ne peut pas être remise en attente.")
            else:
                self.object.statut = ExpressionBesoin.Statut.EN_ATTENTE
                self.object.save(update_fields=["statut"])
                messages.info(request, f"{self.object.reference} remise en attente.")

        elif action == "convertir":
            if self.object.statut != ExpressionBesoin.Statut.APPROUVEE:
                messages.error(request, "Seule une expression approuvée peut être convertie en DRP.")
                return redirect("drp:besoin_detail", pk=self.object.pk)
            self.object.statut = ExpressionBesoin.Statut.CONVERTIE
            self.object.save(update_fields=["statut"])
            messages.success(request, f"{self.object.reference} marquée comme convertie. Complétez la DRP ci-dessous.")
            params = urlencode({
                "titre": self.object.produit,
                "description": (
                    f"Besoin exprimé par le domaine {self.object.domaine.nom}.\n\n"
                    f"{self.object.description}"
                ),
            })
            return redirect(f"{reverse('drp:drp_create')}?{params}")

        else:
            messages.error(request, "Action non reconnue.")

        return redirect("drp:besoin_detail", pk=self.object.pk)


class ExpressionBesoinDeleteView(LoginRequiredMixin, ResponsableAchatRequiredMixin, DeleteView):
    model = ExpressionBesoin
    template_name = "drp/expression_besoin_confirm_delete.html"
    success_url = reverse_lazy("drp:besoin_list")
    context_object_name = "eb"

    def get_queryset(self):
        qs = ExpressionBesoin.objects.filter(
            statut__in=[ExpressionBesoin.Statut.EN_ATTENTE, ExpressionBesoin.Statut.REJETEE]
        )
        if not self.request.user.is_superuser:
            qs = qs.filter(created_by=self.request.user)
        return qs

    def delete(self, request, *args, **kwargs):
        messages.success(request, "L'expression de besoin a été supprimée.")
        return super().delete(request, *args, **kwargs)


class AnalyserProformaPDFView(LoginRequiredMixin, ResponsableAchatRequiredMixin, View):
    """Analyse le PDF d'un proforma via Claude et retourne le résultat en JSON."""

    def get(self, request, pk):
        proforma = get_object_or_404(
            Proforma.objects.select_related(
                "invitation__fournisseur", "invitation__drp"
            ),
            pk=pk,
        )
        analyse = analyser_proforma_pdf(proforma)
        return JsonResponse({"analyse": analyse})


class AnalyserFournisseurIAView(LoginRequiredMixin, ResponsableAchatRequiredMixin, View):
    """Analyse complète IA d'un fournisseur (proforma + facture + contexte) — retourne JSON."""

    def get(self, request, pk):
        proforma = get_object_or_404(
            Proforma.objects.select_related(
                "invitation__fournisseur", "invitation__drp__created_by"
            ),
            pk=pk,
        )
        if not request.user.is_superuser and proforma.invitation.drp.created_by != request.user:
            from django.http import HttpResponseForbidden
            return HttpResponseForbidden()
        analyse = analyser_fournisseur_complet(proforma)
        return JsonResponse({"analyse": analyse})
