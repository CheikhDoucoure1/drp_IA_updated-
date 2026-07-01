from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse


def send_expression_besoin_notification(eb, request=None) -> None:
    """Notifie le responsable du domaine qu'une expression des besoins a été soumise."""
    responsable = getattr(eb.domaine, "responsable", None)
    if not responsable or not responsable.email:
        return
    path = reverse("drp:besoin_detail", kwargs={"pk": eb.pk})
    link = request.build_absolute_uri(path) if request else f"{settings.SITE_PUBLIC_URL}{path}"
    submitter = (
        eb.created_by.get_full_name() or eb.created_by.get_username()
        if eb.created_by else "Inconnu"
    )
    destinataire = responsable.get_full_name() or responsable.get_username()
    body = (
        f"Bonjour {destinataire},\n\n"
        f"Une nouvelle expression des besoins a été soumise dans votre domaine : {eb.domaine.nom}.\n\n"
        f"Référence    : {eb.reference}\n"
        f"Produit      : {eb.produit}\n"
        f"Quantité     : {eb.quantite} {eb.unite}\n"
        f"Soumis par   : {submitter}\n\n"
        f"Consultez la demande ici :\n{link}\n\n"
        f"Cordialement,\nSystème DRP Petrosen"
    )
    send_mail(
        subject=f"[DRP] Nouvelle expression des besoins — {eb.domaine.nom}",
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[responsable.email],
        fail_silently=True,
    )


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


def send_eb_rejetee_par_admin(eb, request=None) -> None:
    """Notifie le demandeur que sa demande a été rejetée par l'admin domaine."""
    if not eb.created_by or not eb.created_by.email:
        return
    path = reverse("drp:portail_user")
    link = request.build_absolute_uri(path) if request else f"{settings.SITE_PUBLIC_URL}{path}"
    destinataire = eb.created_by.get_full_name() or eb.created_by.get_username()
    body = (
        f"Bonjour {destinataire},\n\n"
        f"Votre expression des besoins {eb.reference} ({eb.produit}) a été rejetée "
        f"par le responsable du domaine {eb.domaine.nom}.\n\n"
        f"Vous pouvez soumettre une nouvelle demande via le portail :\n{link}\n\n"
        f"Cordialement,\nSystème DRP Petrosen"
    )
    send_mail(
        subject=f"[DRP] Expression des besoins {eb.reference} rejetée",
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[eb.created_by.email],
        fail_silently=True,
    )


def send_proposition_dg(eb, proposition, request=None) -> None:
    """Notifie tous les superusers (DG) qu'une proposition attend leur décision."""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    dg_emails = list(
        User.objects.filter(is_superuser=True, email__isnull=False)
        .exclude(email="")
        .values_list("email", flat=True)
    )
    if not dg_emails:
        return
    path = reverse("drp:besoin_detail", kwargs={"pk": eb.pk})
    link = request.build_absolute_uri(path) if request else f"{settings.SITE_PUBLIC_URL}{path}"
    soumis_par = proposition.soumis_par
    admin_nom = soumis_par.get_full_name() or soumis_par.get_username() if soumis_par else "Admin"
    fournisseurs_liste = "\n".join(
        f"  - {f.nom} ({f.email})" for f in proposition.fournisseurs.all()
    )
    body = (
        f"Bonjour,\n\n"
        f"L'administrateur du domaine « {eb.domaine.nom} » ({admin_nom}) a soumis une proposition "
        f"de fournisseurs pour l'expression des besoins {eb.reference}.\n\n"
        f"Produit     : {eb.produit}\n"
        f"Quantité    : {eb.quantite} {eb.unite}\n"
        f"Demandeur   : {eb.created_by.get_full_name() or eb.created_by.get_username() if eb.created_by else '—'}\n\n"
        f"Fournisseurs proposés :\n{fournisseurs_liste}\n\n"
        f"{'Commentaire : ' + proposition.commentaire if proposition.commentaire else ''}\n\n"
        f"Consultez et prenez une décision ici :\n{link}\n\n"
        f"Cordialement,\nSystème DRP Petrosen"
    )
    send_mail(
        subject=f"[DRP] Proposition en attente — {eb.reference} ({eb.domaine.nom})",
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=dg_emails,
        fail_silently=True,
    )


def send_decision_dg(eb, approuve: bool, motif: str = "", request=None) -> None:
    """Notifie l'admin domaine et le demandeur de la décision du DG."""
    destinataires = []
    if eb.domaine.responsable and eb.domaine.responsable.email:
        destinataires.append(eb.domaine.responsable.email)
    if eb.created_by and eb.created_by.email:
        destinataires.append(eb.created_by.email)
    if not destinataires:
        return
    path = reverse("drp:besoin_detail", kwargs={"pk": eb.pk})
    link = request.build_absolute_uri(path) if request else f"{settings.SITE_PUBLIC_URL}{path}"
    if approuve:
        sujet = f"[DRP] Expression des besoins {eb.reference} approuvée par le DG"
        decision = "approuvée"
        complement = "La demande va maintenant être traitée conformément au processus DRP."
    else:
        sujet = f"[DRP] Expression des besoins {eb.reference} rejetée par le DG"
        decision = "rejetée"
        complement = f"Motif : {motif}" if motif else ""
    body = (
        f"Bonjour,\n\n"
        f"Le Directeur Général a {decision} l'expression des besoins {eb.reference} ({eb.produit}).\n\n"
        f"{complement}\n\n"
        f"Consulter la demande :\n{link}\n\n"
        f"Cordialement,\nSystème DRP Petrosen"
    )
    send_mail(
        subject=sujet,
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=list(set(destinataires)),
        fail_silently=True,
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
