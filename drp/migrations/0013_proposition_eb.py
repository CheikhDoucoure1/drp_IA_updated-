from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("drp", "0012_domaine_responsable"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PropositionEB",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("commentaire", models.TextField(blank=True, verbose_name="Commentaire / Justification")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "expression_besoin",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="proposition",
                        to="drp.expressionbesoin",
                    ),
                ),
                (
                    "fournisseurs",
                    models.ManyToManyField(
                        related_name="propositions",
                        to="drp.fournisseur",
                        verbose_name="Fournisseurs proposés",
                    ),
                ),
                (
                    "soumis_par",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="propositions_soumises",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Soumis par",
                    ),
                ),
            ],
            options={
                "verbose_name": "Proposition admin",
                "verbose_name_plural": "Propositions admin",
            },
        ),
    ]
