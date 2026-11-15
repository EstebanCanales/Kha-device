"""Server-rendered shell for the operator dashboard; the data comes from the /api/v1/ routes."""

from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie


@ensure_csrf_cookie
def app(request):
    # An account is required, except in the public demonstration, where visitors read simulated data only.
    if not request.user.is_authenticated and not settings.PUBLIC_DEMO:
        return redirect_to_login(request.get_full_path())
    return render(request, "monitoring/app.html", {"public_demo": settings.PUBLIC_DEMO, "landing_url": settings.LANDING_URL})
