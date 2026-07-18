import os

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.hashers import check_password
from django.core.exceptions import ValidationError


class SignupForm(UserCreationForm):
    # Gate value is produced out-of-band with:
    #   python manage.py shell -c "from django.contrib.auth.hashers import make_password; print(make_password('the-actual-secret'))"
    # The hash (never the plaintext) is what SIGNUP_GATE_PASSWORD_HASH holds.
    admin_password = forms.CharField(widget=forms.PasswordInput, label="Admin password")

    class Meta(UserCreationForm.Meta):
        fields = ("username",)

    def clean_admin_password(self):
        value = self.cleaned_data["admin_password"]
        stored_hash = os.environ.get("SIGNUP_GATE_PASSWORD_HASH", "")
        if not stored_hash or not check_password(value, stored_hash):
            raise ValidationError("Incorrect admin password.")
        return value
