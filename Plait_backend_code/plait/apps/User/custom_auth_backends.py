from django.contrib.auth.backends import BaseBackend
from .models import CustomUser


class EmailAuthBackend(BaseBackend):
    def authenticate(self, request, email=None, username=None, password=None):
        if email:
            # Authenticate using email
            user = CustomUser.objects.filter(email=email).first()
        elif username:
            # Authenticate using username
            user = CustomUser.objects.filter(username=username).first()
        else:
            return None

        if user and user.check_password(password):
            return user
        return None

    def get_user(self, user_id):
        try:
            return CustomUser.objects.get(pk=user_id)
        except CustomUser.DoesNotExist:
            return None