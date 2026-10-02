# ============================================================
# APP : bulletins
# Fichier : urls.py (nouveau fichier)
# ============================================================

from django.urls import path
from . import views

app_name = 'bulletins'

urlpatterns = [
    path('<int:classe_id>/generer/', views.generer_bulletins_view, name='generer'),
    path('<int:classe_id>/trimestre/<int:trimestre>/', views.liste_classe_view, name='liste_classe'),
    path(
        '<int:classe_id>/eleves/<int:eleve_id>/trimestre/<int:trimestre>/',
        views.detail_bulletin_view,
        name='detail_eleve'
    ),
    path(
        '<int:classe_id>/eleves/<int:eleve_id>/trimestre/<int:trimestre>/pdf/',
        views.telecharger_bulletin_pdf_view,
        name='telecharger_pdf'
    ),
]