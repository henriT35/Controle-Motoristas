import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()
from django.contrib.auth import get_user_model

username = os.getenv("DJANGO_ADMIN_USERNAME", "admin").strip() or "admin"
password = os.getenv("DJANGO_ADMIN_PASSWORD", "").strip()
email = os.getenv("DJANGO_ADMIN_EMAIL", "admin@localhost").strip()
User = get_user_model()
user, created = User.objects.get_or_create(username=username, defaults={"email": email, "is_staff": True, "is_superuser": True})
changed = False
if not user.is_staff:
    user.is_staff = True; changed = True
if not user.is_superuser:
    user.is_superuser = True; changed = True
if email and user.email != email:
    user.email = email; changed = True
if password and (created or os.getenv("DJANGO_ADMIN_FORCE_PASSWORD", "0") == "1"):
    user.set_password(password); changed = True
if changed:
    user.save()
print(f"Admin {'criado' if created else 'verificado'}: {username}")
