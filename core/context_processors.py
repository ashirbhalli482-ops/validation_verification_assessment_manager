from django.conf import settings

from core.models import CustomUser, Notification

def logged_user_processor(request):
    """
    Context processor to provide logged_user to all templates
    """
    if request.user.is_authenticated:
        try:
            # Use select_related to optimize database queries
            logged_user = CustomUser.objects.select_related('under_supervision').get(id=request.user.id)
            return {'logged_user': logged_user}
        except CustomUser.DoesNotExist:
            return {'logged_user': None}
    return {'logged_user': None}


def notifications_processor(request):
    """
    Context processor to provide unread notifications to all templates
    """
    if request.user.is_authenticated:
        unread_notifications = Notification.objects.filter(recipient=request.user, read=False)[:10]
        return {'unread_notifications': unread_notifications}
    return {'unread_notifications': []}


def static_version_processor(request):
    return {'STATIC_VERSION': getattr(settings, 'STATIC_VERSION', '1')} 