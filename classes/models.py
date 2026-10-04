# ============================================================
# APP : classes. NEW 4/10 22H 28
# Fichier : models.py
# Rôle : gérer les années scolaires, les classes, les matières
#        et les élèves de chaque enseignant.
# ============================================================
#
# Cette app dépend de l'app "comptes" (Enseignant, Etablissement)
# créée précédemment. On l'importe donc ici.

from django.db import models
from comptes.models import Enseignant, Etablissement
# ⚠️ Rappel : pour que cet import fonctionne, l'app "comptes" doit
# être listée AVANT "classes" dans INSTALLED_APPS (settings.py),
# et "comptes" doit déjà être migrée.


# ------------------------------------------------------------
# 1. ANNEE SCOLAIRE
# ------------------------------------------------------------
class AnneeScolaire(models.Model):
    """
    Représente une année scolaire complète (ex: 2025-2026).

    Pourquoi un modèle à part et pas juste un champ "année" sur Classe ?
    -> Une année scolaire a ses propres dates de début/fin, son statut
       "active ou archivée", et sera réutilisée par PLUSIEURS modèles
       plus tard (classes, évaluations, bulletins). La centraliser ici
       évite de répéter/incohérence des dates partout.
    """

    libelle = models.CharField(
        max_length=20,
        unique=True,
        help_text="Exemple : 2025-2026"
    )

    date_debut = models.DateField()
    date_fin = models.DateField()

    est_active = models.BooleanField(
        default=False,
        help_text="Une seule année scolaire doit être 'active' à la fois"
    )

    class Meta:
        verbose_name = "Année scolaire"
        verbose_name_plural = "Années scolaires"
        ordering = ['-date_debut']  # la plus récente en premier

    def __str__(self):
        return self.libelle

    def save(self, *args, **kwargs):
        """
        On surcharge (= on redéfinit) la méthode save() pour garantir
        qu'une seule AnneeScolaire est active en même temps.

        Logique : si CETTE année est marquée active, on désactive
        automatiquement TOUTES les autres avant de sauvegarder.
        C'est une règle métier importante à protéger au niveau du
        modèle (et pas seulement dans un formulaire), pour qu'elle
        s'applique peu importe d'où vient la modification (admin,
        vue, script...).
        """
        if self.est_active:
            # On met à jour toutes les AUTRES années (exclude(pk=self.pk))
            # pour les repasser à est_active=False.
            AnneeScolaire.objects.exclude(pk=self.pk).update(est_active=False)
        # super().save() appelle le comportement normal de Django
        # APRÈS notre vérification personnalisée.
        super().save(*args, **kwargs)


# ------------------------------------------------------------
# 2. MATIERE
# ------------------------------------------------------------
class Matiere(models.Model):
    """
    Une matière enseignée (Français, Mathématiques, Histoire-Géo...).

    On la sépare de "Classe" car une même matière (ex: Français) est
    enseignée dans PLUSIEURS classes différentes : c'est une relation
    "plusieurs-à-plusieurs" qu'on gérera via le modèle Classe ci-dessous.
    """

    nom = models.CharField(max_length=100, unique=True)

    code = models.CharField(
        max_length=10,
        blank=True,
        help_text="Code court, ex : FR, MATH, HG"
    )

    coefficient_defaut = models.PositiveIntegerField(
        default=1,
        help_text="Coefficient standard de cette matière (modifiable par classe si besoin)"
    )

    class Meta:
        verbose_name = "Matière"
        verbose_name_plural = "Matières"
        ordering = ['nom']

    def __str__(self):
        return self.nom


# ------------------------------------------------------------
# 3. CLASSE
# ------------------------------------------------------------
class Classe(models.Model):
    """
    Une classe concrète pour une année scolaire donnée
    (ex : "7ème A - 2025-2026").

    Remarque de conception : on lie la classe à l'ANNÉE SCOLAIRE
    (pas seulement au niveau "7ème") car les effectifs, motifs
    d'évaluation, etc. changent chaque année, même si le niveau
    reste "7ème".
    """

    NIVEAU_CHOICES = [
        ('7EME', '7ème année'),
        ('8EME', '8ème année'),
        ('9EME', '9ème année'),
        # Tu pourras compléter avec le lycée (10e, 11e, 12e) plus tard,
        # ou même le fondamental 1er cycle si tu élargis l'app.
    ]

    nom = models.CharField(
        max_length=50,
        help_text="Exemple : 7ème A"
    )

    niveau = models.CharField(
        max_length=10,
        choices=NIVEAU_CHOICES
    )

    annee_scolaire = models.ForeignKey(
        AnneeScolaire,
        on_delete=models.PROTECT,
        related_name='classes'
    )

    etablissement = models.ForeignKey(
        Etablissement,
        on_delete=models.PROTECT,
        related_name='classes'
    )

    enseignant_principal = models.ForeignKey(
        Enseignant,
        on_delete=models.PROTECT,
        related_name='classes_principales',
        null=True,
        blank=True,
        help_text="Enseignant responsable de cette classe (si applicable)"
    )

    # Relation "plusieurs-à-plusieurs" avec Matiere :
    # une classe a plusieurs matières, une matière est utilisée
    # dans plusieurs classes.
    matieres = models.ManyToManyField(
        Matiere,
        through='ClasseMatiere',
        # "through" indique qu'on passe par un modèle intermédiaire
        # personnalisé (ClasseMatiere ci-dessous) plutôt qu'une table
        # automatique invisible. On fait ça car on veut stocker des
        # infos SUPPLÉMENTAIRES sur cette relation (le coefficient,
        # l'enseignant qui donne cette matière dans cette classe...).
        related_name='classes'
    )

    class Meta:
        verbose_name = "Classe"
        verbose_name_plural = "Classes"
        ordering = ['annee_scolaire', 'niveau', 'nom']
        unique_together = ['nom', 'annee_scolaire', 'etablissement']
        # unique_together : empêche de créer deux fois "7ème A" pour
        # le même établissement et la même année scolaire (doublon).

    def __str__(self):
        return f"{self.nom} ({self.annee_scolaire.libelle})"


# ------------------------------------------------------------
# 4. TABLE INTERMEDIAIRE : ClasseMatiere
# ------------------------------------------------------------
class ClasseMatiere(models.Model):
    """
    Table de liaison entre Classe et Matiere.

    C'est ici qu'on précise, POUR CETTE classe et CETTE matière :
    - quel enseignant la dispense
    - quel coefficient s'applique (peut différer du coefficient_defaut)

    Exemple concret : le Français en 7ème A peut avoir un coefficient
    différent du Français en 9ème A, même si c'est "la même matière".
    """

    classe = models.ForeignKey(Classe, on_delete=models.CASCADE)
    # CASCADE ici (pas PROTECT) : si on supprime carrément la Classe,
    # ça n'a plus de sens de garder cette ligne de liaison orpheline.

    matiere = models.ForeignKey(Matiere, on_delete=models.PROTECT)

    enseignant = models.ForeignKey(
        Enseignant,
        on_delete=models.PROTECT,
        related_name='matieres_enseignees'
    )

    coefficient = models.PositiveIntegerField(
        default=1,
        help_text="Coefficient de cette matière dans CETTE classe précise"
    )

    class Meta:
        verbose_name = "Attribution matière-classe"
        verbose_name_plural = "Attributions matière-classe"
        unique_together = ['classe', 'matiere']
        # Empêche d'ajouter deux fois la même matière dans la même classe.

    def __str__(self):
        return f"{self.matiere.nom} - {self.classe.nom} (coef {self.coefficient})"


# ------------------------------------------------------------
# 5. ELEVE
# ------------------------------------------------------------
class Eleve(models.Model):
    """
    Un élève inscrit dans une classe pour une année scolaire donnée.

    Remarque : si un élève redouble ou change de classe l'année
    suivante, on considère que c'est une NOUVELLE ligne Eleve liée
    à la nouvelle Classe (plutôt que de changer la classe de la ligne
    existante), pour conserver l'historique de son parcours.
    Si tu préfères plutôt un modèle "Personne" unique + un modèle
    "Inscription" séparé par année, on peut aussi le faire — dis-moi
    si tu veux cette variante, plus robuste pour le suivi pluriannuel.
    """

    SEXE_CHOICES = [
        ('M', 'Masculin'),
        ('F', 'Féminin'),
    ]

    matricule = models.CharField(
        max_length=30,
        unique=True,
        help_text="Numéro d'identification unique de l'élève"
    )

    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100)

    sexe = models.CharField(max_length=1, choices=SEXE_CHOICES)

    date_naissance = models.DateField(null=True, blank=True)

    lieu_naissance = models.CharField(max_length=150, blank=True)

    classe = models.ForeignKey(
        Classe,
        on_delete=models.PROTECT,
        related_name='eleves'
    )

    nom_tuteur = models.CharField(
        max_length=150,
        blank=True,
        help_text="Nom du parent ou tuteur légal"
    )

    telephone_tuteur = models.CharField(
        max_length=20,
        blank=True,
        help_text="Utile pour les notifications SMS/WhatsApp de résultats"
    )

    est_actif = models.BooleanField(
        default=True,
        help_text="False si l'élève a quitté l'établissement en cours d'année"
    )

    date_inscription = models.DateTimeField(auto_now_add=True)

    compte_utilisateur = models.OneToOneField(
        'auth.User',
        on_delete=models.SET_NULL,
        # SET_NULL (pas PROTECT ni CASCADE) : si ce compte de connexion
        # est un jour supprimé, l'Eleve lui-même doit continuer
        # d'exister normalement (ses notes, son dossier...) — il perd
        # juste la possibilité de se connecter, rien de plus grave.
        null=True,
        blank=True,
        related_name='profil_eleve',
        help_text="Compte de connexion optionnel, donnant accès à "
                   "l'espace élève (évaluations en ligne). Créé par "
                   "l'enseignant depuis la fiche de l'élève, pas à "
                   "l'inscription — tous les élèves n'en ont pas besoin."
    )

    class Meta:
        verbose_name = "Élève"
        verbose_name_plural = "Élèves"
        ordering = ['classe', 'nom', 'prenom']

    def __str__(self):
        return f"{self.nom} {self.prenom} ({self.classe.nom})"

    @property
    def nom_complet(self):
        """
        @property permet d'appeler cette méthode SANS parenthèses,
        comme un simple attribut : mon_eleve.nom_complet
        au lieu de mon_eleve.nom_complet()
        Pratique pour un raccourci utilisé souvent dans les templates.
        """
        return f"{self.nom} {self.prenom}"


# ------------------------------------------------------------
# 6. JOURNAL DE CONSULTATION (audit)
# ------------------------------------------------------------
class JournalConsultation(models.Model):
    """
    Trace CHAQUE consultation de la fiche d'un élève — qui l'a
    ouverte, quand, et depuis quelle interface (espace enseignant
    ou admin Django).

    Pourquoi ce modèle existe : les données d'un élève (date de
    naissance, contact du tuteur...) sont des données personnelles
    de mineur. Le propriétaire de la plateforme a un accès technique
    total via l'admin, ce qui est normal (il héberge et maintient le
    site), mais ça doit être TRAÇABLE : en cas de doute ou de demande
    d'une école, il doit pouvoir prouver que les consultations
    enregistrées correspondent à un usage légitime (support,
    débogage), jamais à une curiosité injustifiée.

    Ce journal n'enregistre QUE la LECTURE. Les modifications (ajout,
    changement, suppression) sont déjà tracées automatiquement par
    Django lui-même dans la table interne admin.LogEntry — inutile
    de dupliquer ce que Django fait déjà bien.
    """

    ORIGINE_CHOICES = [
        ('ENSEIGNANT', 'Espace enseignant'),
        ('ADMIN', "Interface d'administration"),
    ]

    utilisateur = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        # SET_NULL (pas CASCADE) : si le compte qui a consulté la
        # fiche est un jour supprimé, on garde quand même la TRACE
        # que CETTE fiche a été consultée à CETTE date — seule
        # l'identité de qui l'a fait devient "Utilisateur supprimé".
        # Supprimer la ligne entière reviendrait à effacer une partie
        # de l'historique d'audit, ce qui irait à l'encontre de son
        # utilité même.
        null=True,
        related_name='consultations_effectuees'
    )

    eleve = models.ForeignKey(
        Eleve,
        on_delete=models.CASCADE,
        related_name='consultations'
    )

    origine = models.CharField(max_length=12, choices=ORIGINE_CHOICES)

    date_consultation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Consultation d'élève"
        verbose_name_plural = "Journal des consultations"
        ordering = ['-date_consultation']

    def __str__(self):
        nom_utilisateur = self.utilisateur.username if self.utilisateur else "Utilisateur supprimé"
        return (
            f"{nom_utilisateur} \u2192 {self.eleve.nom_complet} "
            f"({self.date_consultation:%d/%m/%Y %H:%M})"
        )
