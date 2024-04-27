from rest_framework.response import Response
from rest_framework.views import status
from django.core.mail import send_mail
from django.conf import settings
from django.utils.crypto import get_random_string
from .models import CustomUser
from .serializers import UserSignupSerializer, UserSerializer
from rest_framework import viewsets
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from .custom_auth_backends import EmailAuthBackend
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from django.urls import reverse
import random
import string
from django.contrib.auth.hashers import check_password
from .utils import EmailSender
import threading
from rest_framework.pagination import PageNumberPagination


class UserViewSet(viewsets.ViewSet):

    def sign_up(self, request):
        try:
            serializer = UserSignupSerializer(data=request.data)
        # if serializer.is_valid():
            email = request.data['email']
            existing_user = CustomUser.objects.filter(email=email).first()

            if existing_user and not existing_user.verified:
                # Generate new verification code
                verification_code = get_random_string(length=6)

                # Save the new verification code to the existing user object
                existing_user.verification_code = verification_code
                existing_user.save()

                # Send verification email with new code
                send_mail(
                    'New Verification Code',
                    f'Your new verification code is: {verification_code}',
                    settings.EMAIL_HOST_USER,
                    [existing_user.email],
                    fail_silently=False,
                )

                custom_response = {
                    "statusMessage": "A new verification code has been sent to your email.",
                    "errorStatus": False,
                    "data": [],
                    "statusCode": status.HTTP_200_OK,
                }
                return Response(custom_response)
            else:
                if serializer.is_valid():
                    user = serializer.save()

                    # Generate verification code
                    verification_code = get_random_string(length=6)

                    # Save the verification code to user object
                    user.verification_code = verification_code
                    user.save()

                    # Send verification email
                    send_mail(
                        'Verification Code',
                        f'Your verification code is: {verification_code}',
                        settings.EMAIL_HOST_USER,
                        [user.email],
                        fail_silently=False,
                    )

                    custom_response = {
                        "statusMessage": "User created. Check your email for verification code.",
                        "errorStatus": False,
                        "data": [],
                        "statusCode": status.HTTP_201_CREATED,
                    }
                    return Response(custom_response)
            error_message = ""

            if 'username' in serializer.errors:
                error_message += "Username already exists. "
            if 'email' in serializer.errors:
                error_message += "Email already exists. "

            # Constructing the custom response
            if error_message:
                custom_response = {
                    "statusMessage": error_message.strip(),
                    "errorStatus": True,
                    "data": [],
                    "statusCode": status.HTTP_400_BAD_REQUEST,
                }
            else:
                custom_response = {
                    "statusMessage": "Unknown registration error.",
                    "errorStatus": True,
                    "data": [],
                    "statusCode": status.HTTP_400_BAD_REQUEST,
                }

            return Response(custom_response)

        except Exception as e:
            custom_response = {
                "statusMessage": str(e),
                "errorStatus": True,
                "data": [],
                "statusCode": status.HTTP_500_INTERNAL_SERVER_ERROR,
            }
            return Response(custom_response)

    def verify_email(self, request):
        try:
            email = request.data.get('email')
            verification_code = request.data.get('verification_code')

            user = CustomUser.objects.get(email=email)

            if user.verified:
                custom_response = {
                    "statusMessage": "Email already verified",
                    "errorStatus": True,
                    "data": [],
                    "statusCode": status.HTTP_400_BAD_REQUEST,
                }
                return Response(custom_response)

            if user.verification_code != verification_code:
                custom_response = {
                    "statusMessage": "Invalid verification code",
                    "errorStatus": True,
                    "data": [],
                    "statusCode": status.HTTP_400_BAD_REQUEST,
                }
                return Response(custom_response)

            # Mark the user as verified
            user.verified = True
            user.save()
            email_thread = threading.Thread(target=EmailSender().send_email, args=(email,))
            email_thread.start()
            custom_response = {
                "statusMessage": "Email verified successfully",
                "errorStatus": False,
                "data": [],
                "statusCode": status.HTTP_200_OK,
            }
            return Response(custom_response)
        except CustomUser.DoesNotExist:
            custom_response = {
                "statusMessage": "User with this email does not exist",
                "errorStatus": True,
                "data": [],
                "statusCode": status.HTTP_404_NOT_FOUND,
            }
            return Response(custom_response)
        except Exception as e:
            custom_response = {
                "statusMessage": str(e),
                "errorStatus": True,
                "data": [],
                "statusCode": status.HTTP_500_INTERNAL_SERVER_ERROR,
            }
            return Response(custom_response)

    def login(self, request):
        try:
            email_or_username = request.data.get('email')
            password = request.data.get('password')

            # Check if email/username and password are provided
            if not email_or_username or not password:
                custom_response = {
                    "statusMessage": "Both email/username and password are required",
                    "errorStatus": True,
                    "data": [],
                    "statusCode": status.HTTP_400_BAD_REQUEST,
                }
                return Response(custom_response)

            # Authenticate user with custom authentication backend
            if '@' in email_or_username:
                user = EmailAuthBackend().authenticate(request, email=email_or_username, password=password)
            else:
                user = EmailAuthBackend().authenticate(request, username=email_or_username, password=password)

            # Check if user is authenticated
            if user:
                # Check if user is a superuser
                if user.is_superuser:
                    # Generate JWT token for superuser
                    refresh = RefreshToken.for_user(user)
                    data = {
                        'refresh': str(refresh),
                        'access': str(refresh.access_token),
                        'is_superuser': user.is_superuser,
                    }
                    custom_response = {
                        "statusMessage": "Successful",
                        "errorStatus": False,
                        "data": data,
                        "statusCode": status.HTTP_200_OK,
                    }
                    return Response(custom_response)
                else:
                    # Check if email is verified for regular users
                    if user.verified:
                        if not user.is_allowed is True:
                            raise ValueError("Access denied. User is not allowed. Please contact the administrator.")

                        # Generate JWT token for regular user
                        refresh = RefreshToken.for_user(user)
                        data = {
                            'refresh': str(refresh),
                            'access': str(refresh.access_token),
                            'is_superuser': user.is_superuser,
                        }
                        user.last_login = timezone.now()
                        user.save()
                        custom_response = {
                            "statusMessage": "Successful",
                            "errorStatus": False,
                            "data": data,
                            "statusCode": status.HTTP_200_OK,
                        }
                        return Response(custom_response)
                    else:
                        custom_response = {
                            "statusMessage": "Email not verified. Please verify your email first.",
                            "errorStatus": True,
                            "data": [],
                            "statusCode": status.HTTP_400_BAD_REQUEST,
                        }
                        return Response(custom_response)
            else:
                custom_response = {
                    "statusMessage": "Invalid credentials",
                    "errorStatus": True,
                    "data": [],
                    "statusCode": status.HTTP_401_UNAUTHORIZED,
                }
                return Response(custom_response)
        except Exception as e:
            custom_response = {
                "statusMessage": str(e),
                "errorStatus": True,
                "data": [],
                "statusCode": status.HTTP_500_INTERNAL_SERVER_ERROR,
            }
            return Response(custom_response)

    def forgot_password(self, request):
        try:
            email = request.data.get('email')
            user = CustomUser.objects.get(email=email)

            if user.verified and user.is_allowed:
                # Generate a random password
                new_password = ''.join(random.choices(string.ascii_letters + string.digits, k=10))

                # Reset user's password
                user.set_password(new_password)
                user.save()

                # Send new password via email
                send_mail(
                    'Your New Password',
                    f'Your new password is: {new_password}',
                    settings.EMAIL_HOST_USER,
                    [user.email],
                    fail_silently=False,
                )

                custom_response = {
                    "statusMessage": "New password sent via email",
                    "errorStatus": False,
                    "data": [],
                    "statusCode": 200,
                }
            else:
                custom_response = {
                    "statusMessage": "Cannot reset password. Your account is not verified or approved by the admin.",
                    "errorStatus": True,
                    "data": [],
                    "statusCode": 403,  # Forbidden
                }
            return Response(custom_response)

        except CustomUser.DoesNotExist:
            custom_response = {
                "statusMessage": "User not found",
                "errorStatus": True,
                "data": [],
                "statusCode": 404,
            }
            return Response(custom_response)

        except Exception as e:
            custom_response = {
                "statusMessage": str(e),
                "errorStatus": True,
                "data": [],
                "statusCode": 500,
            }
            return Response(custom_response)

class UserListView(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def logout(self, request):
        try:
            refresh_token = request.data.get('refresh_token')
            token = RefreshToken(refresh_token)
            token.blacklist()
            custom_response = {
                "statusMessage": "User logged out successfully.",
                "errorStatus": False,
                "data": [],
                "statusCode": status.HTTP_200_OK,
            }
            return Response(custom_response)
        except Exception as e:
            custom_response = {
                "statusMessage": str(e),
                "errorStatus": True,
                "data": [],
                "statusCode": status.HTTP_400_BAD_REQUEST,
            }
            return Response(custom_response)

    def get_user_list(self, request):
        try:
            # Check if the user is a superuser
            if not request.user.is_superuser:
                custom_response = {
                    'statusMessage': 'Only superusers are allowed to access this endpoint.',
                    'errorStatus': True,
                    'data': [],
                    'statusCode': status.HTTP_403_FORBIDDEN
                }
                return Response(custom_response)

            # Retrieve all user objects excluding superuser
            users = CustomUser.objects.exclude(id=request.user.id).order_by('date_joined')
            paginator = PageNumberPagination()
            paginator.page_size = 10  # Adjust the page size as needed

            result_page = paginator.paginate_queryset(users, request)

            # Serialize the user objects
            serializer = UserSerializer(result_page, many=True)

            custom_response = {
                'statusMessage': 'Success',
                'errorStatus': False,
                'data': serializer.data,
                "next_page": paginator.get_next_link(),
                "previous_page": paginator.get_previous_link(),
                "total_pages": paginator.page.paginator.num_pages,
                "current_page": paginator.page.number,
                'statusCode': status.HTTP_200_OK
            }
            return Response(custom_response)

        except Exception as e:
            custom_response = {
                'error': str(e),
                'error_status': True,
                'data': [],
                'statusCode': status.HTTP_500_INTERNAL_SERVER_ERROR
            }
            return Response(custom_response)

    def update_password(self, request):
        try:
            user = request.user
            old_password = request.data.get('old_password')
            new_password = request.data.get('new_password')

            if not user.check_password(old_password):
                custom_response = {
                    "statusMessage": "Old password is incorrect.",
                    "errorStatus": True,
                    "data": [],
                    "statusCode": status.HTTP_400_BAD_REQUEST,
                }
                return Response(custom_response)

            user.set_password(new_password)
            user.save()

            custom_response = {
                "statusMessage": "User password updated successfully.",
                "errorStatus": False,
                "data": [],
                "statusCode": status.HTTP_200_OK,
            }
            return Response(custom_response)

        except Exception as e:
            custom_response = {
                "statusMessage": str(e),
                "errorStatus": True,
                "data": [],
                "statusCode": status.HTTP_500_INTERNAL_SERVER_ERROR,
            }
            return Response(custom_response)

    def delete_user(self, request):
        try:
            if not request.user.is_superuser:
                custom_response = {
                    'statusMessage': 'Only superusers are allowed to access this endpoint.',
                    'errorStatus': True,
                    'data': [],
                    'statusCode': status.HTTP_403_FORBIDDEN
                }
                return Response(custom_response)

            user_id = request.query_params.get('user_id')

            user = CustomUser.objects.get(id=user_id)
            user.delete()

            custom_response = {
                "statusMessage": "User deleted successfully.",
                "errorStatus": False,
                "data": [],
                "statusCode": status.HTTP_200_OK,
            }
            return Response(custom_response)
        except CustomUser.DoesNotExist:
            custom_response = {
                "statusMessage": "User does not exist.",
                "errorStatus": True,
                "data": [],
                "statusCode": status.HTTP_404_NOT_FOUND,
            }
            return Response(custom_response)
        except Exception as e:
            custom_response = {
                "statusMessage": str(e),
                "errorStatus": True,
                "data": [],
                "statusCode": status.HTTP_500_INTERNAL_SERVER_ERROR,
            }
            return Response(custom_response)

    def change_user_allowed_status(self, request):
        try:
            user_id = request.data.get("user_id")
            user_status = request.data.get("status")
            user = CustomUser.objects.get(id=user_id)
        except CustomUser.DoesNotExist:
            custom_response = {
                "error": "User does not exist",
                "errorStatus": True,
                "data": [],
                "statusCode": status.HTTP_404_NOT_FOUND,
            }
            return Response(custom_response)

        if request.user.is_superuser:
            user.is_allowed = user_status
            user.save()
            custom_response = {
                "message": "User's allowed status has been changed successfully.",
                "errorStatus": False,
                "data": [],
                "statusCode": status.HTTP_200_OK,
            }
            return Response(custom_response)
        else:
            custom_response = {
                "error": "You do not have permission to perform this action.",
                "errorStatus": True,
                "data": [],
                "statusCode": status.HTTP_403_FORBIDDEN,
            }
            return Response(custom_response)

    def update_user(self, request):

        if request.user.is_superuser:
            try:
                user_id = request.data.get("id")
                first_name = request.data.get("first_name")
                last_name = request.data.get("last_name")
                is_superuser = request.data.get("is_superuser")
                user = CustomUser.objects.get(id=user_id)
            except CustomUser.DoesNotExist:
                custom_response = {
                    "error": "User does not exist",
                    "errorStatus": True,
                    "data": [],
                    "statusCode": status.HTTP_404_NOT_FOUND,
                }
                return Response(custom_response)

            user.first_name = first_name
            user.last_name = last_name
            user.is_superuser = is_superuser
            user.save()
            custom_response = {
                "message": "User's name updated successfully.",
                "errorStatus": False,
                "data": [],
                "statusCode": status.HTTP_200_OK,
            }
            return Response(custom_response)
        else:
            custom_response = {
                "error": "You do not have permission to perform this action.",
                "errorStatus": True,
                "data": [],
                "statusCode": status.HTTP_403_FORBIDDEN,
            }
            return Response(custom_response)

    def get_user_information(self, request):
        try:
            # Get the user identifier from the request
            user = request.user

            # Retrieve the specific user object
            user = CustomUser.objects.get(id=user.id)

            # Serialize the user object
            serializer = UserSerializer(user)

            custom_response = {
                'statusMessage': 'Success',
                'errorStatus': False,
                'data': serializer.data,
                'statusCode': status.HTTP_200_OK
            }
            return Response(custom_response)

        except CustomUser.DoesNotExist:
            custom_response = {
                'statusMessage': 'User not found',
                'errorStatus': True,
                'data': [],
                'statusCode': status.HTTP_404_NOT_FOUND
            }
            return Response(custom_response)

        except Exception as e:
            custom_response = {
                'error': str(e),
                'error_status': True,
                'data': [],
                'statusCode': status.HTTP_500_INTERNAL_SERVER_ERROR
            }
            return Response(custom_response)

