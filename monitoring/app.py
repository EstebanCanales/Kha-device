"""Server-rendered shell for the operator dashboard; the data comes from the /api/v1/ routes."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie


@login_required
@ensure_csrf_cookie
def app(request):
    return render(request, "monitoring/app.html")
