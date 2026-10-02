# ============================================================
# APP : pedagogie
# Fichier : forms.py
# Rôle : formulaire des informations générales d'une fiche de
#        préparation, et formset du déroulement (les étapes).
# ============================================================

from django import forms
from django.forms import inlineformset_factory
from .models import FichePreparation, EtapeFiche


class FichePreparationForm(forms.ModelForm):
    """
    Couvre l'EN-TÊTE de la fiche (discipline, titre, durée, R.L.P.,
    O.P.O...), PAS le déroulement étape par étape — celui-ci est
    géré séparément par EtapeFicheFormSet, dans une deuxième page,
    car le nombre d'étapes dépend du type_lecon choisi ICI (on ne
    peut le savoir qu'UNE FOIS ce formulaire déjà soumis).
    """

    class Meta:
        model = FichePreparation
        fields = [
            'sequence',
            'type_lecon',
            'titre',
            'duree_minutes',
            'date_prevue',
            'rappel_lecon_precedente',
            'objectif_pedagogique_operationnel',
            'statut',
        ]
        widgets = {
            'date_prevue': forms.DateInput(attrs={'type': 'date'}),
            'rappel_lecon_precedente': forms.Textarea(attrs={'rows': 2}),
            'objectif_pedagogique_operationnel': forms.Textarea(attrs={'rows': 2}),
        }
        labels = {
            'rappel_lecon_precedente': "R.L.P. (Rappel de la leçon précédente)",
            'objectif_pedagogique_operationnel': "O.P.O. (Objectif Pédagogique Opérationnel)",
        }

    def __init__(self, *args, classe_matiere=None, **kwargs):
        """
        On accepte classe_matiere en paramètre (passé depuis la vue,
        jamais depuis le POST du navigateur) pour ne proposer, dans
        la liste déroulante 'sequence', QUE les séquences qui
        appartiennent à la classe concernée — pas celles d'une
        autre classe, ce qui n'aurait aucun sens.
        """
        super().__init__(*args, **kwargs)
        if classe_matiere is not None:
            self.fields['sequence'].queryset = classe_matiere.classe.sequences.all()
        self.fields['sequence'].required = False


# inlineformset_factory : génère un "formset" (plusieurs formulaires
# du même type d'un coup) spécialement lié à une relation parent/
# enfant déjà existante dans les modèles (ici FichePreparation ->
# EtapeFiche, via le ForeignKey EtapeFiche.fiche). Django s'occupe
# de tout le câblage : ajout, modification, ET suppression d'étapes.
EtapeFicheFormSet = inlineformset_factory(
    FichePreparation,
    EtapeFiche,
    fields=['numero_ordre', 'titre_etape', 'activite_maitre', 'activite_eleve', 'duree_minutes'],
    extra=0,
    # extra=0 ICI : le nombre de lignes vides à afficher est décidé
    # dynamiquement dans la vue (selon le type_lecon de la fiche),
    # pas fixé une fois pour toutes dans le formulaire.
    can_delete=True,
    widgets={
        'activite_maitre': forms.Textarea(attrs={'rows': 2}),
        'activite_eleve': forms.Textarea(attrs={'rows': 2}),
    },
)