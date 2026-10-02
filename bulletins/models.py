# ============================================================
# APP : bulletins
# Fichier : models.py
# Rôle : calculer et stocker les moyennes par matière et
#        générales, le classement, et générer le bulletin
#        au format officiel malien (DNEB) en PDF.
# ============================================================
#
# Cette app dépend de "classes" (Eleve, Classe, ClasseMatiere)
# et lit les notes stockées dans "evaluations" (Copie) pour
# calculer les moyennes — mais elle STOCKE le résultat final
# dans ses propres tables, pour ne pas tout recalculer à chaque
# affichage et garder une trace figée du bulletin déjà publié.

from django.db import models
from django.db.models import Avg, Sum, F
# Avg, Sum, F : outils Django pour faire des calculs directement
# en SQL (moyenne, somme...) plutôt qu'en Python, plus rapide et
# plus fiable sur de gros volumes de données.

from classes.models import Eleve, Classe, ClasseMatiere


# ------------------------------------------------------------
# PONDÉRATION OFFICIELLE MALIENNE
# ------------------------------------------------------------
# Moyenne trimestrielle par matière = (Note de classe + 2 × Note
# de composition) / 3. La composition compte donc pour les deux
# tiers de la moyenne, les devoirs/interrogations pour le tiers
# restant. C'est la norme dans l'enseignement fondamental et
# secondaire malien (et plus largement ouest-africain francophone).
#
# On isole ces deux nombres en CONSTANTES tout en haut du fichier
# (plutôt que de les écrire "en dur" dans le calcul plus bas) pour
# une raison précise : Ma Classe Pro est pensé pour être vendu au-
# delà du Mali. Si un établissement d'un autre pays utilise une
# pondération différente, on n'aura qu'CES DEUX LIGNES à ajuster
# (ou, plus tard, à rendre configurables par établissement) plutôt
# que de chercher la formule éparpillée dans le code.
COEFFICIENT_NOTE_DE_CLASSE = 1
COEFFICIENT_NOTE_COMPOSITION = 2


def suggerer_appreciation(moyenne):
    """
    Suggère une appréciation littérale à partir d'une moyenne sur 20,
    selon l'échelle observée sur un bulletin malien réel (Mal,
    Passable, Assez Bien, Bien, Très Bien, Excellent travail).

    ⚠️ Cette échelle est déduite d'UN exemplaire de bulletin, pas
    d'une circulaire officielle vérifiée auprès du Ministère : les
    seuils exacts peuvent varier d'un établissement à l'autre.
    C'est pourquoi cette fonction ne fait que SUGGÉRER une valeur
    par défaut quand l'enseignant n'a rien saisi — elle ne remplace
    jamais une appréciation déjà écrite à la main (voir son usage
    dans LigneBulletin.calculer_moyenne_depuis_copies), et reste
    modifiable à tout moment depuis l'admin ou l'interface.
    """
    if moyenne is None:
        return ''
    if moyenne >= 18:
        return 'Excellent travail'
    if moyenne >= 16:
        return 'Très bien'
    if moyenne >= 14:
        return 'Bien'
    if moyenne >= 12:
        return 'Assez bien'
    if moyenne >= 10:
        return 'Passable'
    if moyenne >= 8:
        return 'Insuffisant'
    return 'Mal'


# ------------------------------------------------------------
# 1. BULLETIN
# ------------------------------------------------------------
class Bulletin(models.Model):
    """
    Le bulletin d'UN élève pour UN trimestre donné.

    On ne stocke pas directement l'année scolaire ici : elle est
    accessible via classe.annee_scolaire (on évite de dupliquer
    une information déjà présente ailleurs, source d'incohérence
    si les deux valeurs venaient à diverger).
    """

    TRIMESTRE_CHOICES = [
        (1, '1er trimestre'),
        (2, '2ème trimestre'),
        (3, '3ème trimestre'),
    ]

    STATUT_CHOICES = [
        ('BROUILLON', 'Brouillon (calcul en cours)'),
        ('GENERE', 'Généré (PDF prêt)'),
        ('PUBLIE', 'Publié (visible par l\'élève/parent)'),
    ]

    eleve = models.ForeignKey(
        Eleve,
        on_delete=models.PROTECT,
        related_name='bulletins'
    )

    classe = models.ForeignKey(
        Classe,
        on_delete=models.PROTECT,
        related_name='bulletins',
        help_text="Classe de l'élève au moment de ce bulletin"
    )

    trimestre = models.PositiveSmallIntegerField(choices=TRIMESTRE_CHOICES)

    moyenne_generale = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Moyenne pondérée par les coefficients, calculée automatiquement"
    )

    rang = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Rang de l'élève dans sa classe pour ce trimestre"
    )

    effectif_classe = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Nombre d'élèves de la classe pris en compte dans le classement"
    )

    appreciation_generale = models.CharField(
        max_length=100,
        blank=True,
        help_text="Exemple : Très bien, Bien, Assez bien, Passable, Insuffisant"
    )

    statut = models.CharField(
        max_length=10,
        choices=STATUT_CHOICES,
        default='BROUILLON'
    )

    fichier_pdf = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        help_text="Chemin du bulletin PDF généré au format DNEB"
    )

    date_generation = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Rempli automatiquement au moment de la génération du PDF"
    )

    class Meta:
        verbose_name = "Bulletin"
        verbose_name_plural = "Bulletins"
        ordering = ['classe', 'trimestre', 'rang']
        unique_together = ['eleve', 'trimestre', 'classe']
        # Un seul bulletin par élève, par trimestre, dans une classe donnée.

    def __str__(self):
        return f"Bulletin {self.get_trimestre_display()} - {self.eleve.nom_complet}"

    def calculer_moyenne_generale(self):
        """
        Recalcule la moyenne générale à partir des LigneBulletin
        déjà enregistrées, en pondérant chaque matière par son
        coefficient (stocké sur ClasseMatiere).

        Formule : somme(moyenne_matiere * coefficient) / somme(coefficients)
        C'est la méthode standard de calcul de moyenne pondérée
        utilisée dans les bulletins maliens.
        """
        lignes = self.lignes.select_related('classe_matiere')
        total_points = 0
        total_coefficients = 0

        for ligne in lignes:
            if ligne.moyenne is not None:
                coef = ligne.classe_matiere.coefficient
                total_points += ligne.moyenne * coef
                total_coefficients += coef

        if total_coefficients == 0:
            # Évite une division par zéro si aucune note n'est encore saisie.
            return None

        moyenne = round(total_points / total_coefficients, 2)
        self.moyenne_generale = moyenne
        self.save(update_fields=['moyenne_generale'])
        # update_fields : on précise qu'on ne met à jour QUE ce champ,
        # ce qui évite d'écraser accidentellement d'autres modifications
        # en cours sur le même objet, et c'est légèrement plus rapide.
        return moyenne

    @staticmethod
    def calculer_classement(classe, trimestre):
        """
        Calcule le rang de TOUS les élèves d'une classe pour un
        trimestre donné, en se basant sur leur moyenne_generale
        déjà calculée.

        @staticmethod : cette méthode ne dépend pas d'UN bulletin
        précis (self), mais traite TOUTE une classe d'un coup ;
        on l'appelle donc via Bulletin.calculer_classement(...)
        plutôt que sur une instance.
        """
        bulletins = Bulletin.objects.filter(
            classe=classe,
            trimestre=trimestre,
            moyenne_generale__isnull=False
            # __isnull=False : on ne classe que les élèves dont la
            # moyenne a bien été calculée (pas de valeur manquante).
        ).order_by('-moyenne_generale')
        # order_by('-moyenne_generale') : tri décroissant, le 1er de
        # la liste a la meilleure moyenne => rang 1.

        effectif = bulletins.count()

        for position, bulletin in enumerate(bulletins, start=1):
            # enumerate(..., start=1) : numérote à partir de 1 (pas 0),
            # car un rang "0" n'a pas de sens pédagogique.
            bulletin.rang = position
            bulletin.effectif_classe = effectif
            bulletin.save(update_fields=['rang', 'effectif_classe'])


# ------------------------------------------------------------
# 2. LIGNE DE BULLETIN (le détail par matière)
# ------------------------------------------------------------
class LigneBulletin(models.Model):
    """
    Une ligne du bulletin : la moyenne obtenue par l'élève dans
    UNE matière précise, pour le trimestre du bulletin parent.
    """

    bulletin = models.ForeignKey(
        Bulletin,
        on_delete=models.CASCADE,
        # CASCADE : une ligne n'existe que rattachée à son bulletin.
        related_name='lignes'
    )

    classe_matiere = models.ForeignKey(
        ClasseMatiere,
        on_delete=models.PROTECT,
        related_name='lignes_bulletin'
    )

    moyenne_devoirs = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Note de classe",
        help_text="Moyenne des devoirs et interrogations du trimestre, "
                   "calculée uniquement sur les évaluations où l'élève "
                   "a une note (les absences ne comptent jamais comme 0)"
    )

    moyenne_composition = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Note de composition",
        help_text="Moyenne des compositions du trimestre (une seule si "
                   "trimestrielle, moyennée si plusieurs compositions "
                   "mensuelles)"
    )

    moyenne = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Moyenne trimestrielle",
        help_text="(Note de classe + 2 × Note de composition) / 3 — "
                   "calculée automatiquement, ne pas modifier à la main"
    )

    rang_matiere = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Optionnel : rang de l'élève dans CETTE matière précise"
    )

    appreciation = models.CharField(
        max_length=100,
        blank=True,
        help_text="Appréciation courte du professeur pour cette matière"
    )

    class Meta:
        verbose_name = "Ligne de bulletin"
        verbose_name_plural = "Lignes de bulletin"
        ordering = ['bulletin', 'classe_matiere']
        unique_together = ['bulletin', 'classe_matiere']
        # Une seule ligne par matière dans un même bulletin.

    def __str__(self):
        return f"{self.classe_matiere.matiere.nom} - {self.moyenne} ({self.bulletin.eleve.nom_complet})"

    def _moyenne_ponderee_par_type(self, types_evaluation):
        """
        Méthode "privée" (le underscore devant le nom est une
        convention Python signifiant "usage interne à cette classe
        uniquement", pas une vraie restriction technique) qui
        calcule une moyenne pondérée sur UN SOUS-ENSEMBLE de types
        d'évaluation (soit devoirs/interrogations, soit compositions
        — jamais les deux mélangés, voir la constante TYPES_NOTE_DE_CLASSE
        / TYPES_COMPOSITION définie sur le modèle Evaluation).

        Règle clé demandée : si un élève n'a pas de Copie notée pour
        une évaluation donnée (absent, ou copie non encore corrigée),
        cette évaluation est SIMPLEMENT EXCLUE de SON calcul — jamais
        comptée comme un zéro. C'est naturel ici : on ne boucle QUE
        sur les Copies qui existent réellement avec une note.
        """
        from evaluations.models import Copie

        copies = Copie.objects.filter(
            eleve=self.bulletin.eleve,
            evaluation__classe_matiere=self.classe_matiere,
            evaluation__trimestre=self.bulletin.trimestre,
            evaluation__type_evaluation__in=types_evaluation,
            note_obtenue__isnull=False,
        ).select_related('evaluation')

        total_points = 0
        total_coefficients = 0

        for copie in copies:
            coef = copie.evaluation.coefficient
            # On ramène chaque note sur 20 pour pouvoir les comparer/
            # additionner équitablement, même si le barème d'une
            # évaluation était différent (ex: notée sur 10).
            note_sur_20 = (copie.note_obtenue / copie.evaluation.bareme_total) * 20
            total_points += note_sur_20 * coef
            total_coefficients += coef

        if total_coefficients == 0:
            # Aucune évaluation de ce type notée pour cet élève sur
            # ce trimestre (ex : aucune composition saisie pour le
            # moment). On renvoie None plutôt que 0, pour ne jamais
            # faire croire à une note obtenue qui n'existe pas.
            return None

        return round(total_points / total_coefficients, 2)

    def calculer_moyenne_depuis_copies(self):
        """
        Calcule la moyenne TRIMESTRIELLE de l'élève dans cette
        matière, en respectant la règle malienne :

            Moyenne = (Note de classe + 2 × Note de composition) / 3

        où "Note de classe" = moyenne des devoirs/interrogations,
        et "Note de composition" = moyenne des compositions — deux
        calculs INDÉPENDANTS (voir _moyenne_ponderee_par_type),
        combinés seulement à la toute fin.
        """
        from evaluations.models import Evaluation

        self.moyenne_devoirs = self._moyenne_ponderee_par_type(
            Evaluation.TYPES_NOTE_DE_CLASSE
        )
        self.moyenne_composition = self._moyenne_ponderee_par_type(
            Evaluation.TYPES_COMPOSITION
        )

        if self.moyenne_devoirs is not None and self.moyenne_composition is not None:
            # Cas normal : les deux notes existent, on applique la
            # pondération officielle.
            total = (
                self.moyenne_devoirs * COEFFICIENT_NOTE_DE_CLASSE
                + self.moyenne_composition * COEFFICIENT_NOTE_DE_CLASSE * COEFFICIENT_NOTE_COMPOSITION
                # ⚠️ Remarque de lecture : COEFFICIENT_NOTE_DE_CLASSE
                # vaut 1, donc ce deuxième terme se simplifie en
                # "moyenne_composition * 2". On l'écrit sous cette
                # forme volontairement pour que la pondération reste
                # LISIBLE et modifiable même si un jour
                # COEFFICIENT_NOTE_DE_CLASSE change (ex: 2 partout
                # ferait ressortir un ratio différent).
            ) / (COEFFICIENT_NOTE_DE_CLASSE + COEFFICIENT_NOTE_COMPOSITION)
            self.moyenne = round(total, 2)
        elif self.moyenne_composition is not None:
            # Cas rare : aucun devoir/interrogation noté ce trimestre,
            # mais une composition existe déjà. On évite un bulletin
            # vide en se basant uniquement sur elle.
            self.moyenne = self.moyenne_composition
        elif self.moyenne_devoirs is not None:
            # Composition pas encore passée/saisie : moyenne
            # PROVISOIRE basée sur les devoirs seuls. Ne pas
            # considérer ce bulletin comme définitif dans ce cas —
            # à toi de décider dans l'interface de ne publier le
            # bulletin qu'une fois la composition saisie.
            self.moyenne = self.moyenne_devoirs
        else:
            self.moyenne = None

        if not self.appreciation:
            # On ne SUGGÈRE une appréciation que si le champ est
            # encore vide : un texte déjà saisi par l'enseignant
            # (ex: une remarque personnalisée) n'est jamais écrasé
            # par un recalcul automatique.
            self.appreciation = suggerer_appreciation(self.moyenne)

        self.save(update_fields=['moyenne_devoirs', 'moyenne_composition', 'moyenne', 'appreciation'])
        return self.moyenne

    @staticmethod
    def calculer_classement_matiere(classe_matiere, trimestre):
        """
        Calcule le rang de chaque élève DANS une matière précise
        pour un trimestre donné — la colonne "Rang" par discipline
        du bulletin officiel (à ne pas confondre avec Bulletin.rang,
        qui est le rang général tous coefficients confondus).

        Même logique que Bulletin.calculer_classement() : on classe
        tous les élèves de cette matière par moyenne décroissante,
        seulement parmi ceux qui ont déjà une moyenne calculée.
        """
        lignes = LigneBulletin.objects.filter(
            classe_matiere=classe_matiere,
            bulletin__trimestre=trimestre,
            moyenne__isnull=False,
        ).order_by('-moyenne')

        for position, ligne in enumerate(lignes, start=1):
            ligne.rang_matiere = position
            ligne.save(update_fields=['rang_matiere'])

    @property
    def moyenne_coefficiee(self):
        """
        "Moyenne Coéfficiée" : la 4ème colonne du bulletin officiel
        malien (Note de classe, Note de composition, Moyenne,
        Moyenne Coéfficiée) — la moyenne de la matière multipliée
        par son coefficient.

        C'est une @property, PAS un champ stocké en base : elle est
        recalculée à la volée à chaque accès, à partir de 'moyenne'
        et du coefficient actuel de la matière. Impossible qu'elle
        se désynchronise (ex: si le coefficient d'une matière change
        après coup, cette valeur reflète TOUJOURS le coefficient
        actuel, sans avoir besoin de relancer un recalcul manuel).

        C'est aussi exactement le terme utilisé par
        Bulletin.calculer_moyenne_generale() : la moyenne générale
        de l'élève est la somme de ces MoyenneCoéfficiée (toutes
        matières) divisée par la somme des coefficients.
        """
        if self.moyenne is None:
            return None
        return round(self.moyenne * self.classe_matiere.coefficient, 2)

    def _nombre_copies_par_type(self, types_evaluation):
        """
        Compte combien d'évaluations (devoirs/interros, ou
        compositions) ont réellement une note pour cet élève sur ce
        trimestre. Utile pour AFFICHER, à côté de la note de classe
        ou de composition, sur combien d'évaluations elle a été
        calculée — important en primaire où plusieurs compositions
        mensuelles sont moyennées ensemble : le secrétaire ou
        l'enseignant peut ainsi vérifier d'un coup d'œil qu'aucune
        composition du trimestre n'a été oubliée.
        """
        from evaluations.models import Copie

        return Copie.objects.filter(
            eleve=self.bulletin.eleve,
            evaluation__classe_matiere=self.classe_matiere,
            evaluation__trimestre=self.bulletin.trimestre,
            evaluation__type_evaluation__in=types_evaluation,
            note_obtenue__isnull=False,
        ).count()

    @property
    def nombre_devoirs_comptes(self):
        from evaluations.models import Evaluation
        return self._nombre_copies_par_type(Evaluation.TYPES_NOTE_DE_CLASSE)

    @property
    def nombre_compositions_comptees(self):
        from evaluations.models import Evaluation
        return self._nombre_copies_par_type(Evaluation.TYPES_COMPOSITION)