"""Classement des proformas d'une DRP selon les pondérations prix / délai."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from drp.models import DRP, Proforma


@dataclass(frozen=True)
class ProformaClassement:
    proforma: Proforma
    rang: int | None  # 1, 2 ou 3 pour le podium ; None au-delà
    score: Decimal


def classement_proformas(drp: DRP, proformas: list[Proforma]) -> list[ProformaClassement]:
    """
    Classe les offres de la meilleure à la moins bonne.
    Score normalisé sur [0, 1] : plus le prix est bas et le délai court, plus le score est élevé.
    """
    if not proformas:
        return []

    prixs = [p.prix for p in proformas]
    delais = [p.delai_jours for p in proformas]
    min_prix, max_prix = min(prixs), max(prixs)
    min_delai, max_delai = min(delais), max(delais)

    total_poids = drp.poids_prix + drp.poids_delai
    if total_poids <= 0:
        w_prix = w_delai = Decimal("0.5")
    else:
        w_prix = Decimal(drp.poids_prix) / Decimal(total_poids)
        w_delai = Decimal(drp.poids_delai) / Decimal(total_poids)

    scored: list[tuple[Proforma, Decimal]] = []
    for p in proformas:
        if max_prix == min_prix:
            prix_norm = Decimal("1")
        else:
            prix_norm = (max_prix - p.prix) / (max_prix - min_prix)

        if max_delai == min_delai:
            delai_norm = Decimal("1")
        else:
            delai_norm = Decimal(max_delai - p.delai_jours) / Decimal(max_delai - min_delai)

        score = w_prix * prix_norm + w_delai * delai_norm
        scored.append((p, score))

    scored.sort(key=lambda item: (-item[1], item[0].prix, item[0].delai_jours, item[0].pk))

    result: list[ProformaClassement] = []
    for index, (proforma, score) in enumerate(scored):
        rang = index + 1 if index < 3 else None
        result.append(ProformaClassement(proforma=proforma, rang=rang, score=score))
    return result
