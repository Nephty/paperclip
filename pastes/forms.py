from django import forms

ANONYMOUS_CHAR_LIMIT = 1000
DEFAULT_CHAR_LIMIT = 10000


def char_limit_for(user):
    if not user.is_authenticated:
        return ANONYMOUS_CHAR_LIMIT
    profile = getattr(user, "profile", None)
    if profile and profile.unlimited:
        return None
    return DEFAULT_CHAR_LIMIT


def char_limit_message(user, char_limit):
    if char_limit is None:
        return "No character limit for your account."
    if not user.is_authenticated:
        return (
            f"Anonymous pastes are limited to {char_limit:,} characters. "
            "Request a personal account from an administrator to raise this limit."
        )
    return (
        f"Your account is limited to {char_limit:,} characters per paste. "
        "Contact an administrator to request unlimited access."
    )


class PasteCreateForm(forms.Form):
    content = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "rows": 16,
                "placeholder": "Paste your text here...",
                "autofocus": True,
                "class": "flex-1",
            }
        )
    )
    password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={"placeholder": "Optional"}),
        help_text="Leave blank for no password.",
    )
    burn_after_read = forms.BooleanField(
        required=False,
        label="Burn after read (delete once someone views it)",
        widget=forms.CheckboxInput(attrs={"class": "w-4 h-4 accent-[var(--accent)] cursor-pointer"}),
    )
    private = forms.BooleanField(
        required=False,
        label="Private (only visible to me)",
        widget=forms.CheckboxInput(attrs={"class": "w-4 h-4 accent-[var(--accent)] cursor-pointer"}),
    )

    def __init__(self, *args, char_limit=None, limit_message="", **kwargs):
        super().__init__(*args, **kwargs)
        self.char_limit = char_limit
        self.limit_message = limit_message
        if char_limit:
            self.fields["content"].widget.attrs["maxlength"] = char_limit

    def clean_content(self):
        content = self.cleaned_data["content"]
        if self.char_limit and len(content) > self.char_limit:
            raise forms.ValidationError(self.limit_message)
        return content


class UnlockForm(forms.Form):
    password = forms.CharField(widget=forms.PasswordInput(attrs={"autofocus": True}))
