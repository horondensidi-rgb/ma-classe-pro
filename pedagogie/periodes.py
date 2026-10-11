# ============================================================
# APP : pedagogie
# Fichier : periodes.py (nouveau fichier)
# Rôle : déterminer le mois et le trimestre en cours, pour compter
#        les leçons prévues et dispensées sur ces périodes.
# ============================================================

import calendar
from datetime import date

NOMS_TRIMESTRES = {1: '1er trimestre', 2: '2ème trimestre', 3: '3ème trimestre'}


def trimestre_courant(jour):
    """
    Renvoie (numéro, date_début, date_fin) du trimestre qui contient
    la date donnée.

    Convention utilisée (calendrier scolaire malien usuel, à ajuster
    ICI si ton établissement découpe l'année autrement) :
      - 1er trimestre : septembre à décembre
      - 2ème trimestre : janvier à mars
      - 3ème trimestre : avril à août (inclut les vacances de fin d'année)
    """
    if jour.month >= 9:
        return 1, date(jour.year, 9, 1), date(jour.year, 12, 31)
    if jour.month <= 3:
        return 2, date(jour.year, 1, 1), date(jour.year, 3, 31)
    return 3, date(jour.year, 4, 1), date(jour.year, 8, 31)


def bornes_du_mois(jour):
    """Renvoie (premier_jour, dernier_jour) du mois de la date donnée."""
    dernier = calendar.monthrange(jour.year, jour.month)[1]
    return date(jour.year, jour.month, 1), date(jour.year, jour.month, dernier)
