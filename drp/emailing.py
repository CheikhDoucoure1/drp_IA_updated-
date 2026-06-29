from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse


def build_supplier_link(invitation, request=None) -> str:
    path = reverse("drp:supplier_proforma", kwargs={"token": str(invitation.token)})
    if request is not None:
        return request.build_absolute_uri(path)
    return f"{settings.SITE_PUBLIC_URL}{path}"


def send_selection_email(invitation, request=None) -> None:
    """Notifie le fournisseur retenu."""
    subject = f"Résultat appel d'offres — {invitation.drp.titre}"
    body = (
        f"Bonjour,\n\n"
        f"Nous avons le plaisir de vous informer que votre offre a été retenue dans le cadre de "
        f"la demande de prix : {invitation.drp.titre}.\n\n"
        f"Notre équipe prendra contact avec vous prochainement pour la suite du processus.\n\n"
        f"Cordialement"
    )
    send_mail(
        subject=subject,
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[invitation.fournisseur.email],
        fail_silently=False,
    )


def send_non_selection_email(invitation, request=None) -> None:
    """Notifie un fournisseur non retenu."""
    subject = f"Résultat appel d'offres — {invitation.drp.titre}"
    body = (
        f"Bonjour,\n\n"
        f"Nous vous remercions d'avoir soumis votre offre dans le cadre de la demande de prix : "
        f"{invitation.drp.titre}.\n\n"
        f"Après examen des offres reçues, nous avons retenu un autre prestataire pour ce dossier. "
        f"Nous espérons pouvoir collaborer avec vous lors de prochaines consultations.\n\n"
        f"Cordialement"
    )
    send_mail(
        subject=subject,
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[invitation.fournisseur.email],
        fail_silently=False,
    )


def send_relance_email(invitation, request=None) -> None:
    """Envoie un email de relance à un fournisseur qui n'a pas encore répondu."""
    link = build_supplier_link(invitation, request)
    subject = f"[Relance] Demande de prix — {invitation.drp.titre}"
    body = (
        f"Bonjour,\n\n"
        f"Nous revenons vers vous concernant la demande de prix : {invitation.drp.titre}.\n\n"
        f"Nous n'avons pas encore reçu votre proforma. La date de clôture est fixée au "
        f"{invitation.drp.date_cloture:%d/%m/%Y %H:%M}.\n\n"
        f"Lien sécurisé pour soumettre votre offre :\n{link}\n\n"
        f"Merci de ne pas transférer ce lien.\n\n"
        f"Cordialement"
    )
    send_mail(
        subject=subject,
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[invitation.fournisseur.email],
        fail_silently=False,
    )


def send_reactivation_email(invitation, request=None) -> None:
    """Notifie le fournisseur que son lien a été réactivé par l'admin."""
    link = build_supplier_link(invitation, request)
    subject = f"[Réactivation] Demande de prix — {invitation.drp.titre}"
    body = (
        f"Bonjour,\n\n"
        f"Suite à une décision de notre équipe, votre lien de soumission de proforma pour la "
        f"demande de prix « {invitation.drp.titre} » a été réactivé.\n\n"
        f"Vous pouvez soumettre une nouvelle offre jusqu'au "
        f"{invitation.date_reactivation:%d/%m/%Y à %H:%M} via le lien ci-dessous :\n{link}\n\n"
        f"Merci de ne pas transférer ce lien.\n\n"
        f"Cordialement"
    )
    send_mail(
        subject=subject,
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[invitation.fournisseur.email],
        fail_silently=False,
    )


def send_invitation_email(invitation, request=None) -> None:
    """Envoie l’email d’invitation (texte brut, pas de HTML non fiable)."""
    link = build_supplier_link(invitation, request)
    subject = f"Demande de prix — {invitation.drp.titre}"
    body = (
        f"Bonjour,\n\n"
        f"Vous êtes invité(e) à répondre à une demande de prix (DRP) : {invitation.drp.titre}.\n\n"
        f"Lien sécurisé (unique, réponses attendues avant le {invitation.drp.date_cloture:%d/%m/%Y %H:%M}) :\n{link}\n\n"
        f"Merci de ne pas transférer ce lien.\n\n"
        f"Cordialement"
    )
    send_mail(
        subject=subject,
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[invitation.fournisseur.email],
        fail_silently=False,
    )
