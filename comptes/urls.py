# ============================================================
# APP : comptes
# Fichier : urls.py (à créer, n'existe pas encore dans ton projet)
# Rôle : relier chaque URL à sa vue correspondante.
# ============================================================

from django.urls import path, reverse_lazy
from django.contrib.auth import views as auth_views
from . import views

app_name = 'comptes'
# app_name active le "namespacing" : dans les templates, on écrit
# {% url 'comptes:connexion' %} plutôt que juste {% url 'connexion' %}.
# Ça évite tout conflit si une AUTRE app avait aussi une URL nommée
# "connexion" un jour.

urlpatterns = [
    path('', views.accueil_view, name='accueil'),
    path('inscription/', views.inscription_view, name='inscription'),

    path(
        'connexion/',
        auth_views.LoginView.as_view(template_name='comptes/connexion.html'),
        name='connexion'
    ),

    path(
        'eleves/connexion/',
        auth_views.LoginView.as_view(
            template_name='comptes/eleve_connexion.html',
            # next_page (pas success_url, propre à LoginView) : sans
            # ça, un élève connecté serait redirigé vers le tableau
            # de bord ENSEIGNANT par défaut (LOGIN_REDIRECT_URL),
            # qui lui refuserait l'accès (403) faute de profil
            # enseignant — déroutant pour un élève.
            next_page=reverse_lazy('evaluations:eleve_tableau_bord'),
        ),
        name='eleve_connexion'
    ),
    # auth_views.LoginView : vue de connexion FOURNIE par Django.
    # On lui indique juste QUEL template utiliser pour l'affichage ;
    # toute la logique (vérifier le mot de passe, créer la session...)
    # est déjà écrite et testée par l'équipe Django elle-même.

    path(
        'deconnexion/',
        auth_views.LogoutView.as_view(),
        name='deconnexion'
    ),
    # Depuis Django 5, LogoutView n'accepte QUE les requêtes POST
    # (plus de simple lien <a href="deconnexion/">, il faut un
    # formulaire avec un bouton - voir base.html plus loin).

    path('tableau-de-bord/', views.tableau_bord_view, name='tableau_bord'),

    path(
        'mot-de-passe/',
        auth_views.PasswordChangeView.as_view(
            template_name='comptes/changer_mot_de_passe.html',
            # success_url : par défaut, PasswordChangeView redirige vers
            # une URL nommée 'password_change_done' SANS namespace, qui
            # n'existe pas dans notre projet (tout est sous 'comptes:').
            # On précise donc explicitement où aller après succès.
            success_url=reverse_lazy('comptes:mot_de_passe_change_fait'),
        ),
        name='changer_mot_de_passe'
    ),
    path(
        'mot-de-passe/confirmation/',
        auth_views.PasswordChangeDoneView.as_view(
            template_name='comptes/mot_de_passe_change_fait.html'
        ),
        name='mot_de_passe_change_fait'
    ),

    # --- "Mot de passe oublié ?" : 4 étapes fournies par Django ---
    # 1. L'enseignant saisit son e-mail -> un lien de réinitialisation
    #    (à durée de vie limitée) lui est envoyé par e-mail.
    # 2. Page "e-mail envoyé" (toujours affichée, MÊME si l'adresse
    #    n'existe pas en base : c'est volontaire, voir le template).
    # 3. En cliquant le lien reçu, il arrive sur le formulaire de
    #    nouveau mot de passe (le lien contient un jeton vérifié
    #    automatiquement par Django).
    # 4. Page de confirmation finale.
    path(
        'mot-de-passe-oublie/',
        auth_views.PasswordResetView.as_view(
            template_name='comptes/mot_de_passe_oublie.html',
            email_template_name='comptes/email_reinitialisation.txt',
            subject_template_name='comptes/email_reinitialisation_objet.txt',
            success_url=reverse_lazy('comptes:mot_de_passe_oublie_envoye'),
        ),
        name='mot_de_passe_oublie'
    ),
    path(
        'mot-de-passe-oublie/envoye/',
        auth_views.PasswordResetDoneView.as_view(
            template_name='comptes/mot_de_passe_oublie_envoye.html'
        ),
        name='mot_de_passe_oublie_envoye'
    ),
    path(
        'reinitialiser/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(
            template_name='comptes/reinitialiser_mot_de_passe.html',
            success_url=reverse_lazy('comptes:reinitialisation_terminee'),
        ),
        name='reinitialiser_mot_de_passe'
    ),
    path(
        'reinitialisation-terminee/',
        auth_views.PasswordResetCompleteView.as_view(
            template_name='comptes/reinitialisation_terminee.html'
        ),
        name='reinitialisation_terminee'
    ),
]
