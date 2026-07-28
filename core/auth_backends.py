from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.db.models import Q

from .access import enforce_active_company_for_login

User = get_user_model()

class EmailBackend(ModelBackend):
    """
    Custom authentication backend that allows users to authenticate with email
    """
    
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            username = kwargs.get('email')
        if username is None or password is None:
            return None
        
        user = User.objects.filter(
            Q(email=username) | Q(username=username)
        ).first()
        if user is None:
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            if not enforce_active_company_for_login(user):
                return None
            return user
        
        return None
    
    def get_user(self, user_id):
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
        if not self.user_can_authenticate(user):
            return None
        if not enforce_active_company_for_login(user):
            return None
        return user
