import random

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.db import models
from django.urls import reverse

from .wordlist import WORDS


def generate_unique_slug():
    while True:
        words = random.sample(WORDS, 3)
        suffix = f"{random.randint(0, 999):03d}"
        slug = "-".join(words) + f"-{suffix}"
        if not Paste.objects.filter(slug=slug).exists():
            return slug


class Paste(models.Model):
    slug = models.SlugField(max_length=80, unique=True, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="pastes"
    )
    content = models.TextField()
    password_hash = models.CharField(max_length=128, blank=True)
    burn_after_read = models.BooleanField(default=False)
    private = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.slug

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = generate_unique_slug()
        super().save(*args, **kwargs)

    def set_password(self, raw_password):
        self.password_hash = make_password(raw_password)

    def check_password(self, raw_password):
        return check_password(raw_password, self.password_hash)

    @property
    def has_password(self):
        return bool(self.password_hash)

    def get_absolute_url(self):
        return reverse("pastes:detail", args=[self.slug])
