from datetime import timezone
from django.db import models
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.core.files import File
from django.db.models.signals import post_save
from django.dispatch import receiver
import qrcode
import uuid
from io import BytesIO
from django.contrib.auth.hashers import make_password, check_password
from django.core.validators import MinValueValidator
from django.db import transaction
from django.core.exceptions import ValidationError


class Event(models.Model):
    name = models.CharField(max_length=200)
    date = models.DateTimeField()
    location = models.CharField(max_length=200)
    price = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(0.01)]
    )
    ticket_count = models.PositiveIntegerField(default=10)
    max_purchase_per_user = models.PositiveIntegerField(default=5)

    def __str__(self):
        return self.name

    def available_tickets(self):
        return self.ticket_count - self.tickets.filter(status='PURCHASED').count()


class Ticket(models.Model):
    STATUS_CHOICES = [
        ('AVAILABLE', 'Available'),
        ('PURCHASED', 'Purchased'),
        ('USED', 'Used'),
        ('EXPIRED', 'Expired')
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='tickets')
    qr_code = models.ImageField(upload_to='qr_codes/', blank=True)
    unique_code = models.CharField(max_length=17, unique=True, db_index=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='AVAILABLE')
    purchased_at = models.DateTimeField(null=True, blank=True)  # Set when ticket is actually purchased
    last_modified = models.DateTimeField(auto_now=True)

    def generate_unique_code(self):
        while True:
            code = uuid.uuid4().hex[:17].upper()
            if not Ticket.objects.filter(unique_code=code).exists():
                return code

    def generate_qr_code(self):
        # Your QR generation logic
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(f"Ticket ID: {self.id}, Code: {self.unique_code}")
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        
        filename = f"ticket_{self.unique_code}.png"
        self.qr_code.save(filename, ContentFile(buffer.getvalue()), save=False)

    def clean(self):
        super().clean()
        # Add any model-specific validation rules here.
        # For example:
        # if self.status == 'PURCHASED' and not self.user:
        #     raise ValidationError('A purchased ticket must be assigned to a user.')
        # if self.status == 'PURCHASED' and not self.purchased_at:
        #     raise ValidationError('A purchased ticket must have a purchase date.')

    def save(self, *args, **kwargs):
        if not self.unique_code:  # Ensure unique_code is generated if not set
            self.unique_code = self.generate_unique_code()
        
        # Call full_clean before saving. This will call our Ticket.clean() method.
        # Exclude full_clean if only specific fields are being updated (e.g., by update_fields)
        if not kwargs.get('update_fields'):
            self.full_clean()
        
        # Determine if we need to generate and save QR code
        # This check should ideally be for new objects or when relevant fields change
        is_new_object = not self.pk

        super().save(*args, **kwargs)  # Save the model first

        if is_new_object and not self.qr_code.name:
            self.generate_qr_code()  # Generates and saves the QR image file to storage
                                     # This method calls self.qr_code.save(..., save=False)
            # Now, save the model again to persist the self.qr_code.name (path to image) in the database
            # Only update the qr_code field to avoid recursion and re-running all save logic
            super().save(update_fields=['qr_code'])
    def is_valid(self):
        return self.status == 'PURCHASED' and not self.is_expired()

    def is_expired(self):
        # Add expiration logic here
        return False


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone = models.CharField(max_length=20, blank=True)
    role = models.CharField(max_length=20, default='customer')
    credits = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(0.0)]
    )
    has_purchased_pin = models.BooleanField(default=False)
    pin = models.CharField(max_length=6, blank=True, null=True)
    otp_secret = models.CharField(max_length=32, blank=True)
    last_otp = models.CharField(max_length=6, blank=True)
    otp_expiry = models.DateTimeField(null=True, blank=True)

    def set_pin(self, raw_pin):
        self.pin = make_password(raw_pin)
    
    def check_pin(self, raw_pin):
        return check_password(raw_pin, self.pin)

    def deduct_credits(self, amount):
        with transaction.atomic():
            if self.credits >= amount:
                self.credits -= amount
                self.save()
                return True
            return False

    def add_credits(self, amount):
        with transaction.atomic():
            self.credits += amount
            self.save()

class Token(models.Model):
    code = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_by = models.ForeignKey(  # Add this field
        User, 
        on_delete=models.SET_NULL, 
        null=True,
        related_name='created_tokens'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expiry_date = models.DateTimeField()  # Ensure this exists
    used = models.BooleanField(default=False)
    used_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='used_tokens'
    )
    used_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Token {self.code} - ${self.amount}"

class ChatMessage(models.Model):
    LANGUAGE_CHOICES = [
        ('en', 'English'),
        ('am', 'Amharic'),
        ('kri', 'Krio'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    response = models.TextField(blank=True)
    language = models.CharField(
        max_length=10, 
        choices=LANGUAGE_CHOICES, 
        default='en',
        help_text='Language used in this message'
    )

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Chat Message'
        verbose_name_plural = 'Chat Messages'

    def mark_as_read(self):
        self.is_read = True
        self.save(update_fields=['is_read'])
        
    def __str__(self):
        return f"{self.user.username} - {self.timestamp.strftime('%Y-%m-%d %H:%M')} ({self.get_language_display()})"


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance, credits=0)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        instance.profile.save()

class Announcement(models.Model):
    PRIORITY_CHOICES = [
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
    ]
    
    title = models.CharField(max_length=200)
    content = models.TextField()
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='MEDIUM')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='announcements')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    valid_until = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class Transaction(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    timestamp = models.DateTimeField(auto_now_add=True)
    transaction_type = models.CharField(max_length=20, choices=[
        ('PURCHASE', 'Token Purchase'),
        ('REDEMPTION', 'Token Redemption'),
        ('TICKET_PURCHASE', 'Ticket Purchase')
    ])