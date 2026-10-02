# ============================================================
# APP : pedagogie
# Fichier : views.py
# Rôle : créer, consulter, modifier et supprimer les fiches de
#        préparation d'une matière enseignée, en deux temps
#        (informations générales, puis déroulement par étapes).
# ============================================================

from django import forms
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.core.exceptions import PermissionDenied
from django.contrib import messages
from django.forms import inlineformset_factory
from django.db.models import F

from django.db.models import Q

from comptes.permissions import obtenir_enseignant_ou_403
from classes.models import ClasseMatiere
from classes.permissions import enseignant_a_acces_classe_matiere
from .models import FichePreparation, EtapeFiche
from .forms import FichePreparationForm


@login_required
def choisir_matiere_view(request):
    """
    Étape intermédiaire avant la création d'une fiche : la page
    "Mes fiches" (mes_fiches_view) n'a aucune matière précise en
    contexte (elle affiche TOUTES les classes/matières à la fois),
    donc impossible de savoir directement POUR QUELLE matière créer
    la nouvelle fiche. Cette vue liste les matières enseignées par
    l'enseignant connecté, chacune menant vers creer_fiche_view.
    """
    enseignant = obtenir_enseignant_ou_403(request)

    classes_matieres = ClasseMatiere.objects.filter(
        Q(enseignant=enseignant) | Q(classe__enseignant_principal=enseignant)
    ).select_related('classe', 'matiere').distinct().order_by('classe__nom', 'matiere__nom')

    return render(request, 'pedagogie/choisir_matiere.html', {
        'classes_matieres': classes_matieres,
    })


@login_required
def mes_fiches_view(request):
    """
    Liste TOUTES les fiches de préparation de l'enseignant connecté,
    toutes classes et matières confondues — contrairement à
    liste_fiches_view, qui ne montre qu'UNE matière enseignée
    précise. Pas besoin de vérification d'accès supplémentaire ici :
    le filtre enseignant=enseignant garantit déjà qu'on ne voit que
    ses propres fiches.
    """
    enseignant = obtenir_enseignant_ou_403(request)

    fiches = FichePreparation.objects.filter(
        enseignant=enseignant
    ).select_related(
        'classe_matiere__classe', 'classe_matiere__matiere'
    ).order_by(
        F('date_prevue').asc(nulls_last=True), '-date_creation'
    )
    # nulls_last=True : les fiches sans date prévue (pas encore
    # planifiées) apparaissent à la FIN de la liste plutôt qu'au
    # début — plus logique pour un enseignant qui veut d'abord voir
    # ce qui approche.

    return render(request, 'pedagogie/mes_fiches.html', {
        'fiches': fiches,
    })


@login_required
def liste_fiches_view(request, classe_matiere_id):
    """
    Liste toutes les fiches de préparation déjà créées pour UNE
    matière enseignée précise.
    """
    enseignant = obtenir_enseignant_ou_403(request)
    classe_matiere = get_object_or_404(ClasseMatiere, id=classe_matiere_id)

    if not enseignant_a_acces_classe_matiere(enseignant, classe_matiere):
        raise PermissionDenied("Vous n'enseignez pas cette matière dans cette classe.")

    fiches = classe_matiere.fiches.order_by('-date_prevue', '-date_creation')

    return render(request, 'pedagogie/liste_fiches.html', {
        'classe_matiere': classe_matiere,
        'fiches': fiches,
    })


@login_required
def creer_fiche_view(request, classe_matiere_id):
    """
    Étape 1/2 : informations générales de la fiche (R.L.P., O.P.O.,
    type de leçon...). Une fois enregistrée, on enchaîne directement
    sur la saisie du déroulement (modifier_etapes_view).
    """
    enseignant = obtenir_enseignant_ou_403(request)
    classe_matiere = get_object_or_404(ClasseMatiere, id=classe_matiere_id)

    if not enseignant_a_acces_classe_matiere(enseignant, classe_matiere):
        raise PermissionDenied("Vous n'enseignez pas cette matière dans cette classe.")

    if request.method == 'POST':
        form = FichePreparationForm(request.POST, classe_matiere=classe_matiere)
        if form.is_valid():
            fiche = form.save(commit=False)
            fiche.classe_matiere = classe_matiere
            fiche.enseignant = enseignant
            fiche.save()
            messages.success(request, "Fiche créée. Complète maintenant le déroulement.")
            return redirect('pedagogie:modifier_etapes', fiche_id=fiche.id)
    else:
        form = FichePreparationForm(classe_matiere=classe_matiere)

    return render(request, 'pedagogie/creer_fiche.html', {
        'form': form,
        'classe_matiere': classe_matiere,
    })


@login_required
def modifier_fiche_view(request, fiche_id):
    """
    Corrige les informations générales d'une fiche déjà créée
    (sans toucher au déroulement, géré séparément).
    """
    enseignant = obtenir_enseignant_ou_403(request)
    fiche = get_object_or_404(FichePreparation, id=fiche_id)

    if not enseignant_a_acces_classe_matiere(enseignant, fiche.classe_matiere):
        raise PermissionDenied("Vous n'enseignez pas cette matière dans cette classe.")

    if request.method == 'POST':
        form = FichePreparationForm(request.POST, instance=fiche, classe_matiere=fiche.classe_matiere)
        if form.is_valid():
            form.save()
            messages.success(request, "Fiche mise à jour.")
            return redirect('pedagogie:detail_fiche', fiche_id=fiche.id)
    else:
        form = FichePreparationForm(instance=fiche, classe_matiere=fiche.classe_matiere)

    return render(request, 'pedagogie/creer_fiche.html', {
        'form': form,
        'classe_matiere': fiche.classe_matiere,
        'fiche': fiche,
    })


@login_required
def modifier_etapes_view(request, fiche_id):
    """
    Étape 2/2 : le déroulement pas-à-pas de la fiche.

    Le nombre de lignes VIDES proposées dépend du type_lecon de la
    fiche (6 pour la grammaire, 8 pour la conjugaison, 5 par défaut
    sinon) MOINS le nombre d'étapes déjà saisies — on ne réaffiche
    jamais plus de lignes vides que nécessaire si l'enseignant
    revient corriger une fiche déjà partiellement remplie.
    """
    enseignant = obtenir_enseignant_ou_403(request)
    fiche = get_object_or_404(FichePreparation, id=fiche_id)

    if not enseignant_a_acces_classe_matiere(enseignant, fiche.classe_matiere):
        raise PermissionDenied("Vous n'enseignez pas cette matière dans cette classe.")

    nombre_attendu = FichePreparation.NOMBRE_ETAPES_PAR_TYPE.get(
        fiche.type_lecon, FichePreparation.NOMBRE_ETAPES_DEFAUT
    )
    nombre_existant = fiche.etapes.count()
    nombre_lignes_vides = max(0, nombre_attendu - nombre_existant)

    # On (re)construit le formset avec le bon 'extra' à CHAQUE appel :
    # ce paramètre doit être fixé au moment de la création de la
    # classe de formset, pas de son instanciation — c'est une
    # contrainte de Django. On le calcule donc ici, dynamiquement,
    # pour CETTE fiche précise plutôt qu'une seule fois au chargement
    # du module (voir pedagogie/forms.py, où extra=0 par défaut).
    FormSetDynamique = inlineformset_factory(
        FichePreparation, EtapeFiche,
        fields=['numero_ordre', 'titre_etape', 'activite_maitre', 'activite_eleve', 'duree_minutes'],
        extra=nombre_lignes_vides,
        can_delete=True,
        widgets={
            'activite_maitre': forms.Textarea(attrs={'rows': 2}),
            'activite_eleve': forms.Textarea(attrs={'rows': 2}),
        },
    )

    if request.method == 'POST':
        formset = FormSetDynamique(request.POST, instance=fiche)
        if formset.is_valid():
            formset.save()
            messages.success(request, "Déroulement enregistré.")
            return redirect('pedagogie:detail_fiche', fiche_id=fiche.id)
    else:
        formset = FormSetDynamique(instance=fiche)

    return render(request, 'pedagogie/modifier_etapes.html', {
        'fiche': fiche,
        'formset': formset,
        'nombre_attendu': nombre_attendu,
    })


@login_required
def detail_fiche_view(request, fiche_id):
    """
    Affichage "propre" de la fiche complète, dans l'ordre officiel :
    en-tête (discipline, classe, durée, R.L.P., O.P.O.) puis le
    déroulement étape par étape — pensé pour être imprimé ou
    consulté juste avant de donner le cours.
    """
    enseignant = obtenir_enseignant_ou_403(request)
    fiche = get_object_or_404(FichePreparation, id=fiche_id)

    if not enseignant_a_acces_classe_matiere(enseignant, fiche.classe_matiere):
        raise PermissionDenied("Vous n'enseignez pas cette matière dans cette classe.")

    etapes = fiche.etapes.order_by('numero_ordre')

    return render(request, 'pedagogie/detail_fiche.html', {
        'fiche': fiche,
        'etapes': etapes,
    })


@login_required
@require_POST
def supprimer_fiche_view(request, fiche_id):
    """
    Supprime une fiche et toutes ses étapes (CASCADE déjà prévu sur
    EtapeFiche.fiche). Contrairement à une Evaluation, une fiche de
    préparation n'est référencée par PROTECT nulle part ailleurs :
    la suppression ne peut donc pas échouer pour cause de données
    liées, pas besoin de gérer un ProtectedError ici.
    """
    enseignant = obtenir_enseignant_ou_403(request)
    fiche = get_object_or_404(FichePreparation, id=fiche_id)

    if not enseignant_a_acces_classe_matiere(enseignant, fiche.classe_matiere):
        raise PermissionDenied("Vous n'enseignez pas cette matière dans cette classe.")

    classe_matiere_id = fiche.classe_matiere_id
    titre = fiche.titre
    fiche.delete()

    messages.success(request, f"La fiche « {titre} » a été supprimée.")
    return redirect('pedagogie:liste_fiches', classe_matiere_id=classe_matiere_id)