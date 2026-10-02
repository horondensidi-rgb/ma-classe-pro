# ============================================================
# APP : evaluations
# Fichier : forms.py
# Rôle : formulaire de création d'une évaluation (interrogation,
#        devoir, composition).
# ============================================================

from django import forms
from django.forms import inlineformset_factory
from .models import Evaluation, Question, Choix


class EvaluationForm(forms.ModelForm):
    """
    On exclut volontairement 'classe_matiere' : elle est déterminée
    par l'URL (on crée une évaluation DEPUIS la page d'une matière
    enseignée précise), pas choisie dans un menu déroulant — même
    logique que EleveForm dans classes/forms.py.

    On exclut 'sequence' et 'statut' : le rattachement à une séquence
    est optionnel et géré ailleurs, et le statut (brouillon/publiée)
    se pilote désormais via un bouton dédié dans la liste des
    évaluations (voir evaluations/views.py, publier_evaluation_view)
    plutôt que dans ce formulaire — on évite qu'un enseignant publie
    accidentellement une évaluation pas encore prête en cochant la
    mauvaise case au milieu d'un long formulaire.

    'est_en_ligne' EST inclus ici : c'est ce champ, combiné avec le
    statut, qui détermine si l'évaluation apparaît dans l'espace
    élève (voir Evaluation.est_ouverte). Sans lui, impossible de
    créer une évaluation destinée aux élèves.
    """

    class Meta:
        model = Evaluation
        fields = [
            'titre',
            'type_evaluation',
            'trimestre',
            'bareme_total',
            'coefficient',
            'date_evaluation',
            'est_en_ligne',
            'date_limite',
        ]
        widgets = {
            'date_evaluation': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'date_limite': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }
        labels = {
            'est_en_ligne': "Mettre en ligne pour les élèves (QCM)",
            'date_limite': "Date limite de réponse (si en ligne)",
        }


class QuestionForm(forms.ModelForm):
    """
    Informations d'UNE question (énoncé, type, points). Les choix
    de réponse (si type_question='QCM') sont gérés séparément par
    ChoixFormSet, une fois la question déjà créée — même logique en
    deux temps que FichePreparation/EtapeFiche dans l'app pedagogie.
    """

    class Meta:
        model = Question
        fields = ['numero_ordre', 'enonce', 'type_question', 'points']
        widgets = {
            'enonce': forms.Textarea(attrs={'rows': 2}),
        }


# ChoixFormSet : 4 propositions vides par défaut (1 bonne réponse +
# 3 distracteurs, le format QCM le plus courant), modifiable par
# l'enseignant (ajout/suppression de lignes via can_delete).
ChoixFormSet = inlineformset_factory(
    Question,
    Choix,
    fields=['texte', 'est_correct'],
    extra=4,
    can_delete=True,
)
