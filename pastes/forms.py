from django import forms


class PasteCreateForm(forms.Form):
    content = forms.CharField(
        widget=forms.Textarea(
            attrs={"rows": 16, "placeholder": "Paste your text here...", "autofocus": True}
        )
    )
    password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={"placeholder": "Optional"}),
        help_text="Leave blank for no password.",
    )
    burn_after_read = forms.BooleanField(
        required=False, label="Burn after read (delete once someone views it)"
    )
    private = forms.BooleanField(
        required=False, label="Private (only visible to me)"
    )


class UnlockForm(forms.Form):
    password = forms.CharField(widget=forms.PasswordInput(attrs={"autofocus": True}))
