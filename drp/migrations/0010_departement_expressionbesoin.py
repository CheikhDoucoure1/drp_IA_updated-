from django.conf import settings
from django.db import migrations, models
import django.core.validators
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("drp", "0009_invitation_date_reactivation"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Departement",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nom", models.CharField(max_length=200, unique=True)),
            ],
            options={
                "verbose_name": "Département",
                "verbose_name_plural": "Départements",
                "ordering": ["nom"],
            },
        ),
        migrations.CreateModel(
            name="ExpressionBesoin",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("reference", models.CharField(editable=False, max_length=30, unique=True, verbose_name="Référence")),
                ("produit", models.CharField(max_length=300, verbose_name="Produit / Service")),
                (
                    "quantite",
                    models.PositiveIntegerField(
                        default=1,
                        validators=[django.core.validators.MinValueValidator(1)],
                        verbose_name="Quantité",
                    ),
                ),
                ("unite", models.CharField(blank=True, help_text="Ex. unité, kg, litre…", max_length=50, verbose_name="Unité")),
                ("description", models.TextField(verbose_name="Description / Justification")),
                (
                    "statut",
                    models.CharField(
                        choices=[
                            ("en_attente", "En attente"),
                            ("approuvee", "Approuvée"),
                            ("rejetee", "Rejetée"),
                            ("convertie", "Convertie en DRP"),
                        ],
                        default="en_attente",
                        max_length=20,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="expressions_besoin",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "departement",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="expressions_besoin",
                        to="drp.departement",
                        verbose_name="Département demandeur",
                    ),
                ),
                (
                    "drp",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="expressions_besoin",
                        to="drp.drp",
                        verbose_name="DRP associée",
                    ),
                ),
            ],
            options={
                "verbose_name": "Expression de besoin",
                "verbose_name_plural": "Expressions de besoin",
                "ordering": ["-created_at"],
            },
        ),
    ]
