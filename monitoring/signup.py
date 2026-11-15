"""Self-service account creation for the operator dashboard.

Accounts are human users only (device credentials are a separate mechanism). A new account can read nothing:
access is granted per session by an administrator, except for the optional demo session named in
SIGNUP_DEMO_SESSION, which exists so a prototype evaluator can see data right away.
"""

from django.conf import settings
from django.contrib.auth import get_user_model, login
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.views import LoginView
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_protect

from .models import MonitoringSession

# Attempts per client address and window; the limit is deliberately small and local to the process cache.
SIGNUP_LIMIT = 10
SIGNUP_WINDOW_SECONDS = 3600


class SignUpForm(UserCreationForm):
    class Meta:
        model = get_user_model()
        fields = ("username", "email")

    def clean_email(self):
        email = self.cleaned_data.get("email", "").strip()
        if email and get_user_model().objects.filter(email__iexact=email).exists():
            raise ValidationError("Ya existe una cuenta con ese correo.")
        return email


def _client_key(request):
    # REMOTE_ADDR only: X-Forwarded-For is client-controlled unless a trusted proxy is configured.
    return f"signup:{request.META.get('REMOTE_ADDR', 'unknown')}"


def _grant_demo_access(user):
    identifier = settings.SIGNUP_DEMO_SESSION
    if not identifier:
        return
    for session in MonitoringSession.objects.filter(identifier=identifier):
        session.authorized_users.add(user)


@csrf_protect
def signup(request):
    if not settings.ALLOW_SIGNUP:
        raise Http404
    if request.user.is_authenticated:
        return redirect("app")
    form = SignUpForm(request.POST or None)
    limited = False
    if request.method == "POST":
        key = _client_key(request)
        count = cache.get(key, 0)
        if count >= SIGNUP_LIMIT:
            limited = True
        else:
            cache.set(key, count + 1, timeout=SIGNUP_WINDOW_SECONDS)
            if form.is_valid():
                user = form.save()
                _grant_demo_access(user)
                login(request, user)
                return redirect("app")
    response = render(request, "registration/signup.html", {"form": form, "limited": limited})
    if limited:
        response.status_code = 429
    return response


class AppLoginView(LoginView):
    """Login page that offers account creation only while sign-up is enabled."""

    def get_context_data(self, **kwargs):
        return super().get_context_data(allow_signup=settings.ALLOW_SIGNUP, **kwargs)
