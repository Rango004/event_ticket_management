# tickets/migrations/0002_fix_missing_profiles.py
from django.db import migrations
from django.contrib.auth.models import User
from tickets.models import Profile

def create_missing_profiles(apps, schema_editor):
    for user in User.objects.all():
        Profile.objects.get_or_create(
            user=user,
            defaults={'role': 'staff' if user.is_staff else 'customer'}
        )

class Migration(migrations.Migration):
    dependencies = [
        ('tickets', '0001_initial'),  # Replace with your actual last migration
    ]

    operations = [
        migrations.RunPython(create_missing_profiles),
    ]