# ============================================================
# APP : pedagogie
# Fichier : admin.py
# ============================================================

from django.contrib import admin
from .models import Sequence, FichePreparation, EtapeFiche


# ------------------------------------------------------------
# SEQUENCE
# ------------------------------------------------------------
@admin.register(Sequence)
class SequenceAdmin(admin.ModelAdmin):
    list_display = ['titre', 'classe', 'numero', 'trimestre', 'date_debut', 'date_fin']
    list_filter = ['classe', 'trimestre']
    search_fields = ['titre']
    autocomplete_fields = ['classe']
    # Rappel : Classe a déjà search_fields défini dans classes/admin.py,
    # donc pas d'erreur E040 ici.


# ------------------------------------------------------------
# INLINE : gérer les étapes directement depuis la fiche
# ------------------------------------------------------------
class EtapeFicheInline(admin.TabularInline):
    """
    Le cœur de l'usage quotidien : au lieu de créer chaque étape
    séparément, l'enseignant remplit les 6 ou 8 étapes directement
    sous le formulaire de la FichePreparation.
    """
    model = EtapeFiche
    extra = 6
    # extra = 6 : pré-affiche 6 lignes vides par défaut (le cas le
    # plus fréquent, grammaire). Pour une fiche de conjugaison (8
    # étapes), il suffira d'ajouter 2 lignes de plus manuellement
    # avec le bouton "Ajouter une autre Étape de fiche".
    fields = ['numero_ordre', 'titre_etape', 'activite_maitre', 'activite_eleve', 'duree_minutes']
    ordering = ['numero_ordre']


# ------------------------------------------------------------
# FICHE DE PREPARATION
# ------------------------------------------------------------
@admin.register(FichePreparation)
class FichePreparationAdmin(admin.ModelAdmin):
    list_display = [
        'titre',
        'classe_matiere',
        'type_lecon',
        'date_prevue',
        'statut',
        'genere_par_ia',
    ]
    list_filter = ['type_lecon', 'statut', 'genere_par_ia', 'classe_matiere__classe']
    search_fields = ['titre', 'objectif_pedagogique_operationnel']
    autocomplete_fields = ['classe_matiere', 'sequence', 'enseignant']
    readonly_fields = ['date_creation', 'date_modification']
    inlines = [EtapeFicheInline]

    fieldsets = (
        ("Informations générales", {
            'fields': ('enseignant', 'classe_matiere', 'sequence', 'type_lecon', 'titre', 'duree_minutes')
        }),
        ("Contenu pédagogique", {
            'fields': ('rappel_lecon_precedente', 'objectif_pedagogique_operationnel')
        }),
        ("Planification et statut", {
            'fields': ('date_prevue', 'statut', 'genere_par_ia', 'fichier_pdf')
        }),
        ("Horodatage", {
            'fields': ('date_creation', 'date_modification'),
            'classes': ('collapse',),
            # 'collapse' : cette section est repliée par défaut dans le
            # formulaire (moins utile au quotidien, juste informatif).
        }),
    )
    # fieldsets : regroupe les champs en sections visuelles au lieu
    # d'un long formulaire linéaire — plus lisible avec autant de champs.