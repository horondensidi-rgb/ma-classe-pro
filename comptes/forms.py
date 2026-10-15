# ============================================================
# APP : comptes
# Fichier : forms.py
# Rôle : formulaire d'inscription d'un nouvel enseignant.
#
# Django distingue clairement modèle (models.py) et formulaire
# (forms.py) : le formulaire s'occupe de VALIDER et NETTOYER les
# données saisies par l'utilisateur AVANT qu'elles n'atteignent
# la base de données.
# ============================================================

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.db.models import Q
from .models import Etablissement


class InscriptionForm(UserCreationForm):
    """
    On hérite de UserCreationForm (fourni par Django) plutôt que de
    tout réécrire à la main : il gère déjà la création du username,
    la saisie du mot de passe DEUX FOIS (confirmation), et la
    validation de sa solidité (longueur, pas trop commun, etc.).

    On y AJOUTE les champs nécessaires pour créer, en plus du User,
    le profil Enseignant et son Etablissement — même si ces champs
    n'existent pas sur le modèle User lui-même.
    """

    email = forms.EmailField(
        required=True,
        max_length=150,
        label="Adresse e-mail",
        help_text="Elle sert d'identifiant pour te connecter."
    )

    first_name = forms.CharField(
        max_length=150,
        label="Prénom"
    )

    last_name = forms.CharField(
        max_length=150,
        label="Nom"
    )

    telephone = forms.CharField(
        max_length=20,
        label="Téléphone (Mobile Money)",
        help_text="Numéro utilisé pour Orange Money / Moov Money, ex : 70000000"
    )

    etablissement_nom = forms.CharField(
        max_length=200,
        label="Nom de votre établissement"
    )

    etablissement_ville = forms.CharField(
        max_length=100,
        label="Ville"
    )

    etablissement_region = forms.ChoiceField(
        choices=Etablissement.REGION_CHOICES,
        label="Région",
        initial='SIKASSO'
    )

    class Meta(UserCreationForm.Meta):
        # Meta(UserCreationForm.Meta) : on hérite aussi de la config
        # Meta du parent (qui pointe déjà vers model = User), et on
        # la complète juste avec la liste des champs à afficher.
        model = User
        fields = ['first_name', 'last_name', 'email']
        # 'username' n'est volontairement PLUS demandé : deux enseignants
        # peuvent avoir exactement le même nom, mais deux comptes ne
        # peuvent pas partager le même identifiant de connexion. C'est
        # donc l'adresse e-mail (unique par personne) qui sert d'identifiant ;
        # le username interne est rempli automatiquement dans save().
        # On ne remet PAS password1/password2 ici : UserCreationForm
        # les gère déjà tout seul en interne, pas besoin de les redéclarer.

    field_order = [
        'first_name', 'last_name', 'email', 'telephone',
        'etablissement_nom', 'etablissement_ville', 'etablissement_region',
        'password1', 'password2',
    ]

    def clean_email(self):
        """
        Vérifie que l'adresse e-mail n'est pas déjà utilisée (sans tenir
        compte des majuscules), puisqu'elle devient l'identifiant de
        connexion. Elle est enregistrée en minuscules pour éviter qu'une
        même adresse soit saisie de deux façons différentes.
        """
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(Q(email__iexact=email) | Q(username__iexact=email)).exists():
            raise forms.ValidationError(
                "Un compte existe déjà avec cette adresse e-mail. "
                "Connecte-toi, ou utilise « Mot de passe oublié »."
            )
        return email

    def save(self, commit=True):
        """
        On surcharge save() pour transférer les champs supplémentaires
        (email, first_name, last_name) vers l'objet User AVANT de le
        sauvegarder — sinon Django ne saurait pas automatiquement que
        ces champs doivent y être copiés.

        Remarque : cette méthode ne s'occupe QUE de l'objet User.
        La création de l'Etablissement et de l'Enseignant se fait
        dans la vue (views.py), pas ici — pour garder ce formulaire
        centré sur une seule responsabilité claire.
        """
        user = super().save(commit=False)
        # commit=False : on prépare l'objet User en mémoire SANS
        # encore l'écrire en base, le temps de finir de le compléter.
        user.email = self.cleaned_data['email']
        user.username = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        if commit:
            user.save()
        return user
