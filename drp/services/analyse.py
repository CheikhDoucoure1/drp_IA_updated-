"""
Analyse IA des proformas fournisseurs par DRP.

Pour chaque DRP ayant au moins un proforma soumis, agrège les offres des
fournisseurs et demande à Claude d'identifier le meilleur choix.
"""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass, field
from decimal import Decimal


@dataclass
class LigneProforma:
    proforma_id: int
    fournisseur_nom: str
    prix: Decimal
    delai_jours: int
    est_min: bool = False


@dataclass
class AnalyseDRP:
    drp_titre: str
    statut: str
    lignes: list[LigneProforma] = field(default_factory=list)
    nb_proformas: int = 0
    prix_min: Decimal | None = None
    fournisseur_min: str | None = None
    prix_max: Decimal | None = None
    prix_moy: Decimal | None = None
    commentaire_ia: str = ""


def _build_analyses(drp_queryset) -> list[AnalyseDRP]:
    """Agrège les proformas par DRP."""
    from drp.models import Proforma

    analyses = []

    for drp in drp_queryset.order_by("-created_at"):
        proformas = (
            Proforma.objects.filter(invitation__drp=drp)
            .select_related("invitation__fournisseur")
            .order_by("prix")
        )

        lignes: list[LigneProforma] = []
        for p in proformas:
            lignes.append(
                LigneProforma(
                    proforma_id=p.pk,
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
            AnalyseDRP(
                drp_titre=drp.titre,
                statut=drp.statut,
                lignes=lignes,
                nb_proformas=len(lignes),
                prix_min=prix_min,
                fournisseur_min=fournisseur_min,
                prix_max=prix_max,
                prix_moy=prix_moy,
            )
        )

    return analyses


def _prompt_pour_drp(analyse: AnalyseDRP) -> str:
    lignes_txt = "\n".join(
        f"  - Fournisseur : {l.fournisseur_nom} "
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
        f"Voici tous les proformas reçus pour la DRP « {analyse.drp_titre} » :\n\n"
        f"{stats}\n"
        f"Détail des proformas :\n{lignes_txt}\n\n"
        "En 3 à 4 phrases concises en français :\n"
        "1. Indique quel fournisseur propose le prix le plus abordable et de combien il est inférieur à la moyenne.\n"
        "2. Signale si certains fournisseurs sont significativement plus chers que la moyenne.\n"
        "3. Prends en compte les délais pour nuancer la recommandation si nécessaire.\n"
        "4. Donne une recommandation claire pour le choix du fournisseur pour cette DRP.\n"
        "Sois direct et factuel. Ne répète pas les chiffres bruts déjà listés."
    )


def generer_analyse_ia(drp_queryset=None) -> list[AnalyseDRP]:
    """
    Construit les analyses par DRP à partir des proformas et, si
    ANTHROPIC_API_KEY est disponible, enrichit chaque DRP avec un
    commentaire IA identifiant le meilleur fournisseur.
    """
    if drp_queryset is None:
        from drp.models import DRP
        drp_queryset = DRP.objects.all()

    analyses = _build_analyses(drp_queryset)
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
            prompt = _prompt_pour_drp(analyse)
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


def analyser_fournisseur_complet(proforma) -> str:
    """
    Analyse complète d'un fournisseur pour une DRP :
    proforma (+ PDF si disponible) + facture éventuelle + contexte comparatif.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return "Clé ANTHROPIC_API_KEY non configurée — renseignez-la dans votre fichier .env."

    from drp.models import Proforma as ProformaModel

    drp = proforma.invitation.drp
    fournisseur = proforma.invitation.fournisseur

    # Facture si elle existe
    facture = None
    try:
        facture = proforma.invitation.facture
    except Exception:
        pass

    # Autres proformas pour la même DRP (contexte comparatif)
    autres = (
        ProformaModel.objects.filter(invitation__drp=drp)
        .exclude(pk=proforma.pk)
        .select_related("invitation__fournisseur")
        .order_by("prix")
    )
    autres_txt = "\n".join(
        f"  - {p.invitation.fournisseur.nom} : {p.prix:,.0f} FCFA, délai {p.delai_jours} j"
        for p in autres
    ) or "  Aucune autre offre reçue."

    budget_txt = (
        f"\nBudget prévisionnel DRP : {drp.budget_previsionnel:,.0f} FCFA"
        if drp.budget_previsionnel else ""
    )

    facture_txt = ""
    if facture:
        ecart = facture.ecart_proforma
        ecart_pct = facture.ecart_proforma_pct
        ecart_str = (
            f"{ecart:+,.0f} FCFA ({ecart_pct:+.1f}%)"
            if ecart is not None and ecart_pct is not None else "N/D"
        )
        facture_txt = (
            f"\n\n=== FACTURE RÉELLE ===\n"
            f"Numéro       : {facture.numero}\n"
            f"Montant      : {facture.montant:,.0f} FCFA\n"
            f"Date         : {facture.date_facture}\n"
            f"Écart proforma : {ecart_str}\n"
        )

    prompt = (
        f"Tu es un analyste achats senior de Petrosen E&P.\n"
        f"Analyse complète du fournisseur « {fournisseur.nom} » pour la DRP « {drp.titre} ».\n\n"
        f"=== PROFORMA SOUMIS ===\n"
        f"Prix proposé  : {proforma.prix:,.0f} FCFA\n"
        f"Délai proposé : {proforma.delai_jours} jour(s)\n"
        f"Commentaire   : {proforma.commentaire or 'Aucun'}\n"
        f"{budget_txt}\n\n"
        f"=== AUTRES OFFRES REÇUES POUR CETTE DRP ===\n{autres_txt}"
        f"{facture_txt}\n\n"
        "Fournis une analyse structurée en 5 points :\n"
        "1. **Position concurrentielle** : place de ce fournisseur par rapport aux autres (prix, délai)\n"
        "2. **Rapport qualité-prix** : le prix est-il justifié compte tenu du délai et du marché ?\n"
        "3. **Cohérence financière** : si une facture existe, analyse l'écart proforma/facture et ses implications\n"
        "4. **Points de vigilance** : risques identifiés (délai long, surcoût, écart de facturation, etc.)\n"
        "5. **Recommandation finale** : Retenir / À négocier / Écarter — avec justification claire\n\n"
        "Sois direct, factuel et professionnel. Réponds en français."
    )

    # Inclure le PDF du proforma si disponible
    content: object = prompt
    if proforma.fichier:
        try:
            with open(proforma.fichier.path, "rb") as f:
                pdf_b64 = base64.standard_b64encode(f.read()).decode("utf-8")
            content = [
                {
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": "application/pdf",
                        "data": pdf_b64,
                    },
                },
                {
                    "type": "text",
                    "text": prompt + "\n\nLe PDF du proforma est joint — utilise-le pour enrichir ton analyse.",
                },
            ]
        except (OSError, IOError):
            pass

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            messages=[{"role": "user", "content": content}],
        )
        return response.content[0].text.strip()
    except Exception as exc:
        return f"Erreur lors de l'analyse IA : {exc}"


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
