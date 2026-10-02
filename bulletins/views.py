# ============================================================
# APP : bulletins
# Fichier : views.py (nouveau fichier)
# Rôle : générer les bulletins d'une classe pour un trimestre
#        donné (calcul en masse), afficher le classement de la
#        classe, et le bulletin détaillé d'un élève.
# ============================================================

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.contrib import messages
from django.http import HttpResponse

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
# reportlab n'est pas installé par défaut : `pip install reportlab`
# dans ton environnement virtuel Termux avant de tester cette vue.

from comptes.permissions import obtenir_enseignant_ou_403
from classes.models import Classe, Eleve
from classes.permissions import enseignant_a_acces_classe
from .models import Bulletin, LigneBulletin

TRIMESTRES = [(1, '1er trimestre'), (2, '2ème trimestre'), (3, '3ème trimestre')]


@login_required
def generer_bulletins_view(request, classe_id):
    """
    Étape 1 (GET) : demande quel trimestre traiter.
    Étape 2 (POST) : crée/actualise le Bulletin de CHAQUE élève actif
    de la classe, avec une LigneBulletin par matière enseignée,
    recalcule toutes les moyennes, puis le classement de la classe.

    C'est une opération "en masse" volontairement idempotente :
    la relancer plusieurs fois (ex: après avoir corrigé une note
    oubliée) ne crée jamais de doublon, grâce à get_or_create et
    aux contraintes unique_together déjà posées sur les modèles.
    """
    enseignant = obtenir_enseignant_ou_403(request)
    classe = get_object_or_404(Classe, id=classe_id)

    if not enseignant_a_acces_classe(enseignant, classe):
        raise PermissionDenied("Vous n'avez pas accès à cette classe.")

    if request.method == 'POST':
        trimestre = int(request.POST.get('trimestre'))

        eleves = classe.eleves.filter(est_actif=True)
        classes_matieres = classe.classematiere_set.all()

        for eleve in eleves:
            bulletin, _cree = Bulletin.objects.get_or_create(
                eleve=eleve,
                classe=classe,
                trimestre=trimestre,
            )
            for classe_matiere in classes_matieres:
                ligne, _cree = LigneBulletin.objects.get_or_create(
                    bulletin=bulletin,
                    classe_matiere=classe_matiere,
                )
                # C'est ICI que la formule malienne (note de classe +
                # 2 × composition) / 3 est appliquée, matière par
                # matière — voir bulletins/models.py.
                ligne.calculer_moyenne_depuis_copies()

            bulletin.calculer_moyenne_generale()

        # Une fois TOUS les élèves recalculés, on peut établir les
        # classements — le rang de chacun dépend des moyennes de
        # tous les autres, donc ça doit venir en DERNIER.
        Bulletin.calculer_classement(classe, trimestre)
        for classe_matiere in classes_matieres:
            # Classement propre à CHAQUE matière (ex: rang en
            # Mathématiques), en plus du classement général déjà
            # calculé ci-dessus.
            LigneBulletin.calculer_classement_matiere(classe_matiere, trimestre)

        messages.success(
            request,
            f"Bulletins générés pour {eleves.count()} élève(s) — {dict(TRIMESTRES)[trimestre]}."
        )
        return redirect('bulletins:liste_classe', classe_id=classe.id, trimestre=trimestre)

    return render(request, 'bulletins/generer.html', {
        'classe': classe,
        'trimestres': TRIMESTRES,
    })


@login_required
def liste_classe_view(request, classe_id, trimestre):
    """
    Classement de la classe pour un trimestre : un élève par ligne,
    trié par rang.
    """
    enseignant = obtenir_enseignant_ou_403(request)
    classe = get_object_or_404(Classe, id=classe_id)

    if not enseignant_a_acces_classe(enseignant, classe):
        raise PermissionDenied("Vous n'avez pas accès à cette classe.")

    bulletins = Bulletin.objects.filter(
        classe=classe, trimestre=trimestre
    ).select_related('eleve').order_by('rang', 'eleve__nom')

    return render(request, 'bulletins/liste_classe.html', {
        'classe': classe,
        'trimestre': trimestre,
        'trimestre_libelle': dict(TRIMESTRES).get(trimestre, ''),
        'trimestres_disponibles': TRIMESTRES,
        'bulletins': bulletins,
    })


@login_required
def detail_bulletin_view(request, classe_id, eleve_id, trimestre):
    """
    Le bulletin d'UN élève : une ligne par matière (note de classe,
    note de composition, moyenne), plus la moyenne générale et le rang.
    """
    enseignant = obtenir_enseignant_ou_403(request)
    classe = get_object_or_404(Classe, id=classe_id)

    if not enseignant_a_acces_classe(enseignant, classe):
        raise PermissionDenied("Vous n'avez pas accès à cette classe.")

    eleve = get_object_or_404(Eleve, id=eleve_id, classe=classe)
    bulletin = get_object_or_404(Bulletin, classe=classe, eleve=eleve, trimestre=trimestre)

    lignes = bulletin.lignes.select_related(
        'classe_matiere__matiere'
    ).order_by('classe_matiere__matiere__nom')

    return render(request, 'bulletins/detail_eleve.html', {
        'classe': classe,
        'eleve': eleve,
        'bulletin': bulletin,
        'lignes': lignes,
        'trimestre_libelle': dict(TRIMESTRES).get(trimestre, ''),
    })


# ============================================================
# COULEURS DE MARQUE, réutilisées telles quelles depuis
# static/comptes/css/style.css, pour que le PDF garde la même
# identité visuelle que le site plutôt qu'un rendu générique.
# ============================================================
_COULEUR_ENCRE = colors.HexColor('#25313D')
_COULEUR_ACCENT = colors.HexColor('#B6742B')
_COULEUR_TRAIT = colors.HexColor('#D8CFC0')
_COULEUR_FOND_TOTAL = colors.HexColor('#F1ECE1')


@login_required
def telecharger_bulletin_pdf_view(request, classe_id, eleve_id, trimestre):
    """
    Génère le bulletin de l'élève en PDF téléchargeable, avec la
    même structure que le bulletin papier officiel : Discipline |
    Note de classe | Composition | Moyenne | Coef | Moyenne coéf. |
    Rang | Appréciation, suivi de la moyenne générale et du rang.

    On construit le PDF directement dans la RÉPONSE HTTP (response
    sert à la fois de "fichier" pour reportlab et de corps de la
    réponse) : aucun fichier temporaire n'est écrit sur le disque
    du téléphone/serveur, ce qui est plus simple et plus sûr.
    """
    enseignant = obtenir_enseignant_ou_403(request)
    classe = get_object_or_404(Classe, id=classe_id)

    if not enseignant_a_acces_classe(enseignant, classe):
        raise PermissionDenied("Vous n'avez pas accès à cette classe.")

    eleve = get_object_or_404(Eleve, id=eleve_id, classe=classe)
    bulletin = get_object_or_404(Bulletin, classe=classe, eleve=eleve, trimestre=trimestre)
    lignes = bulletin.lignes.select_related('classe_matiere__matiere').order_by('classe_matiere__matiere__nom')

    response = HttpResponse(content_type='application/pdf')
    # On construit le nom de fichier à partir du MATRICULE plutôt que
    # du prénom/nom : garanti unique et toujours composé de caractères
    # simples, ce qui évite tout souci d'encodage dans l'en-tête HTTP
    # Content-Disposition (les caractères accentués y sont plus délicats).
    response['Content-Disposition'] = (
        f'attachment; filename="bulletin_{eleve.matricule}_T{trimestre}.pdf"'
    )

    document = SimpleDocTemplate(
        response,
        pagesize=A4,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
    )

    styles = getSampleStyleSheet()
    style_titre = ParagraphStyle(
        'TitreBulletin', parent=styles['Title'],
        fontSize=15, alignment=TA_CENTER, textColor=_COULEUR_ENCRE, spaceAfter=4,
    )
    style_info = ParagraphStyle('Info', parent=styles['Normal'], fontSize=10)
    style_etablissement = ParagraphStyle(
        'Etablissement', parent=styles['Heading3'], textColor=_COULEUR_ENCRE,
    )

    elements = []

    # --- En-tête établissement ---
    elements.append(Paragraph(classe.etablissement.nom, style_etablissement))
    elements.append(Paragraph(
        f"{classe.etablissement.ville} — Année scolaire {classe.annee_scolaire.libelle}",
        style_info
    ))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("BULLETIN DE NOTES", style_titre))
    elements.append(Paragraph(dict(TRIMESTRES).get(trimestre, ''), style_info))
    elements.append(Spacer(1, 14))

    # --- Informations de l'élève ---
    date_naissance_affichee = (
        eleve.date_naissance.strftime('%d/%m/%Y') if eleve.date_naissance else '—'
    )
    infos = [
        [f"Prénom : {eleve.prenom}", f"Nom : {eleve.nom}"],
        [f"Né(e) le : {date_naissance_affichee}", f"Classe : {classe.nom}"],
        [f"Matricule : {eleve.matricule}", f"Effectif : {bulletin.effectif_classe or '—'}"],
    ]
    table_infos = Table(infos, colWidths=[9 * cm, 8 * cm])
    table_infos.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(table_infos)
    elements.append(Spacer(1, 12))

    if not lignes:
        elements.append(Paragraph("Aucune ligne de bulletin pour ce trimestre.", style_info))
        document.build(elements)
        return response

    # --- Tableau des notes, matière par matière ---
    entetes = ['Discipline', 'Classe', 'Compo', 'Moy.', 'Coef', 'Moy.Coef', 'Rang', 'Appréciation']
    donnees = [entetes]

    for ligne in lignes:
        donnees.append([
            ligne.classe_matiere.matiere.nom,
            str(ligne.moyenne_devoirs) if ligne.moyenne_devoirs is not None else '—',
            str(ligne.moyenne_composition) if ligne.moyenne_composition is not None else '—',
            str(ligne.moyenne) if ligne.moyenne is not None else '—',
            str(ligne.classe_matiere.coefficient),
            str(ligne.moyenne_coefficiee) if ligne.moyenne_coefficiee is not None else '—',
            str(ligne.rang_matiere) if ligne.rang_matiere else '—',
            ligne.appreciation or '—',
        ])

    total_coefficients = sum(ligne.classe_matiere.coefficient for ligne in lignes)
    total_moyenne_coefficiee = sum(
        ligne.moyenne_coefficiee for ligne in lignes if ligne.moyenne_coefficiee is not None
    )
    donnees.append(['TOTAL', '', '', '', str(total_coefficients), f"{total_moyenne_coefficiee:.2f}", '', ''])

    table_notes = Table(
        donnees,
        colWidths=[3.4 * cm, 1.6 * cm, 1.6 * cm, 1.5 * cm, 1.2 * cm, 1.9 * cm, 1.3 * cm, 4 * cm],
        repeatRows=1,
        # repeatRows=1 : si le tableau déborde sur une deuxième page
        # (beaucoup de matières), l'en-tête se répète automatiquement
        # en haut de chaque page suivante.
    )
    table_notes.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), _COULEUR_ENCRE),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, _COULEUR_TRAIT),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('ALIGN', (0, 1), (0, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BACKGROUND', (0, -1), (-1, -1), _COULEUR_FOND_TOTAL),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(table_notes)
    elements.append(Spacer(1, 16))

    # --- Moyenne générale et rang, mis en évidence ---
    rang_affiche = bulletin.rang or '—'
    if bulletin.effectif_classe:
        rang_affiche = f"{rang_affiche} / {bulletin.effectif_classe}"

    resultat = [[
        f"Moyenne générale : {bulletin.moyenne_generale or '—'} / 20",
        f"Rang : {rang_affiche}",
    ]]
    table_resultat = Table(resultat, colWidths=[9 * cm, 8 * cm])
    table_resultat.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('TEXTCOLOR', (0, 0), (-1, -1), _COULEUR_ENCRE),
    ]))
    elements.append(table_resultat)
    elements.append(Spacer(1, 40))

    # --- Ligne de signature ---
    elements.append(Paragraph("Le Chef d'Établissement", style_info))

    document.build(elements)
    return response