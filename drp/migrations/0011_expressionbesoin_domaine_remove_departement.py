from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("drp", "0010_departement_expressionbesoin"),
    ]

    operations = [
        # Remplace le FK departement (vers Departement) par domaine (vers Domaine)
        migrations.RemoveField(
            model_name="expressionbesoin",
            name="departement",
        ),
        migrations.AddField(
            model_name="expressionbesoin",
            name="domaine",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="expressions_besoin",
                to="drp.domaine",
                verbose_name="Domaine",
                # Valeur par défaut temporaire pour les lignes existantes (table vide en dev)
                default=None,
                null=True,
            ),
            preserve_default=False,
        ),
        # Supprime le modèle Departement devenu inutile
        migrations.DeleteModel(
            name="Departement",
        ),
    ]
