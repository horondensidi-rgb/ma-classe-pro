# ============================================================
# APP : comptes
# Fichier : views.py
# Rôle : traiter l'inscription d'un enseignant, et afficher son
#        tableau de bord après connexion.
#
# La connexion (login) et la déconnexion (logout) elles-mêmes
# n'ont PAS besoin de vue personnalisée : Django fournit déjà
# LoginView et LogoutView, branchées directement dans urls.py.
# On ne code une vue que quand le comportement standard ne suffit
# pas — ici, l'inscription, car elle doit créer TROIS objets liés
# (User, Etablissement, Enseignant) en une seule fois.
# ============================================================

from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required

from django.contrib import messages

from .forms import InscriptionForm
from .models import Etablissement, PlanAbonnement, Enseignant
from .permissions import obtenir_enseignant_ou_403


def inscription_view(request):
    """
    Affiche le formulaire d'inscription (GET) et traite sa
    soumission (POST) : crée le User, récupère ou crée son
    Etablissement, l'inscrit sur le plan Gratuit par défaut,
    puis le connecte automatiquement.
    """

    if request.user.is_authenticated:
        # Si un utilisateur déjà connecté retombe sur cette page
        # (ex: en tapant l'URL manuellement), on le renvoie plutôt
        # vers son tableau de bord : pas besoin de se réinscrire.
        return redirect('comptes:tableau_bord')

    if request.method == 'POST':
        form = InscriptionForm(request.POST)

        if form.is_valid():
            # form.is_valid() déclenche TOUTES les validations :
            # celles de UserCreationForm (mots de passe identiques,
            # assez solides, username disponible...) ET les nôtres
            # (champs requis comme telephone, etablissement_nom...).

            user = form.save()
            # Ici, grâce à notre save() personnalisé dans forms.py,
            # le User est créé avec email/prénom/nom déjà remplis.

            etablissement, _cree = Etablissement.objects.get_or_create(
                nom=form.cleaned_data['etablissement_nom'],
                ville=form.cleaned_data['etablissement_ville'],
                defaults={'region': form.cleaned_data['etablissement_region']}
            )
            # get_or_create : cherche un Etablissement avec CE nom et
            # CETTE ville ; s'il existe déjà (un collègue du même
            # établissement s'est peut-être déjà inscrit), on le
            # réutilise plutôt que d'en créer un doublon. "_cree" est
            # un booléen (True si nouvellement créé) qu'on ignore ici
            # (d'où le nom commençant par _, convention Python pour
            # "je reçois cette valeur mais je ne m'en sers pas").

            plan_gratuit, _cree = PlanAbonnement.objects.get_or_create(
                nom='GRATUIT',
                defaults={
                    'prix_mensuel': 0,
                    'nombre_classes_max': 1,
                    'acces_ia_preparation': False,
                    'description': "Plan de découverte : 1 classe, fonctionnalités de base.",
                }
            )
            # Même logique : si le plan "GRATUIT" n'existe pas encore
            # en base (premher lancement du site), on le crée avec des
            # valeurs par défaut raisonnables, au lieu de planer une
            # erreur si l'admin a oublié de le créer à la main.

            Enseignant.objects.create(
                user=user,
                telephone=form.cleaned_data['telephone'],
                etablissement=etablissement,
                plan_abonnement=plan_gratuit,
            )

            login(request, user)
            # Connecte immédiatement le nouvel enseignant : il n'a
            # pas besoin de ressaisir son mot de passe juste après
            # avoir rempli le formulaire d'inscription.

            return redirect('comptes:tableau_bord')
    else:
        # GET : première visite de la page, formulaire vide.
        form = InscriptionForm()

    return render(request, 'comptes/inscription.html', {'form': form})


@login_required
def tableau_bord_view(request):
    """
    Page d'accueil après connexion : affiche un résumé des classes
    de l'enseignant (nombre d'élèves, matières enseignées).

    @login_required : décorateur Django qui bloque l'accès à cette
    vue si l'utilisateur n'est pas connecté, et le redirige
    automatiquement vers LOGIN_URL (configuré dans settings.py)
    au lieu de laisser planter la page.
    """
    from django.db.models import Q
    from django.core.exceptions import PermissionDenied
    from classes.models import Classe
    # Import à l'intérieur de la fonction (pas en haut du fichier) :
    # comptes est une app "de base" que classes importe déjà (voir
    # classes/models.py qui importe Enseignant). Si on importait
    # Classe tout en haut de comptes/views.py, on créerait un import
    # circulaire (classes a besoin de comptes, et comptes aurait
    # besoin de classes). L'import local évite ce problème.

    try:
        enseignant = obtenir_enseignant_ou_403(request)
    except PermissionDenied:
        # Cas typique : un compte superutilisateur créé via
        # `createsuperuser`, qui n'a jamais été créé via le
        # formulaire d'inscription et n'a donc pas de profil
        # Enseignant associé. Ici, contrairement aux autres vues,
        # on préfère un message d'accueil informatif plutôt qu'une
        # page 403 brute : le tableau de bord reste consultable
        # (juste vide), c'est une meilleure première expérience.
        messages.info(
            request,
            "Ce compte n'a pas de profil enseignant. "
            "Connectez-vous avec un compte créé via la page d'inscription, "
            "ou associez ce compte à un Enseignant depuis l'admin."
        )
        return render(request, 'comptes/tableau_bord.html', {'classes': []})

    classes = Classe.objects.filter(
        Q(enseignant_principal=enseignant) | Q(classematiere__enseignant=enseignant)
    ).distinct()

    from django.db.models import F
    from django.utils import timezone
    from pedagogie.models import FichePreparation
    # Mêmes raisons d'import local qu'au-dessus : éviter tout risque
    # d'import circulaire avec une app qui dépend elle-même de comptes.

    prochaines_fiches = FichePreparation.objects.filter(
        enseignant=enseignant,
    ).filter(
        Q(date_prevue__gte=timezone.localdate()) | Q(date_prevue__isnull=True)
        # On montre les fiches à venir OU sans date encore fixée —
        # PAS celles déjà passées, qui n'ont plus d'intérêt sur un
        # tableau de bord tourné vers "ce qui arrive".
    ).select_related(
        'classe_matiere__classe', 'classe_matiere__matiere'
    ).order_by(
        F('date_prevue').asc(nulls_last=True)
    )[:5]
    # [:5] : seulement un aperçu ici : la liste complète reste
    # accessible via le lien "Voir toutes mes fiches" du template.

    return render(request, 'comptes/tableau_bord.html', {
        'classes': classes,
        'prochaines_fiches': prochaines_fiches,
    })