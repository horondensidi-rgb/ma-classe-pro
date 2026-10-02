# ============================================================
# APP : evaluations
# Fichier : vues_eleve.py (nouveau fichier, séparé de views.py)
# Rôle : tout ce que l'ÉLÈVE voit et fait lui-même — consulter
#        ses évaluations en ligne ouvertes, y répondre, voir son
#        résultat. Séparé de views.py (le fichier des vues
#        ENSEIGNANT) pour que les deux publics ne soient jamais
#        mélangés dans le même fichier, plus facile à auditer
#        pour la sécurité : "tout ce qui est dans vues_eleve.py
#        doit être sûr pour un élève", point final.
# ============================================================

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.contrib import messages
from django.db.models import Q
from django.utils import timezone

from classes.permissions import obtenir_eleve_ou_403
from .models import Evaluation, Copie, ReponseEleve


@login_required
def eleve_tableau_bord_view(request):
    """
    Liste les évaluations en ligne actuellement OUVERTES pour la
    classe de l'élève connecté — ni celles pas encore publiées, ni
    celles déjà closes (voir Evaluation.est_ouverte, dont la
    logique est reproduite ici en requête SQL pour filtrer
    efficacement plusieurs évaluations d'un coup).
    """
    eleve = obtenir_eleve_ou_403(request)
    maintenant = timezone.now()

    evaluations = Evaluation.objects.filter(
        classe_matiere__classe=eleve.classe,
        est_en_ligne=True,
        statut='PUBLIEE',
    ).filter(
        Q(date_ouverture__isnull=True) | Q(date_ouverture__lte=maintenant)
    ).filter(
        Q(date_limite__isnull=True) | Q(date_limite__gte=maintenant)
    ).select_related('classe_matiere__matiere').order_by('date_limite')

    copies_existantes = {
        copie.evaluation_id: copie
        for copie in Copie.objects.filter(eleve=eleve, evaluation__in=evaluations)
    }

    lignes = []
    for evaluation in evaluations:
        copie = copies_existantes.get(evaluation.id)
        lignes.append({
            'evaluation': evaluation,
            'deja_repondu': copie is not None and copie.statut != 'NON_RENDU',
        })

    return render(request, 'evaluations/eleve_tableau_bord.html', {
        'eleve': eleve,
        'lignes': lignes,
    })


@login_required
def eleve_repondre_view(request, evaluation_id):
    """
    Affiche le questionnaire et enregistre les réponses de l'élève.

    Sécurité : on vérifie que l'évaluation appartient bien à LA
    classe de cet élève (pas une autre), et qu'elle est encore
    ouverte — sinon, un élève pourrait répondre à une évaluation
    d'une autre classe ou après la date limite en devinant l'URL.
    """
    eleve = obtenir_eleve_ou_403(request)
    evaluation = get_object_or_404(Evaluation, id=evaluation_id)

    if evaluation.classe_matiere.classe_id != eleve.classe_id:
        raise PermissionDenied("Cette évaluation ne concerne pas votre classe.")

    if not evaluation.est_ouverte():
        raise PermissionDenied("Cette évaluation n'est plus ouverte.")

    copie, _cree = Copie.objects.get_or_create(evaluation=evaluation, eleve=eleve)

    if copie.statut == 'CORRIGE':
        # Déjà corrigée : on ne permet plus de revenir modifier les
        # réponses, pour la même raison qu'on ne modifie pas une
        # copie papier déjà rendue au professeur.
        return redirect('evaluations:eleve_resultat', evaluation_id=evaluation.id)

    questions = evaluation.questions.prefetch_related('choix').order_by('numero_ordre')

    if request.method == 'POST':
        for question in questions:
            if question.type_question == 'QCM':
                choix_id = request.POST.get(f'question_{question.id}')
                if not choix_id:
                    continue
                choix = question.choix.filter(id=choix_id).first()
                if not choix:
                    continue
                reponse, _ = ReponseEleve.objects.get_or_create(
                    copie=copie, question=question,
                    defaults={'choix_selectionne': choix}
                )
                reponse.choix_selectionne = choix
                reponse.save(update_fields=['choix_selectionne'])
            else:
                # type_question == 'LIBRE'
                texte = request.POST.get(f'question_{question.id}', '').strip()
                reponse, _ = ReponseEleve.objects.get_or_create(
                    copie=copie, question=question,
                    defaults={'texte_reponse': texte}
                )
                reponse.texte_reponse = texte
                reponse.save(update_fields=['texte_reponse'])

        # Auto-correction IMMÉDIATE de la partie QCM (voir
        # Copie.calculer_note_qcm dans evaluations/models.py).
        points_qcm = copie.calculer_note_qcm()

        a_des_questions_libres = questions.filter(type_question='LIBRE').exists()
        if a_des_questions_libres:
            # Note finale pas encore connue : une question au moins
            # nécessite une correction manuelle par l'enseignant.
            copie.statut = 'SOUMIS'
            copie.note_obtenue = None
        else:
            # Que des QCM : la note est déjà définitive.
            copie.statut = 'CORRIGE'
            copie.note_obtenue = points_qcm

        copie.date_soumission = timezone.now()
        copie.save(update_fields=['statut', 'note_obtenue', 'date_soumission'])

        messages.success(request, "Réponses envoyées.")
        return redirect('evaluations:eleve_resultat', evaluation_id=evaluation.id)

    reponses_existantes = {
        reponse.question_id: reponse
        for reponse in ReponseEleve.objects.filter(copie=copie)
    }

    return render(request, 'evaluations/eleve_repondre.html', {
        'evaluation': evaluation,
        'questions': questions,
        'reponses_existantes': reponses_existantes,
    })


@login_required
def eleve_resultat_view(request, evaluation_id):
    """
    Affiche le résultat d'une évaluation déjà soumise : la note si
    elle est déjà connue (tout QCM), ou "en attente de correction"
    si une question à réponse libre doit encore être notée à la main.
    """
    eleve = obtenir_eleve_ou_403(request)
    evaluation = get_object_or_404(Evaluation, id=evaluation_id)

    if evaluation.classe_matiere.classe_id != eleve.classe_id:
        raise PermissionDenied("Cette évaluation ne concerne pas votre classe.")

    copie = get_object_or_404(Copie, evaluation=evaluation, eleve=eleve)

    return render(request, 'evaluations/eleve_resultat.html', {
        'evaluation': evaluation,
        'copie': copie,
    })