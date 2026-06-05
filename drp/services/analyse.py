"""
Analyse IA des proformas fournisseurs par domaine.

Pour chaque domaine ayant au moins un DRP, agrège tous les proformas soumis
par les fournisseurs et demande à Claude d'identifier le prix le plus abordable.
"""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass, field
from decimal import Decimal


@dataclass
class LigneProforma:
    drp_titre: str
    fournisseur_nom: str
    prix: Decimal
    delai_jours: int
    est_min: bool = False


@dataclass
class AnalyseDomaine:
    domaine_nom: str
    lignes: list[LigneProforma] = field(default_factory=list)
    nb_proformas: int = 0
    prix_min: Decimal | None = None
    fournisseur_min: str | None = None
    prix_max: Decimal | None = None
    prix_moy: Decimal | None = None
    commentaire_ia: str = ""


def _build_analyses() -> list[AnalyseDomaine]:
    """Agrège les proformas par domaine."""
    from drp.models import Domaine, Proforma

    domaines = Domaine.objects.all().order_by("nom")
    analyses = []

    for domaine in domaines:
        proformas = (
            Proforma.objects.filter(invitation__drp__domaines=domaine)
            .select_related(
                "invitation__fournisseur",
                "invitation__drp",
            )
            .order_by("prix")
        )

        lignes: list[LigneProforma] = []
        for p in proformas:
            lignes.append(
                LigneProforma(
                    drp_titre=p.invitation.drp.titre,
                    fournisseur_nom=p.invitation.fournisseur.nom,
                    prix=p.prix,
                    delai_jours=p.delai_jours,
                )
            )

        if not lignes:
            continue

        prix_list = [l.prix for l in lignes]
        prix_min = min(prix_list)
        prix_max = max(prix_list)
        prix_moy = sum(prix_list) / len(prix_list)

        for ligne in lignes:
            if ligne.prix == prix_min:
                ligne.est_min = True

        fournisseur_min = next(l.fournisseur_nom for l in lignes if l.est_min)

        analyses.append(
            AnalyseDomaine(
                domaine_nom=domaine.nom,
                lignes=lignes,
                nb_proformas=len(lignes),
                prix_min=prix_min,
                fournisseur_min=fournisseur_min,
                prix_max=prix_max,
                prix_moy=prix_moy,
            )
        )

    return analyses


def _prompt_pour_domaine(analyse: AnalyseDomaine) -> str:
    lignes_txt = "\n".join(
        f"  - DRP « {l.drp_titre} » | Fournisseur : {l.fournisseur_nom} "
        f"| Prix proforma : {l.prix:,.0f} FCFA | Délai : {l.delai_jours} jour(s)"
        for l in analyse.lignes
    )
    stats = (
        f"Nombre de proformas : {analyse.nb_proformas}\n"
        f"Prix le plus bas    : {analyse.prix_min:,.0f} FCFA ({analyse.fournisseur_min})\n"
        f"Prix le plus élevé  : {analyse.prix_max:,.0f} FCFA\n"
        f"Prix moyen          : {analyse.prix_moy:,.0f} FCFA\n"
    )
    return (
        f"Tu es un analyste achats senior de Petrosen E&P.\n"
        f"Voici tous les proformas reçus pour le domaine « {analyse.domaine_nom} » :\n\n"
        f"{stats}\n"
        f"Détail des proformas :\n{lignes_txt}\n\n"
        "En 3 à 4 phrases concises en français :\n"
        "1. Indique quel fournisseur propose le prix le plus abordable et de combien il est inférieur à la moyenne.\n"
        "2. Signale si certains fournisseurs sont significativement plus chers que la moyenne.\n"
        "3. Prends en compte les délais pour nuancer la recommandation si nécessaire.\n"
        "4. Donne une recommandation claire pour le choix du fournisseur dans ce domaine.\n"
        "Sois direct et factuel. Ne répète pas les chiffres bruts déjà listés."
    )


def generer_analyse_ia() -> list[AnalyseDomaine]:
    """
    Construit les analyses par domaine à partir des proformas et, si
    ANTHROPIC_API_KEY est disponible, enrichit chaque domaine avec un
    commentaire IA identifiant le prix le plus abordable.
    """
    analyses = _build_analyses()
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")

    if not api_key:
        for a in analyses:
            a.commentaire_ia = (
                "Clé ANTHROPIC_API_KEY non configurée — "
                "renseignez-la dans votre fichier .env pour activer l'analyse IA."
            )
        return analyses

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        for analyse in analyses:
            prompt = _prompt_pour_domaine(analyse)
            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=512,
                messages=[{"role": "user", "content": prompt}],
            )
            analyse.commentaire_ia = response.content[0].text.strip()
    except Exception as exc:
        for a in analyses:
            if not a.commentaire_ia:
                a.commentaire_ia = f"Erreur lors de l'analyse IA : {exc}"

    return analyses


def analyser_proforma_pdf(proforma) -> str:
    """
    Lit le PDF d'un proforma et demande à Claude d'extraire et analyser son contenu.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return "Clé ANTHROPIC_API_KEY non configurée — renseignez-la dans votre fichier .env."

    if not proforma.fichier:
        return "Ce proforma ne contient pas de fichier PDF."

    try:
        with open(proforma.fichier.path, "rb") as f:
            pdf_b64 = base64.standard_b64encode(f.read()).decode("utf-8")
    except (OSError, IOError) as exc:
        return f"Impossible de lire le fichier PDF : {exc}"

    prompt = (
        f"Tu es un analyste achats de Petrosen E&P. "
        f"Voici le proforma PDF soumis par le fournisseur « {proforma.invitation.fournisseur.nom} » "
        f"pour la DRP « {proforma.invitation.drp.titre} ».\n\n"
        f"Données saisies manuellement par le fournisseur :\n"
        f"- Prix déclaré : {proforma.prix:,.0f} FCFA\n"
        f"- Délai déclaré : {proforma.delai_jours} jour(s)\n"
        f"- Commentaire : {proforma.commentaire or 'Aucun'}\n\n"
        "Analyse ce document PDF et fournis une réponse structurée en 5 points :\n"
        "1. **Prestations proposées** : résumé de ce qui est offert\n"
        "2. **Cohérence prix/délai** : les chiffres du PDF correspondent-ils aux données saisies ?\n"
        "3. **Conditions particulières** : paiement, garantie, livraison, validité de l'offre\n"
        "4. **Points de vigilance** : risques, clauses défavorables, informations manquantes\n"
        "5. **Recommandation** : Favorable / À négocier / Défavorable — en une phrase\n\n"
        "Réponds en français, de façon concise et professionnelle."
    )

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "document",
                            "source": {
                                "type": "base64",
                                "media_type": "application/pdf",
                                "data": pdf_b64,
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        )
        return response.content[0].text.strip()
    except Exception as exc:
        return f"Erreur lors de l'analyse IA : {exc}"
