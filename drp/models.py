import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import FileExtensionValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class Domaine(models.Model):
    nom = models.CharField(max_length=200, unique=True)
    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="domaines_responsable",
        verbose_name="Responsable",
    )

    class Meta:
        ordering = ["nom"]
        verbose_name = "Domaine"
        verbose_name_plural = "Domaines"

    def __str__(self) -> str:
        return self.nom


class Fournisseur(models.Model):
    nom = models.CharField(max_length=255)
    email = models.EmailField()
    telephone = models.CharField(max_length=40, blank=True)
    actif = models.BooleanField(default=True)
    domaines = models.ManyToManyField(Domaine, related_name="fournisseurs", blank=True)

    class Meta:
        ordering = ["nom"]
        verbose_name = "Fournisseur"
        verbose_name_plural = "Fournisseurs"

    def __str__(self) -> str:
        return self.nom


class DRP(models.Model):
    class Statut(models.TextChoices):
        EN_COURS = "en_cours", "En cours"
        CLOTUREE = "cloturee", "Clôturée"
        ANNULEE = "annulee", "Annulée"

    titre = models.CharField(max_length=300)
    description = models.TextField()
    fichier = models.FileField(
        upload_to="drp/pieces/",
        blank=True,
        null=True,
        validators=[FileExtensionValidator(["pdf"])],
    )
    domaines = models.ManyToManyField(Domaine, related_name="drps")
    statut = models.CharField(
        max_length=20,
        choices=Statut.choices,
        default=Statut.EN_COURS,
    )
    poids_prix = models.PositiveSmallIntegerField(
        default=50,
        validators=[MinValueValidator(1)],
        help_text="Pondération du critère prix (1–100).",
    )
    poids_delai = models.PositiveSmallIntegerField(
        default=50,
        validators=[MinValueValidator(1)],
        help_text="Pondération du critère délai (1–100).",
    )
    budget_previsionnel = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.01"))],
        verbose_name="Budget prévisionnel (FCFA)",
    )
    date_cloture = models.DateTimeField(
        verbose_name="Date de clôture",
        help_text="Les fournisseurs ne peuvent plus soumettre de proforma après cette date.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="drps_creees",
    )
    selected_invitation = models.ForeignKey(
        "Invitation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="drps_retenues",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "DRP"
        verbose_name_plural = "DRP"

    def __str__(self) -> str:
        return self.titre

    def est_limite_reponses_depassee(self) -> bool:
        return timezone.now() > self.date_cloture


class Invitation(models.Model):
    class Statut(models.TextChoices):
        ENVOYEE = "envoyee", "Envoyée"
        REPONDUE = "repondue", "Répondue"
        EXPIREE = "expiree", "Expirée"

    fournisseur = models.ForeignKey(
        Fournisseur,
        on_delete=models.PROTECT,
        related_name="invitations",
    )
    drp = models.ForeignKey(DRP, on_delete=models.CASCADE, related_name="invitations")
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    expiration = models.DateTimeField()
    date_reactivation = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Réactivé jusqu'au",
        help_text="Si renseigné, le lien reste valide jusqu'à cette date même après la clôture du DRP.",
        
    )
    statut = models.CharField(
        max_length=20,
        choices=Statut.choices,
        default=Statut.ENVOYEE,
    )

    class Meta:
        ordering = ["drp", "fournisseur"]
        verbose_name = "Invitation"
        verbose_name_plural = "Invitations"
        constraints = [
            models.UniqueConstraint(fields=["fournisseur", "drp"], name="unique_invitation_fournisseur_drp"),
        ]

    def __str__(self) -> str:
        return f"{self.fournisseur} → {self.drp}"

    def est_expiree(self) -> bool:
        if self.date_reactivation and timezone.now() <= self.date_reactivation:
            return False
        return self.drp.est_limite_reponses_depassee()


class Proforma(models.Model):
    invitation = models.OneToOneField(
        Invitation,
        on_delete=models.CASCADE,
        related_name="proforma",
    )
    prix = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    delai_jours = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    commentaire = models.TextField(blank=True)
    fichier = models.FileField(
        upload_to="proformas/",
        validators=[FileExtensionValidator(["pdf"])],
    )
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Proforma"
        verbose_name_plural = "Proformas"

    def __str__(self) -> str:
        return f"Proforma {self.invitation.fournisseur} ({self.prix} FCFA)"


class ExpressionBesoin(models.Model):
    class Statut(models.TextChoices):
        EN_ATTENTE = "en_attente", "En attente"
        EN_ATTENTE_DG = "en_attente_dg", "En attente approbation DG"
        APPROUVEE = "approuvee", "Approuvée"
        REJETEE = "rejetee", "Rejetée"
        CONVERTIE = "convertie", "Convertie en DRP"

    reference = models.CharField(max_length=30, unique=True, editable=False, verbose_name="Référence")
    produit = models.CharField(max_length=300, verbose_name="Produit / Service")
    quantite = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        verbose_name="Quantité",
    )
    unite = models.CharField(max_length=50, blank=True, verbose_name="Unité", help_text="Ex. unité, kg, litre…")
    domaine = models.ForeignKey(
        "Domaine",
        on_delete=models.PROTECT,
        related_name="expressions_besoin",
        verbose_name="Domaine",
    )
    description = models.TextField(verbose_name="Description / Justification")
    statut = models.CharField(
        max_length=20,
        choices=Statut.choices,
        default=Statut.EN_ATTENTE,
    )
    drp = models.ForeignKey(
        "DRP",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="expressions_besoin",
        verbose_name="DRP associée",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="expressions_besoin",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Expression des besoins"
        verbose_name_plural = "Expressions des besoins"

    def __str__(self) -> str:
        return f"{self.reference} — {self.produit}"

    def save(self, *args, **kwargs):
        if not self.pk and not self.reference:
            year = timezone.now().year
            count = ExpressionBesoin.objects.filter(
                reference__startswith=f"EB-{year}-"
            ).count() + 1
            self.reference = f"EB-{year}-{count:04d}"
        super().save(*args, **kwargs)


class PropositionEB(models.Model):
    """Proposition de fournisseurs soumise par l'admin domaine au DG."""

    expression_besoin = models.OneToOneField(
        ExpressionBesoin,
        on_delete=models.CASCADE,
        related_name="proposition",
    )
    fournisseurs = models.ManyToManyField(
        "Fournisseur",
        related_name="propositions",
        verbose_name="Fournisseurs proposés",
    )
    commentaire = models.TextField(blank=True, verbose_name="Commentaire / Justification")
    soumis_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="propositions_soumises",
        verbose_name="Soumis par",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Proposition admin"
        verbose_name_plural = "Propositions admin"

    def __str__(self) -> str:
        return f"Proposition — {self.expression_besoin.reference}"


class Facture(models.Model):
    """Facture réelle émise par le fournisseur retenu après attribution de la DRP."""

    invitation = models.OneToOneField(
        Invitation,
        on_delete=models.PROTECT,
        related_name="facture",
    )
    numero = models.CharField(max_length=100, verbose_name="Numéro de facture")
    montant = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
        verbose_name="Montant facturé (FCFA)",
    )
    date_facture = models.DateField(verbose_name="Date de facture")
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="factures_saisies",
    )

    class Meta:
        ordering = ["-date_facture"]
        verbose_name = "Facture"
        verbose_name_plural = "Factures"

    def __str__(self) -> str:
        return f"Facture {self.numero} — {self.invitation.fournisseur} ({self.montant} FCFA)"

    @property
    def ecart_proforma(self) -> Decimal | None:
        """Différence montant facturé − prix proforma (positive = surcoût)."""
        try:
            return self.montant - self.invitation.proforma.prix
        except Proforma.DoesNotExist:
            return None

    @property
    def ecart_proforma_pct(self) -> float | None:
        """Écart en % par rapport au prix proforma."""
        try:
            base = self.invitation.proforma.prix
            if base:
                return float((self.montant - base) / base * 100)
        except Proforma.DoesNotExist:
            pass
        return None
