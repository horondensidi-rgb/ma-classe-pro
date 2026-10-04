# ============================================================
# APP : classes NEW 4/10 22H 28
# Fichier : admin.py
# Rôle : rendre AnneeScolaire, Matiere, Classe, ClasseMatiere
#        et Eleve gérables depuis l'admin, avec search_fields
#        sur chacun — INDISPENSABLE car d'autres apps (bulletins,
#        evaluations) utilisent autocomplete_fields pointant vers
#        ces modèles. Sans search_fields ici, Django refuse de
#        démarrer (erreur admin.E040).
# ============================================================

from django.contrib import admin
from .models import AnneeScolaire, Matiere, Classe, ClasseMatiere, Eleve, JournalConsultation


# ------------------------------------------------------------
# ANNEE SCOLAIRE
# ------------------------------------------------------------
@admin.register(AnneeScolaire)
class AnneeScolaireAdmin(admin.ModelAdmin):
    list_display = ['libelle', 'date_debut', 'date_fin', 'est_active']
    list_filter = ['est_active']
    search_fields = ['libelle']
    # search_fields est court ici, mais sa présence suffit à satisfaire
    # Django si un jour un autre modèle pointe vers AnneeScolaire en
    # autocomplete_fields.


# ------------------------------------------------------------
# MATIERE
# ------------------------------------------------------------
@admin.register(Matiere)
class MatiereAdmin(admin.ModelAdmin):
    list_display = ['nom', 'code', 'coefficient_defaut']
    search_fields = ['nom', 'code']


# ------------------------------------------------------------
# INLINE : gérer les ClasseMatiere directement depuis la page Classe
# ------------------------------------------------------------
class ClasseMatiereInline(admin.TabularInline):
    """
    Permet d'ajouter/modifier les matières d'une classe (avec leur
    enseignant et coefficient) directement sur la page de la Classe,
    sans devoir créer chaque ClasseMatiere séparément.
    """
    model = ClasseMatiere
    extra = 1
    fields = ['matiere', 'enseignant', 'coefficient']
    autocomplete_fields = ['matiere', 'enseignant']
    # ⚠️ Ceci exige que MatiereAdmin (ci-dessus) ET EnseignantAdmin
    # (dans comptes/admin.py) définissent bien search_fields.


# ------------------------------------------------------------
# CLASSE
# ------------------------------------------------------------
@admin.register(Classe)
class ClasseAdmin(admin.ModelAdmin):
    list_display = ['nom', 'niveau', 'annee_scolaire', 'etablissement', 'enseignant_principal']
    list_filter = ['annee_scolaire', 'niveau', 'etablissement']
    search_fields = ['nom']
    autocomplete_fields = ['annee_scolaire', 'etablissement', 'enseignant_principal']
    inlines = [ClasseMatiereInline]


# ------------------------------------------------------------
# CLASSE-MATIERE (accès direct, en plus de l'inline ci-dessus)
# ------------------------------------------------------------
@admin.register(ClasseMatiere)
class ClasseMatiereAdmin(admin.ModelAdmin):
    """
    C'est CE search_fields qui manquait et qui bloquait
    bulletins/admin.py (LigneBulletinInline et LigneBulletinAdmin
    pointent vers ClasseMatiere en autocomplete_fields).
    """
    list_display = ['classe', 'matiere', 'enseignant', 'coefficient']
    list_filter = ['classe', 'matiere']
    search_fields = ['classe__nom', 'matiere__nom', 'enseignant__user__last_name']
    # On peut chercher via le nom de la classe, de la matière, OU
    # le nom de famille de l'enseignant (en traversant deux relations
    # avec un double "__" : enseignant -> user -> last_name).
    autocomplete_fields = ['classe', 'matiere', 'enseignant']


# ------------------------------------------------------------
# ELEVE
# ------------------------------------------------------------
@admin.register(Eleve)
class EleveAdmin(admin.ModelAdmin):
    """
    C'est CE search_fields qui manquait et qui bloquait
    bulletins/admin.py (BulletinAdmin.autocomplete_fields = ['eleve', ...]).
    """
    list_display = ['matricule', 'nom', 'prenom', 'classe', 'sexe', 'est_actif', 'a_un_acces_affichage']
    list_filter = ['classe', 'sexe', 'est_actif']
    search_fields = ['matricule', 'nom', 'prenom']
    autocomplete_fields = ['classe']

    def a_un_acces_affichage(self, obj):
        return obj.compte_utilisateur is not None
    a_un_acces_affichage.short_description = "Accès élève"
    a_un_acces_affichage.boolean = True
    # boolean = True : Django affiche une icône ✓/✗ au lieu de
    # "True"/"False" en texte brut, plus lisible dans la liste.

    actions = ['action_desactiver', 'action_reactiver']
    # Même raisonnement que EnseignantAdmin (voir comptes/admin.py) :
    # Eleve est protégé par Copie et Bulletin. La désactivation
    # (déjà utilisée côté interface enseignant — voir
    # classes/views.py, desactiver_eleve_view) est ici accessible
    # en MASSE, pratique en fin d'année pour retirer d'un coup tous
    # les élèves qui ont quitté l'établissement.

    def action_desactiver(self, request, queryset):
        nombre = queryset.update(est_actif=False)
        self.message_user(
            request,
            f"{nombre} élève(s) désactivé(s). Leur historique (notes, "
            f"bulletins) reste conservé."
        )
    action_desactiver.short_description = "Désactiver (au lieu de supprimer)"

    def action_reactiver(self, request, queryset):
        nombre = queryset.update(est_actif=True)
        self.message_user(request, f"{nombre} élève(s) réactivé(s).")
    action_reactiver.short_description = "Réactiver les élèves sélectionnés"

    def change_view(self, request, object_id, form_url='', extra_context=None):
        """
        On surcharge cette méthode (fournie par Django, appelée à
        chaque fois que l'admin OUVRE la fiche d'un objet, qu'il la
        modifie ou non) pour y glisser une ligne de journal — c'est
        le point d'entrée précis qui correspond à "un humain a
        regardé les données de cet élève dans l'admin".
        """
        eleve = Eleve.objects.filter(pk=object_id).first()
        if eleve:
            JournalConsultation.objects.create(
                utilisateur=request.user,
                eleve=eleve,
                origine='ADMIN',
            )
        return super().change_view(request, object_id, form_url, extra_context)


# ------------------------------------------------------------
# JOURNAL DE CONSULTATION (lecture seule — c'est un audit, pas une
# donnée qu'on doit pouvoir modifier ou supprimer au coup par coup)
# ------------------------------------------------------------
@admin.register(JournalConsultation)
class JournalConsultationAdmin(admin.ModelAdmin):
    list_display = ['date_consultation', 'utilisateur', 'eleve', 'origine']
    list_filter = ['origine', 'date_consultation']
    search_fields = ['eleve__matricule', 'eleve__nom', 'eleve__prenom', 'utilisateur__username']
    date_hierarchy = 'date_consultation'

    def has_add_permission(self, request):
        # Une consultation ne se "crée" jamais à la main : elle est
        # TOUJOURS générée automatiquement par le code lui-même.
        return False

    def has_change_permission(self, request, obj=None):
        # Un journal d'audit qu'on pourrait modifier après coup ne
        # prouve plus rien — il doit rester intouchable une fois écrit.
        return False

    def has_delete_permission(self, request, obj=None):
        return False
