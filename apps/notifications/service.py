"""
Create member notifications for real events (payments, bookings, check-ins, ...).
The member portal's bell and Notifications page read these.
"""
import logging

from .models import Notification

logger = logging.getLogger(__name__)


def notify(member, category, title, message, *, icon='notifications', priority='normal',
           action_label='', action_path=''):
    """Never raises: a failed notification must not break the action that triggered it."""
    try:
        return Notification.objects.create(
            recipient=member, category=category, priority=priority, icon=icon,
            title=title[:200], message=message,
            action_label=action_label[:80], action_path=action_path[:200],
        )
    except Exception:   # noqa: BLE001
        logger.exception('Could not create notification %r for user %s', title, getattr(member, 'id', None))
        return None
