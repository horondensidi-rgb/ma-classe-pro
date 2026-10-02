# ============================================================
# APP : comptes
# Fichier : models.py
# Rôle : gérer les enseignants, leurs établissements, et leur
#        abonnement à la plateforme "Ma Classe Pro".
# ============================================================
#
# Cette app est la FONDATION du projet : tous les autres modules
# (pedagogie, evaluations, bulletins) auront besoin de savoir
# "quel enseignant" fait "quoi", donc on la construit en premier.

from django.db import models
from django.contrib.auth.models import User
# User est le modèle d'utilisateur fourni par défaut par Django.
# Il gère déjà : username, password (hashé), email, etc.
# On ne le réécrit PAS : on le complète avec un "profil" Enseignant.

from django.core.validators import RegexValidator
# RegexValidator permet de vérifier qu'un champ texte respecte
# un format précis (ici : un numéro de téléphone malien).


# ------------------------------------------------------------
# 1. ETABLISSEMENT
# ------------------------------------------------------------
class Etablissement(models.Model):
    """
    Représente une école (publique ou privée) où enseigne
    un ou plusieurs professeurs utilisant l'application.

    Un même Etablissement peut être lié à PLUSIEURS enseignants
    (c'est pour ça qu'on ne met pas ce champ directement dans User,
    mais qu'on crée une vraie table à part, réutilisable).
    """

    # --- Choix possibles pour le type d'établissement ---
    # Django "choices" = une liste de tuples (valeur_stockée, texte_affiché)
    # La valeur stockée en base est courte (ex: 'PUB'),
    # le texte affiché à l'utilisateur est clair (ex: 'Public').
    TYPE_ETABLISSEMENT_CHOICES = [
        ('PUB', 'Public'),
        ('PRIV', 'Privé'),
        ('COMM', 'Communautaire'),
        ('CONF', 'Confessionnel'),
    ]

    # --- Régions du Mali (liste non exhaustive, à compléter) ---
    REGION_CHOICES = [
        ('KAYES', 'Kayes'),
        ('KOULIKORO', 'Koulikoro'),
        ('SIKASSO', 'Sikasso'),
        ('SEGOU', 'Ségou'),
        ('MOPTI', 'Mopti'),
        ('TOMBOUCTOU', 'Tombouctou'),
        ('GAO', 'Gao'),
        ('KIDAL', 'Kidal'),
        ('MENAKA', 'Ménaka'),
        ('TAOUDENIT', 'Taoudénit'),
        ('BAMAKO', 'District de Bamako'),
    ]

    nom = models.CharField(
        max_length=200,
        help_text="Nom officiel de l'établissement"
    )

    ville = models.CharField(max_length=100)

    region = models.CharField(
        max_length=20,
        choices=REGION_CHOICES,
        default='SIKASSO'
        # Valeur par défaut = ta propre région, pratique pour tes tests.
    )

    type_etablissement = models.CharField(
        max_length=10,
        choices=TYPE_ETABLISSEMENT_CHOICES,
        default='PUB'
    )

    telephone = models.CharField(
        max_length=20,
        blank=True,   # blank=True => champ facultatif dans les formulaires
        null=True     # null=True  => la base de données accepte "vide" (NULL)
    )

    # On garde une trace de quand l'établissement a été ajouté à la plateforme.
    # auto_now_add=True => Django remplit ce champ TOUT SEUL à la création,
    # impossible à modifier ensuite manuellement.
    date_ajout = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Meta = options qui ne créent pas de colonne, mais changent
        # le comportement du modèle (affichage, tri, nom au pluriel...)
        verbose_name = "Établissement"
        verbose_name_plural = "Établissements"
        ordering = ['nom']  # tri alphabétique par défaut dans les listes

    def __str__(self):
        # __str__ définit comment l'objet s'affiche en texte
        # (dans l'admin Django, dans les listes déroulantes, etc.)
        # Sans ça, Django afficherait juste "Etablissement object (1)".
        return f"{self.nom} ({self.get_region_display()})"
        # get_region_display() est une méthode AUTOMATIQUE que Django
        # crée pour tout champ avec "choices" : elle renvoie le texte
        # lisible ('Sikasso') plutôt que le code stocké ('SIKASSO').


# ------------------------------------------------------------
# 2. PLAN D'ABONNEMENT
# ------------------------------------------------------------
class PlanAbonnement(models.Model):
    """
    Définit les différentes offres commerciales de la plateforme
    (Gratuit, Standard, Premium...).

    On sépare ce modèle du modèle Enseignant pour pouvoir gérer
    les plans facilement depuis l'admin Django, sans toucher au code
    (ex: changer un prix, ajouter un nouveau plan).
    """

    NOM_PLAN_CHOICES = [
        ('GRATUIT', 'Gratuit'),
        ('STANDARD', 'Standard'),
        ('PREMIUM', 'Premium'),
        ('ETABLISSEMENT', 'Établissement (multi-enseignants)'),
    ]

    nom = models.CharField(
        max_length=20,
        choices=NOM_PLAN_CHOICES,
        unique=True
        # unique=True => on ne peut pas créer deux plans avec le même nom
    )

    prix_mensuel = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
        # DecimalField (et pas FloatField) pour l'ARGENT : évite les
        # erreurs d'arrondi que les nombres flottants peuvent provoquer.
    )

    nombre_classes_max = models.PositiveIntegerField(
        default=1,
        help_text="Nombre maximum de classes gérables avec ce plan"
        # PositiveIntegerField interdit les valeurs négatives (0, 1, 2... jamais -1)
    )

    acces_ia_preparation = models.BooleanField(
        default=False,
        help_text="Ce plan donne-t-il accès à l'assistance IA pour les fiches ?"
    )

    description = models.TextField(blank=True)

    class Meta:
        verbose_name = "Plan d'abonnement"
        verbose_name_plural = "Plans d'abonnement"

    def __str__(self):
        return f"{self.get_nom_display()} ({self.prix_mensuel} FCFA/mois)"


# ------------------------------------------------------------
# 3. ENSEIGNANT (le profil complémentaire au User Django)
# ------------------------------------------------------------
class Enseignant(models.Model):
    """
    Profil "métier" de l'enseignant, lié au compte de connexion (User).

    Pourquoi séparer User et Enseignant au lieu de tout mettre dans User ?
    -> User gère uniquement l'AUTHENTIFICATION (login/mot de passe).
    -> Enseignant gère les INFOS MÉTIER (établissement, matières, abonnement).
    Cette séparation est une pratique standard en Django : elle permet
    par exemple de créer plus tard d'autres types de comptes (ex: un
    'Directeur' ou un 'Élève') sans complexifier le modèle User.
    """

    # Validateur pour un numéro mobile malien : +223 optionnel, puis
    # 8 chiffres dont le premier est entre 5 et 9.
    #
    # Pourquoi ne PAS viser un opérateur précis (Orange = 7, Malitel/
    # Moov = 6...) : désormais PLUSIEURS opérateurs (Orange Money,
    # Moov Money) font des transactions financières, et leurs plages
    # de préfixes ne sont ni identiques, ni figées dans le temps
    # (un 3ème opérateur, Telecel, est arrivé en 2018 et redistribue
    # encore les plages). Coder une liste précise de préfixes
    # deviendrait vite obsolète et rejetterait des numéros pourtant
    # valides. On valide donc seulement la FORME générale d'un numéro
    # mobile malien, sans présumer de l'opérateur.
    telephone_validator = RegexValidator(
        regex=r'^(\+223)?[5-9]\d{7}$',
        message="Numéro invalide. Format attendu : +22370000000 ou 70000000"
    )

    # --- Lien vers le compte de connexion Django ---
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        # CASCADE ici (pas PROTECT) : si le compte User est supprimé,
        # ça a du sens de supprimer aussi le profil Enseignant qui va avec.
        # (Différent de tes FK vers eleves/classes où tu voulais PROTECT
        # pour ne jamais perdre de données pédagogiques par erreur.)
        related_name='profil_enseignant'
        # related_name permet d'écrire : mon_user.profil_enseignant
        # pour retrouver le profil depuis l'objet User.
    )

    telephone = models.CharField(
        max_length=20,
        validators=[telephone_validator],
        help_text="Numéro Mobile Money (Orange Money / Moov Money)"
    )

    etablissement = models.ForeignKey(
        Etablissement,
        on_delete=models.PROTECT,
        # PROTECT : on garde ta convention. Impossible de supprimer un
        # établissement tant qu'un enseignant y est encore rattaché.
        related_name='enseignants'
    )

    plan_abonnement = models.ForeignKey(
        PlanAbonnement,
        on_delete=models.PROTECT,
        related_name='enseignants'
    )

    date_debut_abonnement = models.DateField(
        null=True,
        blank=True
    )

    date_fin_abonnement = models.DateField(
        null=True,
        blank=True,
        help_text="Date à laquelle l'abonnement actuel expire"
    )

    est_actif = models.BooleanField(
        default=True,
        help_text="Permet de désactiver un compte sans le supprimer"
    )

    date_inscription = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Enseignant"
        verbose_name_plural = "Enseignants"
        ordering = ['user__last_name', 'user__first_name']
        # user__last_name : on traverse la relation vers User pour trier
        # par nom de famille (le double underscore "__" sert à naviguer
        # entre tables liées, aussi bien en tri qu'en filtre).

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} - {self.etablissement.nom}"

    def abonnement_est_valide(self):
        """
        Méthode "métier" : renvoie True/False selon que l'abonnement
        est encore valide aujourd'hui.
        C'est un exemple de logique qu'on met DANS le modèle (et pas
        dans une vue) car elle concerne directement les données de
        l'objet Enseignant lui-même.
        """
        from datetime import date
        if self.date_fin_abonnement is None:
            return False
        return self.date_fin_abonnement >= date.today()


# ------------------------------------------------------------
# 4. HISTORIQUE DES PAIEMENTS (pour le suivi Mobile Money)
# ------------------------------------------------------------
class Paiement(models.Model):
    """
    Trace chaque paiement effectué par un enseignant pour son
    abonnement (Orange Money, Moov Money, etc.).

    Utile pour :
    - vérifier/débugger un paiement contesté
    - générer des statistiques de revenus
    - réactiver automatiquement un abonnement après paiement
    """

    MOYEN_PAIEMENT_CHOICES = [
        ('ORANGE', 'Orange Money'),
        ('MOOV', 'Moov Money'),
        ('ESPECES', 'Espèces'),
        ('AUTRE', 'Autre'),
    ]

    STATUT_CHOICES = [
        ('EN_ATTENTE', 'En attente'),
        ('CONFIRME', 'Confirmé'),
        ('ECHOUE', 'Échoué'),
    ]

    enseignant = models.ForeignKey(
        Enseignant,
        on_delete=models.PROTECT,
        related_name='paiements'
    )

    plan = models.ForeignKey(
        PlanAbonnement,
        on_delete=models.PROTECT
        # On garde une référence au plan payé, même si l'enseignant
        # change de plan plus tard : ceci reste l'historique exact.
    )

    montant = models.DecimalField(max_digits=10, decimal_places=2)

    moyen_paiement = models.CharField(
        max_length=10,
        choices=MOYEN_PAIEMENT_CHOICES
    )

    reference_transaction = models.CharField(
        max_length=100,
        blank=True,
        help_text="Référence renvoyée par l'opérateur Mobile Money"
    )

    statut = models.CharField(
        max_length=15,
        choices=STATUT_CHOICES,
        default='EN_ATTENTE'
    )

    date_paiement = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Paiement"
        verbose_name_plural = "Paiements"
        ordering = ['-date_paiement']
        # Le "-" devant le nom du champ = tri décroissant
        # (le paiement le plus récent apparaît en premier).

    def __str__(self):
        return f"{self.enseignant} - {self.montant} FCFA ({self.get_statut_display()})"