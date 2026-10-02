# ============================================================
# APP : comptes
# Fichier : permissions.py (nouveau fichier)
# Rôle : centraliser la récupération sécurisée du profil
#        Enseignant lié à l'utilisateur connecté.
# ============================================================

from django.core.exceptions import PermissionDenied


def obtenir_enseignant_ou_403(request):
    """
    Renvoie le profil Enseignant de l'utilisateur connecté, ou lève
    une erreur 403 (Accès refusé) si ce compte n'en a pas — par
    exemple un compte superutilisateur créé via `createsuperuser`,
    qui n'est jamais passé par le formulaire d'inscription.

    Centraliser cette vérification ICI évite de la réécrire (et de
    l'oublier) dans chaque vue qui a besoin de "l'enseignant
    actuellement connecté" — c'est déjà arrivé une fois avec
    liste_classes_view, qui plantait sans ce garde-fou.
    """
    try:
        enseignant = request.user.profil_enseignant
    except AttributeError:
        # request.user.profil_enseignant lève AttributeError (via
        # RelatedObjectDoesNotExist, qui hérite à la fois de
        # AttributeError et de Enseignant.DoesNotExist) quand aucun
        # profil Enseignant n'existe pour ce User.
        raise PermissionDenied(
            "Ce compte n'a pas de profil enseignant associé."
        )

    if not enseignant.est_actif:
        # C'EST ICI que le champ Enseignant.est_actif devient un vrai
        # outil de désactivation, et pas juste une case à cocher sans
        # effet : un enseignant désactivé par l'administrateur (ex:
        # a quitté l'établissement) perd IMMÉDIATEMENT l'accès à
        # toute vue de l'application, sans que ses données (classes,
        # fiches, notes déjà saisies) soient jamais supprimées.
        raise PermissionDenied(
            "Ce compte enseignant a été désactivé par l'administrateur."
        )

    return enseignant