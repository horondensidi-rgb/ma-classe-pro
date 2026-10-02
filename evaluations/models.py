# ============================================================
# APP : evaluations
# Fichier : models.py
# Rôle : gérer les devoirs/compositions, permettre leur mise en
#        ligne pour les élèves (QCM auto-corrigés + réponses
#        libres notées manuellement), et stocker les résultats.
# ============================================================
#
# Cette app dépend de "classes" (ClasseMatiere, Eleve)
# et de "pedagogie" (Sequence, pour rattacher une évaluation
# à un thème déjà préparé en cours).

from django.db import models
from django.utils import timezone
from classes.models import ClasseMatiere, Eleve
from pedagogie.models import Sequence


# ------------------------------------------------------------
# 1. EVALUATION
# ------------------------------------------------------------
class Evaluation(models.Model):
    """
    Une évaluation au sens large : interrogation écrite, devoir
    surveillé, composition, ou QCM mis en ligne.

    Le champ "est_en_ligne" détermine si les élèves peuvent la
    voir/y répondre depuis leur espace (fonctionnalité "évaluations
    en ligne" demandée dans le cahier des charges).
    """

    TYPE_EVALUATION_CHOICES = [
        ('INTERROGATION', 'Interrogation écrite'),
        ('DEVOIR', 'Devoir surveillé'),
        ('COMPOSITION', 'Composition'),
        ('QCM_LIGNE', 'QCM en ligne'),
    ]

    # Regroupement utilisé PARTOUT dans le calcul des moyennes
    # (voir bulletins/models.py) : au Mali, on ne mélange JAMAIS
    # devoirs/interrogations ("note de classe") et compositions
    # dans un même calcul de moyenne — ce sont deux notes distinctes,
    # combinées seulement à la toute fin avec une pondération précise.
    TYPES_NOTE_DE_CLASSE = ['INTERROGATION', 'DEVOIR']
    TYPES_COMPOSITION = ['COMPOSITION']

    STATUT_CHOICES = [
        ('BROUILLON', 'Brouillon'),
        ('PUBLIEE', 'Publiée (visible des élèves)'),
        ('CLOTUREE', 'Clôturée (réponses fermées)'),
        ('CORRIGEE', 'Corrigée'),
    ]

    classe_matiere = models.ForeignKey(
        ClasseMatiere,
        on_delete=models.PROTECT,
        related_name='evaluations'
    )

    sequence = models.ForeignKey(
        Sequence,
        on_delete=models.PROTECT,
        related_name='evaluations',
        null=True,
        blank=True
    )

    trimestre = models.PositiveSmallIntegerField(
        choices=Sequence.TRIMESTRE_CHOICES,
        default=1,
        help_text="Trimestre auquel appartient cette évaluation. "
                   "INDISPENSABLE pour calculer les moyennes trimestrielles "
                   "séparément (voir bulletins.LigneBulletin) : contrairement "
                   "à 'sequence', ce champ n'est jamais optionnel, on peut "
                   "donc toujours savoir de quel trimestre relève une note, "
                   "même si l'enseignant n'a pas encore créé de séquence."
    )

    date_evaluation = models.DateField(
        default=timezone.localdate,
        verbose_name="Date de l'évaluation",
        help_text="Jour où l'évaluation a réellement eu lieu. Sert à "
                   "filtrer les notes par mois (indispensable pour les "
                   "compositions mensuelles). Différent de 'date_limite', "
                   "qui ne concerne que les évaluations en ligne."
        # default=timezone.localdate : on passe la FONCTION (sans
        # parenthèses), pas son résultat. Django l'appelle à chaque
        # création d'évaluation => la date du jour à ce moment-là.
        # Écrire localdate() avec parenthèses figerait la date du
        # démarrage du serveur : erreur classique à éviter.
    )

    titre = models.CharField(max_length=200)

    type_evaluation = models.CharField(
        max_length=15,
        choices=TYPE_EVALUATION_CHOICES
    )

    bareme_total = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=20,
        help_text="Note maximale de cette évaluation (souvent /20)"
    )

    coefficient = models.PositiveIntegerField(
        default=1,
        help_text="Coefficient de cette évaluation dans la moyenne"
    )

    duree_minutes = models.PositiveIntegerField(
        null=True,
        blank=True
    )

    est_en_ligne = models.BooleanField(
        default=False,
        help_text="Si True, les élèves peuvent y répondre depuis leur espace"
    )

    statut = models.CharField(
        max_length=15,
        choices=STATUT_CHOICES,
        default='BROUILLON'
    )

    date_ouverture = models.DateTimeField(
        null=True,
        blank=True,
        help_text="À partir de quand les élèves peuvent commencer à répondre"
    )

    date_limite = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Après cette date/heure, les réponses ne sont plus acceptées"
    )

    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Évaluation"
        verbose_name_plural = "Évaluations"
        ordering = ['-date_creation']

    def __str__(self):
        return f"{self.titre} - {self.classe_matiere.classe.nom}"

    def est_ouverte(self):
        """
        Vérifie si l'évaluation est actuellement accessible aux élèves,
        en comparant l'heure actuelle aux bornes date_ouverture/date_limite.
        Logique centralisée ici pour être réutilisée partout
        (vue élève, tâche planifiée de clôture automatique, etc.)
        sans dupliquer le calcul.
        """
        from django.utils import timezone
        maintenant = timezone.now()
        if not self.est_en_ligne or self.statut != 'PUBLIEE':
            return False
        if self.date_ouverture and maintenant < self.date_ouverture:
            return False
        if self.date_limite and maintenant > self.date_limite:
            return False
        return True


# ------------------------------------------------------------
# 2. QUESTION (pour les évaluations en ligne / QCM)
# ------------------------------------------------------------
class Question(models.Model):
    """
    Une question rattachée à une évaluation en ligne.

    Deux types de questions possibles :
    - QCM (à choix multiples) : auto-corrigée grâce au modèle Choix
    - Réponse libre : notée manuellement par l'enseignant
    """

    TYPE_QUESTION_CHOICES = [
        ('QCM', 'Choix multiple (auto-corrigé)'),
        ('LIBRE', 'Réponse libre (notée manuellement)'),
    ]

    evaluation = models.ForeignKey(
        Evaluation,
        on_delete=models.CASCADE,
        # CASCADE : une question n'a pas de sens sans son évaluation.
        related_name='questions'
    )

    numero_ordre = models.PositiveIntegerField()

    enonce = models.TextField(verbose_name="Énoncé de la question")

    type_question = models.CharField(
        max_length=10,
        choices=TYPE_QUESTION_CHOICES,
        default='QCM'
    )

    points = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=1,
        help_text="Points attribués à cette question"
    )

    class Meta:
        verbose_name = "Question"
        verbose_name_plural = "Questions"
        ordering = ['evaluation', 'numero_ordre']
        unique_together = ['evaluation', 'numero_ordre']

    def __str__(self):
        return f"Q{self.numero_ordre} - {self.enonce[:50]}"
        # [:50] = tronque le texte à 50 caractères pour un affichage
        # propre dans l'admin (évite d'afficher un énoncé entier très long).


# ------------------------------------------------------------
# 3. CHOIX DE REPONSE (pour les questions de type QCM)
# ------------------------------------------------------------
class Choix(models.Model):
    """
    Une proposition de réponse pour une question de type QCM.
    """

    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name='choix'
    )

    texte = models.CharField(max_length=300)

    est_correct = models.BooleanField(
        default=False,
        help_text="Coché si cette proposition est la bonne réponse"
    )

    class Meta:
        verbose_name = "Choix de réponse"
        verbose_name_plural = "Choix de réponse"

    def __str__(self):
        marque = "✓" if self.est_correct else "✗"
        return f"{marque} {self.texte}"


# ------------------------------------------------------------
# 4. COPIE (la "tentative" d'un élève sur une évaluation)
# ------------------------------------------------------------
class Copie(models.Model):
    """
    Représente la copie/tentative d'UN élève sur UNE évaluation.

    Pour une évaluation classique (papier), une seule Copie peut
    suffire à stocker directement la note finale. Pour une évaluation
    en ligne, la Copie regroupe toutes les réponses détaillées de
    l'élève (voir modèle ReponseEleve ci-dessous).
    """

    STATUT_CHOICES = [
        ('NON_RENDU', 'Non rendu'),
        ('SOUMIS', 'Soumis'),
        ('CORRIGE', 'Corrigé'),
    ]

    evaluation = models.ForeignKey(
        Evaluation,
        on_delete=models.PROTECT,
        related_name='copies'
    )

    eleve = models.ForeignKey(
        Eleve,
        on_delete=models.PROTECT,
        related_name='copies'
    )

    note_obtenue = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Note finale sur le barème de l'évaluation"
    )

    statut = models.CharField(
        max_length=10,
        choices=STATUT_CHOICES,
        default='NON_RENDU'
    )

    date_soumission = models.DateTimeField(null=True, blank=True)

    commentaire_enseignant = models.TextField(blank=True)

    class Meta:
        verbose_name = "Copie"
        verbose_name_plural = "Copies"
        unique_together = ['evaluation', 'eleve']
        # Un élève ne peut avoir qu'UNE SEULE copie par évaluation.

    def __str__(self):
        return f"{self.eleve.nom_complet} - {self.evaluation.titre}"

    def calculer_note_qcm(self):
        """
        Calcule automatiquement la note à partir des réponses QCM
        liées à cette copie (utile pour l'auto-correction en ligne).
        Ne touche pas aux questions de type LIBRE, qui restent notées
        manuellement par l'enseignant.
        """
        total_points = 0
        for reponse in self.reponses.select_related('question', 'choix_selectionne'):
            # select_related : optimisation qui va chercher en UNE seule
            # requête SQL les objets liés (question, choix_selectionne)
            # au lieu de faire une requête séparée pour chacun.
            if reponse.question.type_question == 'QCM' and reponse.choix_selectionne:
                if reponse.choix_selectionne.est_correct:
                    total_points += reponse.question.points
        return total_points


# ------------------------------------------------------------
# 5. REPONSE DE L'ELEVE (le détail, question par question)
# ------------------------------------------------------------
class ReponseEleve(models.Model):
    """
    La réponse d'un élève à UNE question précise, dans le cadre
    de sa Copie sur une évaluation en ligne.
    """

    copie = models.ForeignKey(
        Copie,
        on_delete=models.CASCADE,
        related_name='reponses'
    )

    question = models.ForeignKey(
        Question,
        on_delete=models.PROTECT,
        related_name='reponses'
    )

    # Rempli si la question est de type QCM :
    choix_selectionne = models.ForeignKey(
        Choix,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='reponses_recues'
    )

    # Rempli si la question est de type LIBRE :
    texte_reponse = models.TextField(blank=True)

    points_obtenus = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Rempli automatiquement pour le QCM, manuellement pour le libre"
    )

    class Meta:
        verbose_name = "Réponse d'élève"
        verbose_name_plural = "Réponses d'élèves"
        unique_together = ['copie', 'question']
        # Un élève ne répond qu'une fois à chaque question dans sa copie.

    def __str__(self):
        return f"{self.copie.eleve.nom_complet} - Q{self.question.numero_ordre}"