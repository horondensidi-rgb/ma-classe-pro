"""
Django settings for ecole_project project.

Version adaptée pour le déploiement (Render + PostgreSQL), tout en
restant utilisable en local sur Termux sans configuration lourde :
chaque réglage sensible a une valeur de secours ("fallback") pour le
développement si la variable d'environnement correspondante est absente.
"""

import os
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# load_dotenv lit un fichier .env À LA RACINE du projet (s'il existe)
# et en copie le contenu dans os.environ, COMME SI tu avais fait
# `export VARIABLE=valeur` toi-même dans le terminal. En local sur
# Termux, c'est le moyen le plus simple de définir SECRET_KEY, etc.
# sans les taper à chaque démarrage. Sur Render, ce fichier n'existe
# pas : load_dotenv() ne fait alors simplement rien (aucune erreur),
# car Render fournit déjà les variables d'environnement autrement.
load_dotenv(BASE_DIR / '.env')


# ------------------------------------------------------------
# SECRET_KEY : ne JAMAIS garder une valeur en clair dans le code
# une fois le projet déployé ou poussé sur GitHub. La valeur de
# secours ci-dessous ne sert QUE si aucune variable d'environnement
# n'est définie (donc en local, pour ne pas bloquer un premier test).
# ------------------------------------------------------------
SECRET_KEY = os.environ.get('SECRET_KEY')

# DEBUG : False par défaut (sûr). En local, si tu veux retrouver les
# pages d'erreur détaillées de Django pendant le développement, crée
# un fichier .env contenant la ligne : DEBUG=True
DEBUG = os.environ.get('DEBUG', 'False') == 'True'

# ALLOWED_HOSTS : liste séparée par des virgules dans la variable
# d'environnement, ex: "monecole.onrender.com,monecole.ml"
# Les valeurs de secours couvrent le développement local (Termux,
# navigateur sur le même téléphone).
ALLOWED_HOSTS = os.environ.get(
    'ALLOWED_HOSTS', '127.0.0.1,localhost'
).split(',')


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'comptes',
    'classes',
    'evaluations',
    'pedagogie',
    'rapports',
    'bulletins',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    # WhiteNoise juste après SecurityMiddleware (position exigée par
    # sa documentation) : permet à Django lui-même de servir les
    # fichiers CSS/JS en production, sans serveur web séparé (nginx)
    # ni service externe — suffisant pour un pilote de cette taille.
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'ecole_project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'ecole_project.wsgi.application'


# ------------------------------------------------------------
# Base de données : PostgreSQL si DATABASE_URL est définie (c'est le
# cas sur Render/Neon/Supabase, qui te la fournissent automatiquement
# une fois la base créée), sinon SQLite EN LOCAL uniquement — pour
# continuer à développer sur Termux sans dépendre d'une connexion
# internet à une base distante à chaque test.
# ------------------------------------------------------------
DATABASES = {
    'default': dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
    )
}


AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


LANGUAGE_CODE = 'fr-fr'
TIME_ZONE = 'Africa/Bamako'
USE_I18N = True
USE_TZ = True


# ------------------------------------------------------------
# Fichiers statiques (CSS)
# ------------------------------------------------------------
STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
# STATIC_ROOT : dossier où `collectstatic` RASSEMBLE tous les fichiers
# statiques de toutes les apps avant déploiement. STATICFILES_DIRS
# (déjà présent) sert au développement ; STATIC_ROOT sert à la mise
# en production — les deux sont nécessaires, ils ne se remplacent pas.

STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
        # Compresse (gzip) et nomme chaque fichier avec un hash de son
        # contenu (ex: style.a3f8c1.css) : le navigateur peut mettre
        # ces fichiers en cache INDÉFINIMENT sans risquer d'afficher
        # une vieille version après une mise à jour du design.
    },
}


LOGIN_URL = 'comptes:connexion'
LOGIN_REDIRECT_URL = 'comptes:tableau_bord'
LOGOUT_REDIRECT_URL = 'comptes:connexion'
DEFAULT_FROM_EMAIL = os.environ.get(
    'DEFAULT_FROM_EMAIL', 'Ma Classe Pro <noreply@maclassepro.local>'
)


# ------------------------------------------------------------
# E-mail : console en local (rien n'est réellement envoyé, le message
# s'affiche juste dans le terminal) ; SMTP réel si les variables
# d'environnement EMAIL_HOST sont définies (ex: avec Brevo une fois
# déployé), sans avoir à changer une seule ligne de code entre les
# deux environnements.
# ------------------------------------------------------------
if os.environ.get('EMAIL_HOST'):
    MAILERS = {
        'default': {
            'BACKEND': 'django.core.mail.backends.smtp.EmailBackend',
            'HOST': os.environ.get('EMAIL_HOST'),
            'PORT': int(os.environ.get('EMAIL_PORT', 587)),
            'USERNAME': os.environ.get('EMAIL_HOST_USER'),
            'PASSWORD': os.environ.get('EMAIL_HOST_PASSWORD'),
            'USE_TLS': os.environ.get('EMAIL_USE_TLS', 'True') == 'True',
        },
    }
else:
    MAILERS = {
        'default': {
            'BACKEND': 'django.core.mail.backends.console.EmailBackend',
        },
    }


# ------------------------------------------------------------
# Durcissement de sécurité, actif UNIQUEMENT quand DEBUG=False
# (donc jamais gênant en développement local).
# ------------------------------------------------------------
if not DEBUG:
    # Render (et la plupart des hébergeurs gratuits) placent
    # l'application derrière un proxy qui gère le HTTPS lui-même et
    # transmet la requête en HTTP en interne. Sans cet en-tête,
    # Django croirait à tort que CHAQUE requête est en HTTP non
    # sécurisé, et les cookies "Secure" ci-dessous seraient alors
    # systématiquement rejetés par le navigateur.
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
