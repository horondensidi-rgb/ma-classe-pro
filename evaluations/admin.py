# ============================================================
# APP : evaluations
# Fichier : admin.py
# ============================================================

from django.contrib import admin
from .models import Evaluation, Question, Choix, Copie, ReponseEleve


# ------------------------------------------------------------
# INLINE : choix de réponse directement sous chaque question
# ------------------------------------------------------------
class ChoixInline(admin.TabularInline):
    model = Choix
    extra = 4
    # 4 propositions par défaut : un standard courant de QCM
    # (souvent 1 bonne réponse + 3 distracteurs).
    fields = ['texte', 'est_correct']


# ------------------------------------------------------------
# INLINE : questions directement sous chaque évaluation
# ------------------------------------------------------------
class QuestionInline(admin.TabularInline):
    """
    Inline "léger" (sans les choix) pour avoir une vue d'ensemble
    rapide des questions depuis la page Evaluation. Pour ajouter les
    choix de réponse d'une question précise, il faut ouvrir cette
    question individuellement (lien cliquable via show_change_link).
    """
    model = Question
    extra = 1
    fields = ['numero_ordre', 'enonce', 'type_question', 'points']
    show_change_link = True
    # show_change_link : ajoute un lien "Modifier" sur chaque ligne
    # pour ouvrir la question en détail (et accéder à ses Choix).


# ------------------------------------------------------------
# EVALUATION
# ------------------------------------------------------------
@admin.register(Evaluation)
class EvaluationAdmin(admin.ModelAdmin):
    list_display = [
        'titre',
        'classe_matiere',
        'type_evaluation',
        'trimestre',
        'date_evaluation',
        'bareme_total',
        'coefficient',
        'est_en_ligne',
        'statut',
        'date_limite',
    ]
    list_filter = ['trimestre', 'type_evaluation', 'statut', 'est_en_ligne', 'classe_matiere__classe']
    search_fields = ['titre']
    autocomplete_fields = ['classe_matiere', 'sequence']
    inlines = [QuestionInline]


# ------------------------------------------------------------
# QUESTION (accès direct, nécessaire pour atteindre ses Choix)
# ------------------------------------------------------------
@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ['evaluation', 'numero_ordre', 'enonce', 'type_question', 'points']
    list_filter = ['type_question', 'evaluation']
    search_fields = ['enonce']
    autocomplete_fields = ['evaluation']
    inlines = [ChoixInline]


# ------------------------------------------------------------
# CHOIX (enregistrement indépendant nécessaire)
# ------------------------------------------------------------
@admin.register(Choix)
class ChoixAdmin(admin.ModelAdmin):
    """
    Choix est déjà géré comme inline sous Question (ChoixInline
    ci-dessus), MAIS ça ne suffit pas : dès qu'un AUTRE endroit du
    code (ici ReponseEleveInline.autocomplete_fields) veut proposer
    une recherche de Choix, Django exige que ce modèle ait aussi
    son PROPRE ModelAdmin enregistré via @admin.register, même s'il
    n'est jamais utilisé directement en dehors des inlines.
    C'est l'erreur admin.E039 : "must be registered" (différente de
    E040 qui elle réclamait juste search_fields sur un admin déjà
    enregistré).
    """
    list_display = ['question', 'texte', 'est_correct']
    list_filter = ['est_correct', 'question__evaluation']
    search_fields = ['texte']
    autocomplete_fields = ['question']


# ------------------------------------------------------------
# COPIE
# ------------------------------------------------------------
class ReponseEleveInline(admin.TabularInline):
    model = ReponseEleve
    extra = 0
    # extra = 0 : ici on ne veut PAS de ligne vide pré-remplie —
    # les réponses viendront des élèves eux-mêmes via le futur
    # espace élève, pas d'une saisie manuelle habituelle.
    fields = ['question', 'choix_selectionne', 'texte_reponse', 'points_obtenus']
    autocomplete_fields = ['question', 'choix_selectionne']
    readonly_fields = ['question', 'texte_reponse']
    # On rend "question" et "texte_reponse" non modifiables ici :
    # l'enseignant doit pouvoir CORRIGER (points_obtenus, choix
    # éventuellement) mais pas réécrire la réponse brute de l'élève.


@admin.register(Copie)
class CopieAdmin(admin.ModelAdmin):
    list_display = ['eleve', 'evaluation', 'note_obtenue', 'statut', 'date_soumission']
    list_filter = ['statut', 'evaluation']
    search_fields = ['eleve__nom', 'eleve__prenom']
    autocomplete_fields = ['eleve', 'evaluation']
    inlines = [ReponseEleveInline]

    actions = ['action_calculer_note_qcm']

    def action_calculer_note_qcm(self, request, queryset):
        """
        Recalcule automatiquement la partie QCM de la note pour
        chaque copie sélectionnée (n'écrase pas les points saisis
        à la main sur les questions à réponse libre).
        """
        compteur = 0
        for copie in queryset:
            points_qcm = copie.calculer_note_qcm()
            # Ici on choisit de ne PAS écraser note_obtenue si des
            # questions libres existent aussi : on informe seulement
            # l'enseignant du sous-total QCM calculé.
            compteur += 1
        self.message_user(
            request,
            f"Points QCM recalculés pour {compteur} copie(s). "
            f"Pense à ajouter manuellement les points des questions libres "
            f"pour obtenir la note finale."
        )
    action_calculer_note_qcm.short_description = "Recalculer les points QCM"