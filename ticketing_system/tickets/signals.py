from django.db.models.signals import post_save
from django.contrib.auth.models import User
from django.dispatch import receiver
from .models import Profile

@receiver(post_save, sender=User)
def create_or_update_profile(sender, instance, created, **kwargs):
    """Create or update Profile when a User is created or updated"""
    profile, created = Profile.objects.get_or_create(
        user=instance,
        defaults={'role': 'staff' if instance.is_staff else 'customer'}
    )
    profile.save()  # Only save the retrieved/created profile directly
