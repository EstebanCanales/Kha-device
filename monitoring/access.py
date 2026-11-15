"""Who may read which monitoring session.

One place for the rule, so the session API, the combined report and any future reader agree.
Writing is a separate matter: configuration and session changes stay staff-only everywhere.
"""

from django.conf import settings

from .models import MonitoringSession


def readable_sessions(user, queryset=None):
    """Sessions this account may read.

    - Staff read everything.
    - With ``OPEN_READ_ACCESS`` on, every signed-in account reads everything. It is meant for a demonstration
      with simulated data; it must stay off once a session holds a real participant's readings.
    - Otherwise an account reads only the sessions it was explicitly authorized for.
    """
    queryset = MonitoringSession.objects.all() if queryset is None else queryset
    if not user or not user.is_authenticated or not user.is_active:
        return queryset.none()
    if user.is_staff or settings.OPEN_READ_ACCESS:
        return queryset
    return queryset.filter(authorized_users=user)
