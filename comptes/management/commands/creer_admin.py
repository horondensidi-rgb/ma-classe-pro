import os

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model


class Command(BaseCommand):
    help = "Crée ou met à jour l'administrateur de production."

    def handle(self, *args, **options):
        User = get_user_model()

        username = os.environ.get("ADMIN_USERNAME")
        email = os.environ.get("ADMIN_EMAIL")
        password = os.environ.get("ADMIN_PASSWORD")

        if not username or not email or not password:
            self.stdout.write(
                self.style.WARNING(
                    "Variables ADMIN_USERNAME, ADMIN_EMAIL et ADMIN_PASSWORD "
                    "non configurées. Aucun administrateur créé ou modifié."
                )
            )
            return

        user, created = User.objects.get_or_create(
            username=username,
            defaults={"email": email},
        )

        user.email = email
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.set_password(password)
        user.save()

        self.stdout.write(
            f"VERIFICATION ADMIN : username={user.username}, "
            f"is_staff={user.is_staff}, "
            f"is_superuser={user.is_superuser}, "
            f"is_active={user.is_active}"
        )

        if created:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Superutilisateur '{username}' créé avec succès."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Administrateur '{username}' mis à jour avec succès."
                )
            )
