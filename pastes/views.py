from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import PasteCreateForm, UnlockForm
from .models import Paste


@login_required
def create(request):
    if request.method == "POST":
        form = PasteCreateForm(request.POST)
        if form.is_valid():
            paste = Paste(
                owner=request.user,
                content=form.cleaned_data["content"],
                burn_after_read=form.cleaned_data["burn_after_read"],
                private=form.cleaned_data["private"],
            )
            password = form.cleaned_data["password"]
            if password:
                paste.set_password(password)
            paste.save()
            return redirect("pastes:created", slug=paste.slug)
    else:
        form = PasteCreateForm()
    return render(request, "pastes/create.html", {"form": form})


@login_required
def created(request, slug):
    paste = get_object_or_404(Paste, slug=slug, owner=request.user)
    paste_url = request.build_absolute_uri(paste.get_absolute_url())
    return render(request, "pastes/created.html", {"paste": paste, "paste_url": paste_url})


@login_required
def mine(request):
    pastes = request.user.pastes.all()
    return render(request, "pastes/mine.html", {"pastes": pastes})


def detail(request, slug):
    try:
        paste = Paste.objects.get(slug=slug)
    except Paste.DoesNotExist:
        return render(request, "404.html", status=404)

    is_owner = request.user.is_authenticated and request.user.id == paste.owner_id
    if paste.private and not is_owner:
        return render(request, "404.html", status=404)

    session_key = f"unlocked_paste_{paste.pk}"
    unlocked = not paste.has_password or request.session.get(session_key, False)

    form = None
    error = None
    if not unlocked:
        if request.method == "POST":
            form = UnlockForm(request.POST)
            if form.is_valid() and paste.check_password(form.cleaned_data["password"]):
                unlocked = True
                request.session[session_key] = True
            else:
                error = "Incorrect password."
        else:
            form = UnlockForm()

    if not unlocked:
        return render(request, "pastes/locked.html", {"form": form, "error": error})

    if paste.burn_after_read:
        confirmed = request.method == "POST" and request.POST.get("confirm_burn") == "1"
        if not confirmed:
            return render(request, "pastes/burn_confirm.html", {"paste": paste})
        content = paste.content
        paste.delete()
        request.session.pop(session_key, None)
        return render(
            request,
            "pastes/detail.html",
            {"paste": paste, "content": content, "is_owner": is_owner, "burned": True},
        )

    return render(
        request,
        "pastes/detail.html",
        {"paste": paste, "content": paste.content, "is_owner": is_owner, "burned": False},
    )


@login_required
@require_POST
def delete(request, slug):
    paste = get_object_or_404(Paste, slug=slug, owner=request.user)
    paste.delete()
    return redirect("pastes:mine")
