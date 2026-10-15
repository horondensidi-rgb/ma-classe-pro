# ============================================================
# APP : comptes
# Fichier : backends.py (nouveau fichier)
# Rôle : permettre de se connecter avec son adresse e-mail OU son
#        identifiant, sans tenir compte des majuscules.
#
# Pourquoi : les nouveaux enseignants n'ont plus d'identifiant choisi
# à l'inscription, c'est leur e-mail qui sert d'identifiant. Les
# comptes existants (administrateur, élèves identifiés par matricule...)
# continuent de se connecter avec leur identifiant habituel.
# ============================================================

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q


class IdentifiantOuEmailBackend(ModelBackend):
    """
    Hérite de ModelBackend (le mécanisme de connexion standard de Django)
    et ne modifie que la façon de RETROUVER l'utilisateur : par
    identifiant OU par e-mail, majuscules/minuscules ignorées.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        UserModel = get_user_model()
        if username is None:
            username = kwargs.get(UserModel.USERNAME_FIELD)
        if not username or password is None:
            return None

        candidats = UserModel._default_manager.filter(
            Q(username__iexact=username) | Q(email__iexact=username)
        )
        # On teste le mot de passe sur chaque candidat : cela couvre le cas
        # (rare) de deux anciens comptes partageant la même adresse e-mail.
        for utilisateur in candidats:
            if utilisateur.check_password(password) and self.user_can_authenticate(utilisateur):
                return utilisateur

        if not candidats:
            # Même durée de calcul qu'avec un vrai compte : empêche de
            # deviner quels identifiants existent en mesurant le temps de réponse.
            UserModel().set_password(password)
        return None
