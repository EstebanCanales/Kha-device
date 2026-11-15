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
    - With ``PUBLIC_DEMO`` on, a visitor without an account is a reader too, of simulated data only
      (see ``may_read_source``).
    """
    queryset = MonitoringSession.objects.all() if queryset is None else queryset
    if not user or not user.is_authenticated:
        # Visitors without an account read nothing, unless the public demonstration is on.
        return queryset if settings.PUBLIC_DEMO else queryset.none()
    if not user.is_active:
        return queryset.none()
    if user.is_staff or settings.OPEN_READ_ACCESS:
        return queryset
    return queryset.filter(authorized_users=user)


def may_read_source(user, source: str) -> bool:
    """Whether this reader may ask for data of that provenance.

    Signed-in readers choose freely. A visitor without an account, admitted by ``PUBLIC_DEMO``, is limited to
    simulated data: readings from real instruments are never public.
    """
    if user and user.is_authenticated:
        return True
    return settings.PUBLIC_DEMO and source == "simulated"
