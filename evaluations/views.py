# ============================================================
# APP : evaluations
# Fichier : views.py
# Rôle : créer une évaluation pour une matière enseignée, et
#        saisir les notes de toute la classe en une seule page.
# ============================================================

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models.deletion import ProtectedError
from django.views.decorators.http import require_POST
from django.contrib import messages

from comptes.permissions import obtenir_enseignant_ou_403
from classes.models import ClasseMatiere
from classes.permissions import enseignant_a_acces_classe_matiere
from .models import Evaluation, Copie, Question
from .forms import EvaluationForm, QuestionForm, ChoixFormSet


@login_required
def liste_evaluations_view(request, classe_matiere_id):
    """
    Liste toutes les évaluations déjà créées pour UNE matière
    enseignée précise (ex : Français en 7ème A).
    """
    enseignant = obtenir_enseignant_ou_403(request)
    classe_matiere = get_object_or_404(ClasseMatiere, id=classe_matiere_id)

    if not enseignant_a_acces_classe_matiere(enseignant, classe_matiere):
        raise PermissionDenied("Vous n'enseignez pas cette matière dans cette classe.")

    evaluations = classe_matiere.evaluations.order_by('-date_creation')
    # classe_matiere.evaluations vient du related_name='evaluations'
    # défini sur Evaluation.classe_matiere dans evaluations/models.py.

    return render(request, 'evaluations/liste_evaluations.html', {
        'classe_matiere': classe_matiere,
        'evaluations': evaluations,
    })


@login_required
def creer_evaluation_view(request, classe_matiere_id):
    """
    Formulaire de création d'une évaluation, rattachée à la
    matière enseignée dont l'ID vient de l'URL.
    """
    enseignant = obtenir_enseignant_ou_403(request)
    classe_matiere = get_object_or_404(ClasseMatiere, id=classe_matiere_id)

    if not enseignant_a_acces_classe_matiere(enseignant, classe_matiere):
        raise PermissionDenied("Vous n'enseignez pas cette matière dans cette classe.")

    if request.method == 'POST':
        form = EvaluationForm(request.POST)
        if form.is_valid():
            evaluation = form.save(commit=False)
            evaluation.classe_matiere = classe_matiere
            evaluation.save()
            messages.success(request, "Évaluation créée. Vous pouvez maintenant saisir les notes.")
            return redirect('evaluations:saisir_notes', evaluation_id=evaluation.id)
    else:
        form = EvaluationForm()

    return render(request, 'evaluations/creer_evaluation.html', {
        'form': form,
        'classe_matiere': classe_matiere,
    })


@login_required
def modifier_evaluation_view(request, evaluation_id):
    """
    Corrige une évaluation déjà créée (titre, barème, coefficient,
    date, trimestre...). Même formulaire que la création
    (EvaluationForm), pré-rempli via instance=evaluation.
    """
    enseignant = obtenir_enseignant_ou_403(request)
    evaluation = get_object_or_404(Evaluation, id=evaluation_id)

    if not enseignant_a_acces_classe_matiere(enseignant, evaluation.classe_matiere):
        raise PermissionDenied("Vous n'enseignez pas cette matière dans cette classe.")

    if request.method == 'POST':
        form = EvaluationForm(request.POST, instance=evaluation)
        if form.is_valid():
            form.save()
            messages.success(request, "Évaluation mise à jour.")
            return redirect('evaluations:liste_evaluations', classe_matiere_id=evaluation.classe_matiere_id)
    else:
        form = EvaluationForm(instance=evaluation)

    return render(request, 'evaluations/modifier_evaluation.html', {
        'form': form,
        'evaluation': evaluation,
        'classe_matiere': evaluation.classe_matiere,
    })


@login_required
@require_POST
def supprimer_evaluation_view(request, evaluation_id):
    """
    Supprime une évaluation, SAUF si des notes (Copie) lui sont déjà
    rattachées : Copie.evaluation utilise on_delete=PROTECT (choix
    fait dès le départ pour ne jamais perdre une note enregistrée),
    donc Django refuse la suppression et lève ProtectedError — on
    l'attrape pour afficher un message clair plutôt que de laisser
    planter la page avec une erreur brute à 500.
    """
    enseignant = obtenir_enseignant_ou_403(request)
    evaluation = get_object_or_404(Evaluation, id=evaluation_id)

    if not enseignant_a_acces_classe_matiere(enseignant, evaluation.classe_matiere):
        raise PermissionDenied("Vous n'enseignez pas cette matière dans cette classe.")

    classe_matiere_id = evaluation.classe_matiere_id
    titre = evaluation.titre

    try:
        evaluation.delete()
        messages.success(request, f"L'évaluation « {titre} » a été supprimée.")
    except ProtectedError:
        messages.error(
            request,
            f"Impossible de supprimer « {titre} » : des notes y sont déjà "
            f"enregistrées. Retire d'abord les notes concernées si tu es "
            f"certain de vouloir la supprimer."
        )

    return redirect('evaluations:liste_evaluations', classe_matiere_id=classe_matiere_id)


@login_required
@require_POST
def publier_evaluation_view(request, evaluation_id):
    """
    Bascule le statut d'une évaluation entre BROUILLON et PUBLIEE.

    Tant qu'une évaluation reste en BROUILLON, elle n'apparaît JAMAIS
    dans l'espace élève (voir Evaluation.est_ouverte, qui exige
    statut == 'PUBLIEE' en plus de est_en_ligne == True) — ce qui
    laisse le temps à l'enseignant de préparer ses questions
    tranquillement avant de la rendre visible.
    """
    enseignant = obtenir_enseignant_ou_403(request)
    evaluation = get_object_or_404(Evaluation, id=evaluation_id)

    if not enseignant_a_acces_classe_matiere(enseignant, evaluation.classe_matiere):
        raise PermissionDenied("Vous n'enseignez pas cette matière dans cette classe.")

    if evaluation.statut == 'PUBLIEE':
        evaluation.statut = 'BROUILLON'
        messages.success(request, f"« {evaluation.titre} » n'est plus visible des élèves.")
    else:
        evaluation.statut = 'PUBLIEE'
        messages.success(request, f"« {evaluation.titre} » est maintenant publiée.")

    evaluation.save(update_fields=['statut'])
    return redirect('evaluations:liste_evaluations', classe_matiere_id=evaluation.classe_matiere_id)


@login_required
def liste_questions_view(request, evaluation_id):
    """
    Liste les questions déjà créées pour une évaluation (utile pour
    les évaluations en ligne : QCM destinés aux élèves).
    """
    enseignant = obtenir_enseignant_ou_403(request)
    evaluation = get_object_or_404(Evaluation, id=evaluation_id)

    if not enseignant_a_acces_classe_matiere(enseignant, evaluation.classe_matiere):
        raise PermissionDenied("Vous n'enseignez pas cette matière dans cette classe.")

    questions = evaluation.questions.order_by('numero_ordre')

    return render(request, 'evaluations/liste_questions.html', {
        'evaluation': evaluation,
        'questions': questions,
    })


@login_required
def creer_question_view(request, evaluation_id):
    """
    Crée une question pour une évaluation. Numéro d'ordre par
    défaut = position suivante dans la liste (1, 2, 3...), pour
    éviter à l'enseignant de devoir le calculer lui-même.
    """
    enseignant = obtenir_enseignant_ou_403(request)
    evaluation = get_object_or_404(Evaluation, id=evaluation_id)

    if not enseignant_a_acces_classe_matiere(enseignant, evaluation.classe_matiere):
        raise PermissionDenied("Vous n'enseignez pas cette matière dans cette classe.")

    prochain_numero = evaluation.questions.count() + 1

    if request.method == 'POST':
        form = QuestionForm(request.POST)
        if form.is_valid():
            question = form.save(commit=False)
            question.evaluation = evaluation
            question.save()
            if question.type_question == 'QCM':
                messages.success(request, "Question créée. Ajoute maintenant les choix de réponse.")
                return redirect('evaluations:modifier_choix', question_id=question.id)
            messages.success(request, "Question créée.")
            return redirect('evaluations:liste_questions', evaluation_id=evaluation.id)
    else:
        form = QuestionForm(initial={'numero_ordre': prochain_numero, 'points': 1})

    return render(request, 'evaluations/creer_question.html', {
        'form': form,
        'evaluation': evaluation,
    })


@login_required
def modifier_question_view(request, question_id):
    """
    Corrige l'énoncé/type/points d'une question déjà créée.
    """
    enseignant = obtenir_enseignant_ou_403(request)
    question = get_object_or_404(Question, id=question_id)

    if not enseignant_a_acces_classe_matiere(enseignant, question.evaluation.classe_matiere):
        raise PermissionDenied("Vous n'enseignez pas cette matière dans cette classe.")

    if request.method == 'POST':
        form = QuestionForm(request.POST, instance=question)
        if form.is_valid():
            form.save()
            messages.success(request, "Question mise à jour.")
            return redirect('evaluations:liste_questions', evaluation_id=question.evaluation_id)
    else:
        form = QuestionForm(instance=question)

    return render(request, 'evaluations/creer_question.html', {
        'form': form,
        'evaluation': question.evaluation,
        'question': question,
    })


@login_required
def modifier_choix_view(request, question_id):
    """
    Gère les propositions de réponse (Choix) d'UNE question QCM :
    texte de chaque proposition + case "bonne réponse".
    """
    enseignant = obtenir_enseignant_ou_403(request)
    question = get_object_or_404(Question, id=question_id)

    if not enseignant_a_acces_classe_matiere(enseignant, question.evaluation.classe_matiere):
        raise PermissionDenied("Vous n'enseignez pas cette matière dans cette classe.")

    if request.method == 'POST':
        formset = ChoixFormSet(request.POST, instance=question)
        if formset.is_valid():
            formset.save()
            messages.success(request, "Choix de réponse enregistrés.")
            return redirect('evaluations:liste_questions', evaluation_id=question.evaluation_id)
    else:
        formset = ChoixFormSet(instance=question)

    return render(request, 'evaluations/modifier_choix.html', {
        'question': question,
        'formset': formset,
    })


@login_required
@require_POST
def supprimer_question_view(request, question_id):
    """
    Supprime une question et ses choix (CASCADE déjà prévu sur
    Choix.question). Si des élèves ont déjà répondu à cette question
    (ReponseEleve.question utilise on_delete=PROTECT), Django refuse
    la suppression — on l'attrape proprement, même logique que pour
    supprimer_evaluation_view.
    """
    enseignant = obtenir_enseignant_ou_403(request)
    question = get_object_or_404(Question, id=question_id)

    if not enseignant_a_acces_classe_matiere(enseignant, question.evaluation.classe_matiere):
        raise PermissionDenied("Vous n'enseignez pas cette matière dans cette classe.")

    evaluation_id = question.evaluation_id

    try:
        question.delete()
        messages.success(request, "Question supprimée.")
    except ProtectedError:
        messages.error(
            request,
            "Impossible de supprimer cette question : des élèves y ont déjà répondu."
        )

    return redirect('evaluations:liste_questions', evaluation_id=evaluation_id)


@login_required
def saisir_notes_view(request, evaluation_id):
    """
    Affiche TOUS les élèves actifs de la classe concernée, avec un
    champ de saisie de note par élève, sur UNE seule page — plutôt
    qu'un formulaire séparé par élève, bien plus pratique pour
    corriger un paquet de copies d'un coup.
    """
    enseignant = obtenir_enseignant_ou_403(request)
    evaluation = get_object_or_404(Evaluation, id=evaluation_id)

    if not enseignant_a_acces_classe_matiere(enseignant, evaluation.classe_matiere):
        raise PermissionDenied("Vous n'enseignez pas cette matière dans cette classe.")

    eleves = evaluation.classe_matiere.classe.eleves.filter(
        est_actif=True
    ).order_by('nom', 'prenom')

    # On récupère les copies déjà enregistrées, indexées par élève,
    # pour PRÉ-REMPLIR les notes déjà saisies (ex : l'enseignant
    # revient corriger/modifier après une première saisie).
    copies_existantes = {
        copie.eleve_id: copie
        for copie in Copie.objects.filter(evaluation=evaluation)
    }
    # Ceci est une "dict comprehension" : ça construit un dictionnaire
    # {id_eleve: copie} en une seule ligne, plus rapide à écrire (et
    # à exécuter) qu'une boucle for classique avec .append().

    if request.method == 'POST':
        for eleve in eleves:
            valeur_brute = request.POST.get(f'note_{eleve.id}', '').strip()
            # Chaque champ du formulaire HTML est nommé "note_<id>" :
            # on le retrouve dans request.POST avec ce même nom exact
            # (voir le template saisir_notes.html plus loin).

            if valeur_brute == '':
                # Champ laissé vide : l'enseignant n'a pas encore la
                # note de cet élève. On ne crée pas de Copie pour lui
                # plutôt que d'enregistrer une note à 0 par erreur.
                continue

            try:
                note = float(valeur_brute.replace(',', '.'))
                # .replace(',', '.') : accepte "14,5" (virgule
                # française) aussi bien que "14.5" (point).
            except ValueError:
                messages.error(request, f"Note invalide pour {eleve.nom_complet}, ignorée.")
                continue

            copie, cree = Copie.objects.get_or_create(
                evaluation=evaluation,
                eleve=eleve,
                defaults={'note_obtenue': note, 'statut': 'CORRIGE'}
            )
            if not cree:
                # La copie existait déjà : on met à jour la note
                # au lieu d'en créer une deuxième (unique_together
                # sur evaluation+eleve l'aurait de toute façon empêché).
                copie.note_obtenue = note
                copie.statut = 'CORRIGE'
                copie.save(update_fields=['note_obtenue', 'statut'])

        messages.success(request, "Notes enregistrées.")
        return redirect('evaluations:saisir_notes', evaluation_id=evaluation.id)

    # Pour l'affichage (GET), on prépare une liste simple de paires
    # (élève, note actuelle ou None) : plus facile à parcourir dans
    # le template qu'un dictionnaire indexé par ID.
    lignes = []
    for eleve in eleves:
        copie = copies_existantes.get(eleve.id)
        lignes.append({
            'eleve': eleve,
            'note_actuelle': copie.note_obtenue if copie else None,
        })

    return render(request, 'evaluations/saisir_notes.html', {
        'evaluation': evaluation,
        'lignes': lignes,
    })
