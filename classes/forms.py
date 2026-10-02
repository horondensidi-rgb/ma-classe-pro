# ============================================================
# APP : classes
# Fichier : forms.py
# Rôle : formulaire d'ajout/modification d'un élève.
# ============================================================

from django import forms
from .models import Eleve


class EleveForm(forms.ModelForm):
    """
    ModelForm : contrairement à InscriptionForm (comptes/forms.py)
    qui combinait plusieurs modèles à la main, ici un simple
    ModelForm suffit — Django génère automatiquement les champs
    à partir du modèle Eleve, avec les bonnes validations
    (ex : matricule unique, sexe limité aux choices...).
    """

    class Meta:
        model = Eleve
        # On exclut 'classe' : elle sera déterminée par l'URL
        # (on ajoute un élève DEPUIS la page d'une classe précise),
        # pas choisie librement dans un menu déroulant.
        fields = [
            'matricule',
            'prenom',
            'nom',
            'sexe',
            'date_naissance',
            'lieu_naissance',
            'nom_tuteur',
            'telephone_tuteur',
        ]
        widgets = {
            # widgets : permet de préciser le TYPE de champ HTML
            # généré. Par défaut, DateField afficherait un simple
            # champ texte ; type='date' fait apparaître un vrai
            # sélecteur de date sur mobile comme sur PC.
            'date_naissance': forms.DateInput(attrs={'type': 'date'}),
        }