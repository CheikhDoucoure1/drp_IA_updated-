from datetime import timedelta

from django.contrib import admin, messages
from django.utils import timezone

from drp.emailing import send_reactivation_email
from drp.models import Domaine, DRP, ExpressionBesoin, Fournisseur, Invitation, Proforma


@admin.register(ExpressionBesoin)
class ExpressionBesoinAdmin(admin.ModelAdmin):
    list_display = ("reference", "produit", "quantite", "unite", "domaine", "statut", "created_by", "created_at")
    list_filter = ("statut", "domaine")
    search_fields = ("reference", "produit")
    readonly_fields = ("reference", "created_at")


@admin.register(Domaine)
class DomaineAdmin(admin.ModelAdmin):
    search_fields = ("nom",)


@admin.register(Fournisseur)
class FournisseurAdmin(admin.ModelAdmin):
    list_display = ("nom", "email", "telephone", "actif")
    list_filter = ("actif",)
    search_fields = ("nom", "email")
    filter_horizontal = ("domaines",)


class InvitationInline(admin.TabularInline):
    model = Invitation
    extra = 0
    readonly_fields = ("token", "expiration", "statut", "fournisseur")
    can_delete = False


@admin.register(DRP)
class DRPAdmin(admin.ModelAdmin):
    list_display = ("titre", "statut", "date_cloture", "created_at", "created_by")
    list_filter = ("statut",)
    search_fields = ("titre",)
    readonly_fields = ("created_at", "selected_invitation")
    inlines = [InvitationInline]


@admin.action(description="Réactiver le lien de soumission (48 h)")
def reactiver_lien_proforma(modeladmin, request, queryset):
    nouvelle_expiration = timezone.now() + timedelta(hours=48)
    count = 0
    erreurs_email = 0

    for invitation in queryset.select_related("drp", "fournisseur"):
        # Supprimer le proforma existant pour permettre une nouvelle soumission
        try:
            invitation.proforma.delete()
        except Proforma.DoesNotExist:
            pass

        invitation.statut = Invitation.Statut.ENVOYEE
        invitation.date_reactivation = nouvelle_expiration
        invitation.save(update_fields=["statut", "date_reactivation"])

        try:
            send_reactivation_email(invitation, request)
        except Exception:
            erreurs_email += 1

        count += 1

    msg = (
        f"{count} lien(s) réactivé(s) jusqu'au {nouvelle_expiration:%d/%m/%Y à %H:%M}."
    )
    if erreurs_email:
        msg += f" ({erreurs_email} notification(s) email échouée(s).)"
    modeladmin.message_user(request, msg, messages.SUCCESS)


@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
    list_display = ("drp", "fournisseur", "statut", "expiration", "date_reactivation", "token")
    list_filter = ("statut",)
    readonly_fields = ("token",)
    actions = [reactiver_lien_proforma]


@admin.register(Proforma)
class ProformaAdmin(admin.ModelAdmin):
    list_display = ("invitation", "prix", "delai_jours", "submitted_at")
    readonly_fields = ("submitted_at",)
