# ============================================================
# APP : comptes
# Fichier : admin.py
# Rôle : rendre Etablissement, PlanAbonnement, Enseignant et
#        Paiement gérables depuis l'admin. Etablissement et
#        Enseignant DOIVENT avoir search_fields, car l'app
#        "classes" les utilise en autocomplete_fields.
# ============================================================

from django.contrib import admin
from .models import Etablissement, PlanAbonnement, Enseignant, Paiement


# ------------------------------------------------------------
# ETABLISSEMENT
# ------------------------------------------------------------
@admin.register(Etablissement)
class EtablissementAdmin(admin.ModelAdmin):
    """
    search_fields indispensable ici : ClasseAdmin (app classes)
    pointe vers Etablissement via autocomplete_fields.
    """
    list_display = ['nom', 'ville', 'region', 'type_etablissement']
    list_filter = ['region', 'type_etablissement']
    search_fields = ['nom', 'ville']


# ------------------------------------------------------------
# PLAN D'ABONNEMENT
# ------------------------------------------------------------
@admin.register(PlanAbonnement)
class PlanAbonnementAdmin(admin.ModelAdmin):
    list_display = ['nom', 'prix_mensuel', 'nombre_classes_max', 'acces_ia_preparation']
    list_filter = ['acces_ia_preparation']
    search_fields = ['nom']


# ------------------------------------------------------------
# ENSEIGNANT
# ------------------------------------------------------------
@admin.register(Enseignant)
class EnseignantAdmin(admin.ModelAdmin):
    """
    search_fields indispensable ici : ClasseAdmin et
    ClasseMatiereInline (app classes) pointent vers Enseignant
    via autocomplete_fields.
    """
    list_display = [
        'user',
        'etablissement',
        'plan_abonnement',
        'est_actif',
        'date_fin_abonnement',
    ]
    list_filter = ['etablissement', 'plan_abonnement', 'est_actif']
    search_fields = [
        'user__username',
        'user__first_name',
        'user__last_name',
        'telephone',
    ]
    # On traverse la relation vers User (user__...) car le nom et
    # prénom réels sont stockés sur User, pas directement sur Enseignant.
    autocomplete_fields = ['etablissement', 'plan_abonnement']

    actions = ['action_desactiver', 'action_reactiver']
    # Pourquoi ces actions plutôt que le bouton "Supprimer" classique :
    # Enseignant est protégé (on_delete=PROTECT) par tout son
    # historique — classes, fiches, évaluations, paiements. Dès qu'un
    # enseignant a la moindre activité enregistrée, Django REFUSE la
    # suppression pour ne jamais perdre ces données, et affiche à la
    # place une longue liste d'objets bloquants souvent illisible.
    # La désactivation est le bon outil : l'enseignant perd l'accès
    # à l'application (voir comptes/permissions.py), mais tout son
    # historique reste intact et consultable.

    def action_desactiver(self, request, queryset):
        nombre = queryset.update(est_actif=False)
        self.message_user(
            request,
            f"{nombre} enseignant(s) désactivé(s). Ils ne peuvent plus se "
            f"connecter, mais leurs classes, fiches et notes restent intactes."
        )
    action_desactiver.short_description = "Désactiver (au lieu de supprimer)"

    def action_reactiver(self, request, queryset):
        nombre = queryset.update(est_actif=True)
        self.message_user(request, f"{nombre} enseignant(s) réactivé(s).")
    action_reactiver.short_description = "Réactiver les enseignants sélectionnés"


# ------------------------------------------------------------
# PAIEMENT
# ------------------------------------------------------------
@admin.register(Paiement)
class PaiementAdmin(admin.ModelAdmin):
    list_display = ['enseignant', 'plan', 'montant', 'moyen_paiement', 'statut', 'date_paiement']
    list_filter = ['moyen_paiement', 'statut', 'plan']
    search_fields = ['enseignant__user__username', 'reference_transaction']
    autocomplete_fields = ['enseignant', 'plan']