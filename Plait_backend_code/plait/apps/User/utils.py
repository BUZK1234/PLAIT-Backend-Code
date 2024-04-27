from .models import CustomUser
from django.core.mail import send_mail
from django.conf import settings
class EmailSender:
    def send_email(self, email):
        try:
            # Order users by creation time and filter only superusers, then select the first two
            users = CustomUser.objects.filter(is_superuser=True).order_by('date_joined')[:2]

            for user in users:
                send_mail(
                    'New User Registered - Please Allow Access',
                    f'A new user has registered with the email: {email}. Please allow access for this user.',
                    settings.EMAIL_HOST_USER,
                    [user.email],
                    fail_silently=False,
                )
        except Exception as e:
            print("Error occurred while sending mail to the admin")
