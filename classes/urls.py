# ============================================================
# APP : classes
# Fichier : urls.py (à créer, n'existe pas encore)
# ============================================================

from django.urls import path
from . import views

app_name = 'classes'

urlpatterns = [
    path('', views.liste_classes_view, name='liste_classes'),
    path('<int:classe_id>/', views.detail_classe_view, name='detail_classe'),
    path('<int:classe_id>/ajouter-eleve/', views.ajouter_eleve_view, name='ajouter_eleve'),
    path('<int:classe_id>/eleves/<int:eleve_id>/', views.fiche_eleve_view, name='fiche_eleve'),
    path('<int:classe_id>/eleves/<int:eleve_id>/modifier/', views.modifier_eleve_view, name='modifier_eleve'),
    path(
        '<int:classe_id>/eleves/<int:eleve_id>/acces/',
        views.creer_ou_reinitialiser_acces_eleve_view,
        name='creer_acces_eleve'
    ),
    path('<int:classe_id>/emploi-du-temps/', views.emploi_du_temps_view, name='emploi_du_temps'),
    path('<int:classe_id>/emploi-du-temps/creer/', views.creer_creneau_view, name='creer_creneau'),
    path(
        '<int:classe_id>/emploi-du-temps/<int:creneau_id>/modifier/',
        views.modifier_creneau_view,
        name='modifier_creneau'
    ),
    path(
        '<int:classe_id>/emploi-du-temps/<int:creneau_id>/supprimer/',
        views.supprimer_creneau_view,
        name='supprimer_creneau'
    ),
    path('<int:classe_id>/eleves/<int:eleve_id>/desactiver/', views.desactiver_eleve_view, name='desactiver_eleve'),
    path('<int:classe_id>/eleves/<int:eleve_id>/reactiver/', views.reactiver_eleve_view, name='reactiver_eleve'),
]
# <int:classe_id> : capture un nombre entier dans l'URL et le passe
# à la vue sous le nom "classe_id" (doit correspondre exactement au
# nom du paramètre dans la signature de la fonction en views.py).
