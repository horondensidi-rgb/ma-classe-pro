# ============================================================
# APP : pedagogie
# Fichier : models.py
# Rôle : gérer les séquences pédagogiques et les fiches de
#        préparation de cours (le vrai différenciateur de l'app),
#        conformes aux méthodologies officielles maliennes
#        (6 étapes grammaire, 8 étapes conjugaison...).
# ============================================================
#
# Cette app dépend de "comptes" (Enseignant) et de "classes"
# (Classe, ClasseMatiere).

from django.db import models
from comptes.models import Enseignant
from classes.models import Classe, ClasseMatiere


# ------------------------------------------------------------
# 1. SEQUENCE PEDAGOGIQUE
# ------------------------------------------------------------
class Sequence(models.Model):
    """
    Une séquence regroupe plusieurs fiches de préparation autour
    d'un même thème, sur une période donnée (souvent liée à un
    trimestre).

    Exemple : Séquence 3 - "Le passé composé" en 8ème, qui contiendra
    plusieurs fiches (grammaire, conjugaison, lecture...) toutes
    reliées à ce même thème.
    """

    TRIMESTRE_CHOICES = [
        (1, '1er trimestre'),
        (2, '2ème trimestre'),
        (3, '3ème trimestre'),
    ]

    classe = models.ForeignKey(
        Classe,
        on_delete=models.PROTECT,
        related_name='sequences'
    )

    numero = models.PositiveIntegerField(
        help_text="Numéro d'ordre de la séquence dans l'année (1, 2, 3...)"
    )

    titre = models.CharField(
        max_length=200,
        help_text="Exemple : Le passé composé"
    )

    trimestre = models.PositiveSmallIntegerField(choices=TRIMESTRE_CHOICES)

    date_debut = models.DateField(null=True, blank=True)
    date_fin = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name = "Séquence"
        verbose_name_plural = "Séquences"
        ordering = ['classe', 'trimestre', 'numero']
        unique_together = ['classe', 'numero', 'trimestre']
        # Empêche deux séquences avec le même numéro dans le même
        # trimestre pour la même classe (incohérence de numérotation).

    def __str__(self):
        return f"Séquence {self.numero} - {self.titre} ({self.classe.nom})"


# ------------------------------------------------------------
# 2. FICHE DE PREPARATION
# ------------------------------------------------------------
class FichePreparation(models.Model):
    """
    Une fiche de préparation de cours, conforme au format officiel
    malien : Discipline, Classe, Durée, R.L.P. (Rappel/Leçon
    Précédente), O.P.O. (Objectif Pédagogique Opérationnel),
    puis un déroulement en étapes (voir modèle EtapeFiche plus bas).

    Le CONTENU détaillé des étapes est stocké dans un modèle séparé
    (EtapeFiche) plutôt que dans un seul gros champ texte ici, car :
    - le nombre d'étapes change selon le type de leçon
      (6 pour la grammaire, 8 pour la conjugaison, etc.)
    - ça permet d'afficher/modifier chaque étape indépendamment
      dans un formulaire, plutôt qu'un bloc de texte unique.
    """

    TYPE_LECON_CHOICES = [
        ('GRAMMAIRE', 'Grammaire'),
        ('CONJUGAISON', 'Conjugaison'),
        ('LECTURE', 'Lecture'),
        ('EXPRESSION_ECRITE', 'Expression écrite'),
        ('ORTHOGRAPHE', 'Orthographe'),
        ('VOCABULAIRE', 'Vocabulaire'),
        ('DICTEE_PREPAREE', 'Dictée préparée'),
        ('DICTEE_CONTROLE', 'Dictée de contrôle'),
        ('MATHEMATIQUES', 'Mathématiques'),
		('CALCUL', 'Calcul'),
		('PHYSIQUE', 'Physique'),
		('CHIMIE', 'Chimie'),
		('MUSIQUE', 'Musique'),
		('REDACTION', 'Rédaction'),
		('RECITATION', 'Récitation'),
		('SPORT', 'Sport'),
		('BIOLOGIE', 'Biologie'),
		('AUTRE', 'Autre'),
    ]

    STATUT_CHOICES = [
        ('BROUILLON', 'Brouillon'),
        ('FINALISEE', 'Finalisée'),
        ('DISPENSEE', 'Dispensée (cours donné)'),
    ]

    # Nombre d'étapes du déroulement attendu selon la méthodologie
    # officielle malienne, utilisé pour pré-afficher le bon nombre
    # de lignes vides quand l'enseignant saisit le déroulement d'une
    # fiche (voir pedagogie/views.py, modifier_etapes_view). Les
    # types absents de ce dictionnaire utilisent NOMBRE_ETAPES_DEFAUT.
    NOMBRE_ETAPES_PAR_TYPE = {
        'GRAMMAIRE': 6,
        'CONJUGAISON': 8,
    }
    NOMBRE_ETAPES_DEFAUT = 5

    enseignant = models.ForeignKey(
        Enseignant,
        on_delete=models.PROTECT,
        related_name='fiches'
    )

    classe_matiere = models.ForeignKey(
        ClasseMatiere,
        on_delete=models.PROTECT,
        related_name='fiches',
        help_text="Précise à la fois la classe ET la matière concernées"
    )

    sequence = models.ForeignKey(
        Sequence,
        on_delete=models.PROTECT,
        related_name='fiches',
        null=True,
        blank=True,
        help_text="Optionnel : rattacher cette fiche à une séquence existante"
    )

    type_lecon = models.CharField(
        max_length=20,
        choices=TYPE_LECON_CHOICES
    )

    titre = models.CharField(
        max_length=200,
        help_text="Titre précis de la leçon, ex : Le passé composé des verbes du 1er groupe"
    )

    duree_minutes = models.PositiveIntegerField(
        default=60,
        help_text="Durée prévue du cours en minutes"
    )

    rappel_lecon_precedente = models.TextField(
        blank=True,
        verbose_name="R.L.P. (Rappel de la leçon précédente)"
    )

    objectif_pedagogique_operationnel = models.TextField(
        verbose_name="O.P.O. (Objectif Pédagogique Opérationnel)",
        help_text="Ce que l'élève doit être capable de faire à la fin du cours"
    )

    date_prevue = models.DateField(
        null=True,
        blank=True,
        help_text="Date prévue pour dispenser ce cours"
    )

    statut = models.CharField(
        max_length=15,
        choices=STATUT_CHOICES,
        default='BROUILLON'
    )

    genere_par_ia = models.BooleanField(
        default=False,
        help_text="True si cette fiche a été générée avec l'assistance IA"
    )

    fichier_pdf = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        help_text="Chemin du fichier PDF exporté (on stocke le chemin, "
                   "pas le fichier binaire, comme convenu pour ce projet)"
    )

    date_creation = models.DateTimeField(auto_now_add=True)
    # auto_now_add : rempli une seule fois, à la création.

    date_modification = models.DateTimeField(auto_now=True)
    # auto_now (sans _add) : mis à jour AUTOMATIQUEMENT à CHAQUE
    # sauvegarde, contrairement à auto_now_add. Utile pour savoir
    # quand la fiche a été modifiée pour la dernière fois.

    class Meta:
        verbose_name = "Fiche de préparation"
        verbose_name_plural = "Fiches de préparation"
        ordering = ['-date_prevue', '-date_creation']

    def __str__(self):
        return f"{self.titre} - {self.classe_matiere.classe.nom} ({self.get_type_lecon_display()})"


# ------------------------------------------------------------
# 3. ETAPE DE LA FICHE (le déroulement pas-à-pas)
# ------------------------------------------------------------
class EtapeFiche(models.Model):
    """
    Une étape du déroulement d'une fiche de préparation.

    Ce modèle est volontairement GÉNÉRIQUE (pas un champ par étape
    fixe dans FichePreparation) pour s'adapter à N'IMPORTE QUELLE
    méthodologie :
    - Grammaire malienne : 6 étapes fixes
    - Conjugaison malienne : 8 étapes fixes
    - Une future matière avec un nombre d'étapes différent

    On stocke donc juste "numero_ordre" + le contenu, et c'est la
    LOGIQUE APPLICATIVE (pas la base de données) qui connaît, pour
    chaque type_lecon, les intitulés officiels des étapes (ex: étape 1
    = "Rappel", étape 2 = "Motivation", etc. pour la grammaire).
    """

    fiche = models.ForeignKey(
        FichePreparation,
        on_delete=models.CASCADE,
        # CASCADE : si on supprime la fiche entière, ses étapes
        # n'ont plus aucune raison d'exister toutes seules.
        related_name='etapes'
    )

    numero_ordre = models.PositiveIntegerField(
        help_text="Position de l'étape dans le déroulement (1, 2, 3...)"
    )

    titre_etape = models.CharField(
        max_length=150,
        help_text="Exemple : Motivation, Observation, Conceptualisation..."
    )

    activite_maitre = models.TextField(
        verbose_name="Activité du maître",
        blank=True
    )

    activite_eleve = models.TextField(
        verbose_name="Activité de l'élève",
        blank=True
    )

    duree_minutes = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Durée indicative de cette étape précise"
    )

    class Meta:
        verbose_name = "Étape de fiche"
        verbose_name_plural = "Étapes de fiche"
        ordering = ['fiche', 'numero_ordre']
        unique_together = ['fiche', 'numero_ordre']
        # Empêche d'avoir deux fois l'étape n°3 dans la même fiche.

    def __str__(self):
        return f"Étape {self.numero_ordre} - {self.titre_etape} ({self.fiche.titre})"