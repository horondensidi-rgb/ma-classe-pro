# ============================================================
# APP : classes
# Fichier : views.py
# Rôle : afficher les classes de l'enseignant connecté, le détail
#        d'une classe (élèves + matières), et permettre d'ajouter
#        un élève.
# ============================================================

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.contrib import messages

import secrets
from django.contrib.auth.models import User
from django.db import IntegrityError

from comptes.permissions import obtenir_enseignant_ou_403
from .models import Classe, Eleve, JournalConsultation, Creneau
from .forms import EleveForm, CreneauForm
from .permissions import enseignant_a_acces_classe


@login_required
def liste_classes_view(request):
    """
    Affiche uniquement les classes où l'enseignant connecté
    intervient : soit comme enseignant_principal, soit parce
    qu'il donne au moins une matière dedans (via ClasseMatiere).
    """
    enseignant = obtenir_enseignant_ou_403(request)

    classes = Classe.objects.filter(
        Q(enseignant_principal=enseignant) | Q(classematiere__enseignant=enseignant)
    ).distinct()
    # Q(...) | Q(...) : combine deux conditions avec un "OU" logique
    # (impossible à écrire avec un simple .filter(a=1, b=2), qui
    # ferait un "ET"). .distinct() évite qu'une classe apparaisse
    # deux fois si l'enseignant est À LA FOIS principal ET titulaire
    # d'une matière dans cette classe.

    return render(request, 'classes/liste_classes.html', {
        'classes': classes,
    })


@login_required
def detail_classe_view(request, classe_id):
    """
    Affiche les élèves et les matières d'UNE classe précise.

    get_object_or_404 : si aucune Classe avec cet ID n'existe,
    Django renvoie directement une page d'erreur 404 propre, au
    lieu de planter avec une exception brute non gérée.
    """
    enseignant = obtenir_enseignant_ou_403(request)
    classe = get_object_or_404(Classe, id=classe_id)

    if not enseignant_a_acces_classe(enseignant, classe):
        # PermissionDenied : Django affiche automatiquement une
        # page 403 "Accès refusé". Sans CE contrôle, n'importe quel
        # enseignant connecté pouvait consulter les élèves (et leurs
        # données personnelles) de N'IMPORTE QUELLE classe en
        # changeant juste le nombre à la fin de l'URL.
        raise PermissionDenied("Vous n'avez pas accès à cette classe.")

    eleves_actifs = classe.eleves.filter(est_actif=True).order_by('nom', 'prenom')
    eleves_inactifs = classe.eleves.filter(est_actif=False).order_by('nom', 'prenom')
    # Deux requêtes séparées plutôt qu'une seule liste triée en Python :
    # plus simple à afficher en deux tableaux distincts dans le
    # template, et la base de données fait le tri/filtre plus
    # efficacement qu'une boucle Python le ferait.

    recherche = request.GET.get('q', '').strip()
    if recherche:
        # Q(...) | Q(...) : on cherche le texte saisi DANS matricule
        # OU prénom OU nom, peu importe lequel des trois correspond.
        # icontains : comparaison SANS tenir compte des majuscules/
        # minuscules ("kone" retrouve "Koné" aussi bien que "KONE").
        filtre_recherche = (
            Q(matricule__icontains=recherche)
            | Q(prenom__icontains=recherche)
            | Q(nom__icontains=recherche)
        )
        eleves_actifs = eleves_actifs.filter(filtre_recherche)
        eleves_inactifs = eleves_inactifs.filter(filtre_recherche)

    matieres = classe.classematiere_set.select_related('matiere', 'enseignant__user')
    # classe.classematiere_set : nom AUTOMATIQUE généré par Django
    # pour remonter vers ClasseMatiere depuis Classe, car on n'a PAS
    # défini de related_name explicite sur ce ForeignKey précis.
    # select_related : va chercher matiere et enseignant en une seule
    # requête SQL au lieu d'une requête par ligne affichée (plus rapide).

    return render(request, 'classes/detail_classe.html', {
        'classe': classe,
        'eleves_actifs': eleves_actifs,
        'eleves_inactifs': eleves_inactifs,
        'matieres': matieres,
        'recherche': recherche,
    })


@login_required
def modifier_eleve_view(request, classe_id, eleve_id):
    """
    Permet à l'enseignant de corriger les informations d'un élève
    qu'il a lui-même saisies (matricule, prénom, nom, sexe, date de
    naissance, tuteur...). Même formulaire que l'ajout (EleveForm),
    mais initialisé avec les données existantes via instance=eleve.
    """
    enseignant = obtenir_enseignant_ou_403(request)
    classe = get_object_or_404(Classe, id=classe_id)

    if not enseignant_a_acces_classe(enseignant, classe):
        raise PermissionDenied("Vous n'avez pas accès à cette classe.")

    eleve = get_object_or_404(Eleve, id=eleve_id, classe=classe)

    if request.method == 'POST':
        form = EleveForm(request.POST, instance=eleve)
        # instance=eleve : indique à Django de MODIFIER cet élève
        # précis au lieu d'en créer un nouveau. Sans ce paramètre,
        # ModelForm créerait systématiquement une nouvelle ligne.
        if form.is_valid():
            form.save()
            messages.success(request, f"Les informations de {eleve.nom_complet} ont été mises à jour.")
            return redirect('classes:fiche_eleve', classe_id=classe.id, eleve_id=eleve.id)
    else:
        form = EleveForm(instance=eleve)
        # Sans requête POST (première ouverture de la page), on
        # pré-remplit simplement le formulaire avec les valeurs
        # actuelles de l'élève.

    return render(request, 'classes/modifier_eleve.html', {
        'form': form,
        'classe': classe,
        'eleve': eleve,
    })


@login_required
def fiche_eleve_view(request, classe_id, eleve_id):
    """
    Fiche individuelle d'un élève : informations saisies par
    l'enseignant + notes obtenues, regroupées par trimestre.

    Règle de visibilité des notes : un enseignant ne voit que les
    notes des matières QU'IL enseigne. Le titulaire de la classe
    (enseignant_principal) voit toutes les matières, car il a un
    rôle de suivi global de ses élèves.
    """
    from evaluations.models import Copie
    # Import local pour éviter un import circulaire, comme déjà
    # fait dans comptes/views.py (evaluations dépend de classes).

    enseignant = obtenir_enseignant_ou_403(request)
    classe = get_object_or_404(Classe, id=classe_id)

    if not enseignant_a_acces_classe(enseignant, classe):
        raise PermissionDenied("Vous n'avez pas accès à cette classe.")

    eleve = get_object_or_404(Eleve, id=eleve_id, classe=classe)

    JournalConsultation.objects.create(
        utilisateur=request.user,
        eleve=eleve,
        origine='ENSEIGNANT',
    )
    # Une ligne d'audit par ouverture de cette page — volontairement
    # placée APRÈS la vérification de permission : si l'accès est
    # refusé (403), on ne veut pas enregistrer une "consultation" qui
    # n'a en réalité jamais eu lieu.

    copies = Copie.objects.filter(
        eleve=eleve,
        note_obtenue__isnull=False,
    ).select_related('evaluation__classe_matiere__matiere')
    # select_related suit toute la chaîne de relations en UNE requête
    # SQL (copie -> évaluation -> classe_matiere -> matière), au lieu
    # d'une requête par ligne affichée dans le tableau.

    if classe.enseignant_principal_id != enseignant.id:
        # Enseignant simple : on restreint à SES matières uniquement.
        copies = copies.filter(evaluation__classe_matiere__enseignant=enseignant)

    # --- Filtres optionnels, lus dans l'URL (méthode GET) ---
    # Exemple : /fiche/?trimestre=2&mois=11
    # Un filtre absent ou vide = "Tous" (aucune restriction).
    trimestre_choisi = request.GET.get('trimestre', '')
    mois_choisi = request.GET.get('mois', '')

    if trimestre_choisi.isdigit() and int(trimestre_choisi) in (1, 2, 3):
        copies = copies.filter(evaluation__trimestre=int(trimestre_choisi))
    else:
        trimestre_choisi = ''
    # .isdigit() + vérification de la plage : on ne fait JAMAIS
    # confiance à ce qui arrive dans l'URL. Quelqu'un pourrait taper
    # ?trimestre=abc ; sans cette validation, int('abc') ferait
    # planter la page. Une valeur invalide est simplement ignorée.

    if mois_choisi.isdigit() and 1 <= int(mois_choisi) <= 12:
        copies = copies.filter(evaluation__date_evaluation__month=int(mois_choisi))
        # __month : extrait le numéro du mois de la date (1 à 12).
        # Sans ambiguïté sur une année scolaire (sept. à juin), car
        # aucun mois n'y apparaît deux fois.
    else:
        mois_choisi = ''

    copies = copies.order_by(
        'evaluation__date_evaluation',
        'evaluation__classe_matiere__matiere__nom',
    )

    return render(request, 'classes/fiche_eleve.html', {
        'classe': classe,
        'eleve': eleve,
        'copies': copies,
        'trimestre_choisi': trimestre_choisi,
        'mois_choisi': mois_choisi,
        'trimestres': [(1, '1er trimestre'), (2, '2ème trimestre'), (3, '3ème trimestre')],
        'mois_liste': [
            (1, 'Janvier'), (2, 'Février'), (3, 'Mars'), (4, 'Avril'),
            (5, 'Mai'), (6, 'Juin'), (7, 'Juillet'), (8, 'Août'),
            (9, 'Septembre'), (10, 'Octobre'), (11, 'Novembre'), (12, 'Décembre'),
        ],
    })


@login_required
@require_POST
def creer_ou_reinitialiser_acces_eleve_view(request, classe_id, eleve_id):
    """
    Crée l'accès à l'espace élève (première fois), ou réinitialise
    son mot de passe (si l'élève l'a oublié — pas de "mot de passe
    oublié" par e-mail côté élève, beaucoup n'en ayant pas).

    Identifiant = matricule de l'élève (déjà unique). Mot de passe =
    un code à 6 chiffres généré aléatoirement, affiché UNE SEULE FOIS
    à l'enseignant via un message — à communiquer oralement ou par
    écrit à l'élève. On ne le stocke jamais en clair : Django le
    hache immédiatement via set_password()/create_user().
    """
    enseignant = obtenir_enseignant_ou_403(request)
    classe = get_object_or_404(Classe, id=classe_id)

    if not enseignant_a_acces_classe(enseignant, classe):
        raise PermissionDenied("Vous n'avez pas accès à cette classe.")

    eleve = get_object_or_404(Eleve, id=eleve_id, classe=classe)

    code_genere = ''.join(secrets.choice('0123456789') for _ in range(6))
    # secrets.choice (pas random.choice) : générateur cryptographiquement
    # sûr, adapté à la génération de mots de passe/codes d'accès.

    if eleve.compte_utilisateur:
        eleve.compte_utilisateur.set_password(code_genere)
        eleve.compte_utilisateur.save()
        messages.success(
            request,
            f"Nouveau code d'accès pour {eleve.nom_complet} — "
            f"Identifiant : {eleve.matricule} — Code : {code_genere}"
        )
    else:
        try:
            utilisateur = User.objects.create_user(
                username=eleve.matricule,
                password=code_genere,
            )
        except IntegrityError:
            # Cas très rare : un compte avec ce nom d'utilisateur
            # existe déjà (collision improbable avec un identifiant
            # enseignant). On informe plutôt que de laisser planter.
            messages.error(
                request,
                f"Impossible de créer l'accès : l'identifiant "
                f"{eleve.matricule} est déjà utilisé par un autre compte."
            )
            return redirect('classes:fiche_eleve', classe_id=classe.id, eleve_id=eleve.id)

        eleve.compte_utilisateur = utilisateur
        eleve.save(update_fields=['compte_utilisateur'])
        messages.success(
            request,
            f"Accès créé pour {eleve.nom_complet} — "
            f"Identifiant : {eleve.matricule} — Code : {code_genere}"
        )

    return redirect('classes:fiche_eleve', classe_id=classe.id, eleve_id=eleve.id)


@login_required
@require_POST
# @require_POST : refuse toute requête GET sur cette vue (ex: si
# quelqu'un essaie d'ouvrir l'URL directement dans le navigateur).
# Une action qui MODIFIE des données ne doit jamais être accessible
# par un simple lien/GET, seulement par un formulaire soumis en POST.
def desactiver_eleve_view(request, classe_id, eleve_id):
    """
    "Retire" un élève de la liste active, SANS le supprimer de la
    base : on bascule juste est_actif à False. Ça préserve tout
    l'historique (notes, bulletins) déjà lié à cet élève, que
    Django refuserait de toute façon de supprimer (PROTECT).
    """
    enseignant = obtenir_enseignant_ou_403(request)
    classe = get_object_or_404(Classe, id=classe_id)

    if not enseignant_a_acces_classe(enseignant, classe):
        raise PermissionDenied("Vous n'avez pas accès à cette classe.")

    eleve = get_object_or_404(Eleve, id=eleve_id, classe=classe)
    # On filtre AUSSI par classe=classe (pas seulement id=eleve_id) :
    # ça empêche de désactiver un élève d'une AUTRE classe en
    # modifiant l'ID dans l'URL par erreur ou intentionnellement.

    eleve.est_actif = False
    eleve.save(update_fields=['est_actif'])

    messages.success(request, f"{eleve.nom_complet} a été retiré de la liste des élèves actifs.")
    return redirect('classes:detail_classe', classe_id=classe.id)


@login_required
@require_POST
def reactiver_eleve_view(request, classe_id, eleve_id):
    """
    Symétrique de la vue précédente : permet d'annuler une
    désactivation faite par erreur, sans repasser par l'admin.
    """
    enseignant = obtenir_enseignant_ou_403(request)
    classe = get_object_or_404(Classe, id=classe_id)

    if not enseignant_a_acces_classe(enseignant, classe):
        raise PermissionDenied("Vous n'avez pas accès à cette classe.")

    eleve = get_object_or_404(Eleve, id=eleve_id, classe=classe)

    eleve.est_actif = True
    eleve.save(update_fields=['est_actif'])

    messages.success(request, f"{eleve.nom_complet} a été réactivé.")
    return redirect('classes:detail_classe', classe_id=classe.id)


@login_required
def ajouter_eleve_view(request, classe_id):
    """
    Formulaire d'ajout d'un élève dans une classe précise
    (l'ID de la classe vient de l'URL, pas d'un champ du formulaire).
    """
    enseignant = obtenir_enseignant_ou_403(request)
    classe = get_object_or_404(Classe, id=classe_id)

    if not enseignant_a_acces_classe(enseignant, classe):
        raise PermissionDenied("Vous n'avez pas accès à cette classe.")

    if request.method == 'POST':
        form = EleveForm(request.POST)
        if form.is_valid():
            eleve = form.save(commit=False)
            # commit=False : on complète l'objet en mémoire avant
            # de l'écrire réellement en base, comme pour InscriptionForm.
            eleve.classe = classe
            eleve.save()
            messages.success(request, f"{eleve.nom_complet} a été ajouté à la classe.")
            # messages.success : stocke un message flash affiché une
            # seule fois, à la prochaine page chargée (voir base.html
            # à compléter pour l'afficher - détail plus bas).
            return redirect('classes:detail_classe', classe_id=classe.id)
    else:
        form = EleveForm()

    return render(request, 'classes/ajouter_eleve.html', {
        'form': form,
        'classe': classe,
    })


@login_required
def emploi_du_temps_view(request, classe_id):
    """
    Affiche l'emploi du temps complet d'une classe, regroupé par
    jour de la semaine.
    """
    enseignant = obtenir_enseignant_ou_403(request)
    classe = get_object_or_404(Classe, id=classe_id)

    if not enseignant_a_acces_classe(enseignant, classe):
        raise PermissionDenied("Vous n'avez pas accès à cette classe.")

    creneaux = Creneau.objects.filter(
        classe_matiere__classe=classe
    ).select_related('classe_matiere__matiere', 'classe_matiere__enseignant__user')
    # Déjà triés par jour_semaine puis heure_debut grâce au Meta.ordering
    # du modèle Creneau — pas besoin de repréciser .order_by() ici.

    # On regroupe par jour sous forme de LISTE DE TUPLES (pas un
    # dictionnaire) : Django ne sait pas faire dictionnaire[variable]
    # dans un template, donc transmettre {code: [...]} obligerait à
    # une astuce. Une liste de (code, libelle, liste_de_creneaux) se
    # parcourt directement avec un simple {% for %}, sans contorsion.
    emploi_par_jour = {code: [] for code, _ in Creneau.JOUR_CHOICES}
    for creneau in creneaux:
        emploi_par_jour[creneau.jour_semaine].append(creneau)

    jours_avec_creneaux = [
        (libelle, emploi_par_jour[code])
        for code, libelle in Creneau.JOUR_CHOICES
    ]

    return render(request, 'classes/emploi_du_temps.html', {
        'classe': classe,
        'jours_avec_creneaux': jours_avec_creneaux,
    })


@login_required
def creer_creneau_view(request, classe_id):
    enseignant = obtenir_enseignant_ou_403(request)
    classe = get_object_or_404(Classe, id=classe_id)

    if not enseignant_a_acces_classe(enseignant, classe):
        raise PermissionDenied("Vous n'avez pas accès à cette classe.")

    if request.method == 'POST':
        form = CreneauForm(request.POST, classe=classe)
        if form.is_valid():
            form.save()
            messages.success(request, "Créneau ajouté à l'emploi du temps.")
            return redirect('classes:emploi_du_temps', classe_id=classe.id)
        # Si form.is_valid() est False à cause d'un chevauchement
        # (voir Creneau.clean()), l'erreur apparaît automatiquement
        # dans form.non_field_errors() au rendu du template.
    else:
        form = CreneauForm(classe=classe)

    return render(request, 'classes/creer_creneau.html', {
        'form': form,
        'classe': classe,
    })


@login_required
def modifier_creneau_view(request, classe_id, creneau_id):
    enseignant = obtenir_enseignant_ou_403(request)
    classe = get_object_or_404(Classe, id=classe_id)

    if not enseignant_a_acces_classe(enseignant, classe):
        raise PermissionDenied("Vous n'avez pas accès à cette classe.")

    creneau = get_object_or_404(Creneau, id=creneau_id, classe_matiere__classe=classe)

    if request.method == 'POST':
        form = CreneauForm(request.POST, instance=creneau, classe=classe)
        if form.is_valid():
            form.save()
            messages.success(request, "Créneau mis à jour.")
            return redirect('classes:emploi_du_temps', classe_id=classe.id)
    else:
        form = CreneauForm(instance=creneau, classe=classe)

    return render(request, 'classes/creer_creneau.html', {
        'form': form,
        'classe': classe,
        'creneau': creneau,
    })


@login_required
@require_POST
def supprimer_creneau_view(request, classe_id, creneau_id):
    enseignant = obtenir_enseignant_ou_403(request)
    classe = get_object_or_404(Classe, id=classe_id)

    if not enseignant_a_acces_classe(enseignant, classe):
        raise PermissionDenied("Vous n'avez pas accès à cette classe.")

    creneau = get_object_or_404(Creneau, id=creneau_id, classe_matiere__classe=classe)
    creneau.delete()
    messages.success(request, "Créneau supprimé.")

    return redirect('classes:emploi_du_temps', classe_id=classe.id)
