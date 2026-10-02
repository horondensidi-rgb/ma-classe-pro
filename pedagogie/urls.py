# ============================================================
# APP : pedagogie
# Fichier : urls.py (nouveau fichier)
# ============================================================

from django.urls import path
from . import views

app_name = 'pedagogie'

urlpatterns = [
    path('mes-fiches/', views.mes_fiches_view, name='mes_fiches'),
    path('nouvelle-fiche/', views.choisir_matiere_view, name='choisir_matiere'),
    path(
        'classe-matiere/<int:classe_matiere_id>/',
        views.liste_fiches_view,
        name='liste_fiches'
    ),
    path(
        'classe-matiere/<int:classe_matiere_id>/creer/',
        views.creer_fiche_view,
        name='creer_fiche'
    ),
    path('<int:fiche_id>/', views.detail_fiche_view, name='detail_fiche'),
    path('<int:fiche_id>/modifier/', views.modifier_fiche_view, name='modifier_fiche'),
    path('<int:fiche_id>/etapes/', views.modifier_etapes_view, name='modifier_etapes'),
    path('<int:fiche_id>/supprimer/', views.supprimer_fiche_view, name='supprimer_fiche'),
]