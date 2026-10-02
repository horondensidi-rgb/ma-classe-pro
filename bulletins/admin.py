# ============================================================
# APP : bulletins
# Fichier : admin.py
# Rôle : rendre les modèles Bulletin et LigneBulletin gérables
#        depuis l'interface d'administration Django, avec un
#        affichage pratique pour un usage quotidien (pas juste
#        un enregistrement basique).
# ============================================================

from django.contrib import admin
from .models import Bulletin, LigneBulletin


# ------------------------------------------------------------
# INLINE : permet d'éditer les LigneBulletin DIRECTEMENT
# depuis la page du Bulletin parent, sans naviguer ailleurs.
# ------------------------------------------------------------
class LigneBulletinInline(admin.TabularInline):
    """
    TabularInline affiche les lignes liées sous forme de petit
    tableau compact, directement intégré dans la page d'admin
    du Bulletin. C'est beaucoup plus pratique que de devoir
    ouvrir chaque LigneBulletin séparément pour saisir les
    moyennes matière par matière.
    """

    model = LigneBulletin

    extra = 1
    # extra = 1 : Django affiche 1 ligne vide supplémentaire par
    # défaut, prête à remplir, en plus des lignes déjà existantes.

    fields = [
        'classe_matiere', 'moyenne_devoirs', 'moyenne_composition',
        'moyenne', 'moyenne_coefficiee_affichage', 'rang_matiere', 'appreciation'
    ]
    readonly_fields = ['moyenne_devoirs', 'moyenne_composition', 'moyenne', 'moyenne_coefficiee_affichage']
    # readonly_fields : ces valeurs sont calculées par
    # calculer_moyenne_depuis_copies() (ou dérivées via @property),
    # jamais saisies à la main — on les affiche pour vérification,
    # sans permettre de les modifier directement et créer une
    # incohérence avec les notes réelles.

    def moyenne_coefficiee_affichage(self, obj):
        # Un TabularInline ne peut pas afficher directement une
        # @property du modèle dans 'fields' : il faut passer par
        # une petite méthode wrapper comme celle-ci, enregistrée
        # elle aussi dans fields ET readonly_fields.
        return obj.moyenne_coefficiee
    moyenne_coefficiee_affichage.short_description = "Moy. coéf."

    autocomplete_fields = ['classe_matiere']
    # autocomplete_fields : remplace le simple menu déroulant par
    # une barre de recherche - très utile car ClasseMatiere peut
    # vite contenir beaucoup d'entrées (une par matière/classe).
    # ⚠️ Pour que ça fonctionne, il faut que ClasseMatiereAdmin
    # (dans classes/admin.py) définisse bien search_fields.


# ------------------------------------------------------------
# ADMIN : Bulletin
# ------------------------------------------------------------
@admin.register(Bulletin)
# @admin.register(...) est un "décorateur" : une écriture plus
# courte et moderne, équivalente à faire ensuite manuellement
# admin.site.register(Bulletin, BulletinAdmin) tout en bas du fichier.
class BulletinAdmin(admin.ModelAdmin):

    list_display = [
        'eleve',
        'classe',
        'trimestre',
        'moyenne_generale',
        'rang',
        'effectif_classe',
        'statut',
    ]
    # list_display : les colonnes visibles dans la liste des
    # bulletins (au lieu du simple "Bulletin object (1)" par défaut).

    list_filter = ['classe', 'trimestre', 'statut']
    # list_filter : ajoute des filtres cliquables sur le côté droit
    # de la page (ex : afficher uniquement le 2ème trimestre de la
    # classe 8ème A).

    search_fields = ['eleve__nom', 'eleve__prenom', 'eleve__matricule']
    # search_fields : active la barre de recherche en haut de la page.
    # eleve__nom (double underscore) = on cherche dans le champ "nom"
    # de l'objet Eleve LIÉ au bulletin, pas un champ direct de Bulletin.

    autocomplete_fields = ['eleve', 'classe']

    readonly_fields = ['date_generation']
    # readonly_fields : champ visible mais non modifiable à la main
    # dans le formulaire (il est rempli par le code, pas par saisie).

    inlines = [LigneBulletinInline]
    # On rattache l'inline défini plus haut : les lignes de matières
    # apparaîtront directement sous le formulaire du bulletin.

    actions = ['action_recalculer_moyennes', 'action_calculer_classement']
    # actions : ajoute des opérations groupées, sélectionnables via
    # les cases à cocher dans la liste (menu déroulant "Actions").

    def action_recalculer_moyennes(self, request, queryset):
        """
        Action d'admin : recalcule la moyenne générale de chaque
        bulletin sélectionné, à partir de ses LigneBulletin.

        'queryset' contient uniquement les bulletins que l'utilisateur
        a cochés dans la liste avant de lancer l'action.
        """
        compteur = 0
        for bulletin in queryset:
            resultat = bulletin.calculer_moyenne_generale()
            if resultat is not None:
                compteur += 1

        # self.message_user affiche un message de confirmation en haut
        # de la page admin après l'exécution de l'action (comme un
        # message flash classique).
        self.message_user(
            request,
            f"{compteur} bulletin(s) recalculé(s) avec succès."
        )
    action_recalculer_moyennes.short_description = "Recalculer la moyenne générale"
    # short_description : le texte affiché dans le menu déroulant
    # des actions (sinon Django afficherait le nom brut de la fonction).

    def action_calculer_classement(self, request, queryset):
        """
        Action d'admin : calcule le classement (rang) pour TOUTES
        les classes/trimestres représentés dans la sélection.

        On utilise un 'set' de tuples (classe, trimestre) pour ne
        lancer le calcul qu'UNE seule fois par combinaison, même si
        plusieurs bulletins de la même classe/trimestre sont cochés.
        """
        combinaisons_traitees = set()

        for bulletin in queryset:
            cle = (bulletin.classe_id, bulletin.trimestre)
            if cle not in combinaisons_traitees:
                Bulletin.calculer_classement(bulletin.classe, bulletin.trimestre)
                combinaisons_traitees.add(cle)

        self.message_user(
            request,
            f"Classement recalculé pour {len(combinaisons_traitees)} "
            f"combinaison(s) classe/trimestre."
        )
    action_calculer_classement.short_description = "Calculer le classement (rang)"


# ------------------------------------------------------------
# ADMIN : LigneBulletin (accès direct, en plus de l'inline)
# ------------------------------------------------------------
@admin.register(LigneBulletin)
class LigneBulletinAdmin(admin.ModelAdmin):
    """
    On garde aussi un accès direct aux LigneBulletin (en plus de
    l'inline dans Bulletin), pratique si tu veux un jour filtrer/
    corriger en masse toutes les lignes d'UNE matière précise,
    tous bulletins confondus.
    """

    list_display = ['bulletin', 'classe_matiere', 'moyenne_devoirs', 'moyenne_composition', 'moyenne', 'moyenne_coefficiee_affichage', 'rang_matiere']

    def moyenne_coefficiee_affichage(self, obj):
        return obj.moyenne_coefficiee
    moyenne_coefficiee_affichage.short_description = "Moy. coéf."

    list_filter = ['classe_matiere__matiere', 'classe_matiere__classe']

    search_fields = [
        'bulletin__eleve__nom',
        'bulletin__eleve__prenom',
    ]

    autocomplete_fields = ['bulletin', 'classe_matiere']