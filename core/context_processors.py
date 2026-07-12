import time

from django.conf import settings
from django.core.cache import cache
from django.utils.dateparse import parse_datetime

from core.models import Notification

NOTIFICATION_CACHE_TTL = 300


class _CachedNotification:
    """Lightweight stand-in for template rendering."""

    def __init__(self, link, message, created_at):
        self.link = link
        self.message = message
        self.created_at = (
            parse_datetime(created_at) if isinstance(created_at, str) else created_at
        )


def logged_user_processor(request):
    """Reuse the authenticated user already loaded by AuthenticationMiddleware."""
    if request.user.is_authenticated:
        return {'logged_user': request.user}
    return {'logged_user': None}


def _fetch_unread_notifications(user):
    return list(
        Notification.objects.filter(recipient_id=user.pk, read=False)
        .only('pk', 'message', 'created_at', 'read', 'link')
        .order_by('-created_at')[:10]
    )


def _notification_cache_key(user_pk):
    return f'unread_notifications_{user_pk}'


def notifications_processor(request):
    """Provide unread notifications for the header dropdown."""
    if not request.user.is_authenticated:
        return {'unread_notifications': []}
    if getattr(request, 'partial_nav', False):
        return {'unread_notifications': []}

    cache_key = _notification_cache_key(request.user.pk)
    cached_items = cache.get(cache_key)
    if cached_items is not None:
        return {
            'unread_notifications': [
                _CachedNotification(item['link'], item['message'], item['created_at'])
                for item in cached_items
            ],
        }

    notifications = _fetch_unread_notifications(request.user)
    cache.set(
        cache_key,
        [
            {
                'link': n.link or '',
                'message': n.message,
                'created_at': n.created_at.isoformat(),
            }
            for n in notifications
        ],
        NOTIFICATION_CACHE_TTL,
    )
    return {'unread_notifications': notifications}


def invalidate_notification_cache(user_pk):
    cache.delete(_notification_cache_key(user_pk))


def static_version_processor(request):
    return {
        'STATIC_VERSION': getattr(settings, 'STATIC_VERSION', '1'),
        'IS_DEV': settings.DEBUG,
    }
