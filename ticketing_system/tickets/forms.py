from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.utils import timezone
from .models import Profile, Announcement

class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)
    phone = forms.CharField(max_length=20, required=False)

    class Meta:
        model = User
        fields = ["username", "email", "password1", "password2"]

from django import forms
from django.core.validators import RegexValidator

class SecurePurchaseForm(forms.Form):
    #email = forms.EmailField(required=True)
    #phone = forms.CharField(required=True, validators=[
     #   RegexValidator(r'^\+?1?\d{9,15}$', 'Enter a valid phone number')
    #])
    #pin = forms.CharField(required=False, max_length=6, min_length=6)
    #otp = forms.CharField(required=False, max_length=6, min_length=6)
    pass


class AnnouncementForm(forms.ModelForm):
    class Meta:
        model = Announcement
        fields = ['title', 'content', 'priority', 'is_active', 'valid_until']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
            'priority': forms.Select(attrs={'class': 'form-select'}),
            'valid_until': forms.DateTimeInput(
                attrs={
                    'type': 'datetime-local',
                    'class': 'form-control',
                    'min': timezone.now().strftime('%Y-%m-%dT%H:%M')
                },
                format='%Y-%m-%dT%H:%M'
            ),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set initial value for the datetime-local field
        if self.instance and self.instance.valid_until:
            self.initial['valid_until'] = self.instance.valid_until.strftime('%Y-%m-%dT%H:%M')