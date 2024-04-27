# urls.py
from django.urls import path
from .views import UserViewSet, UserListView

urlpatterns = [
    path('signup', UserViewSet.as_view({"post": "sign_up"}), name='user_signup'),
    path('verify-email', UserViewSet.as_view({"post": "verify_email"}), name='verify_email'),
    path('login', UserViewSet.as_view({"post": "login"}), name='login'),
    path('logout', UserListView.as_view({"post": "logout"}), name='logout'),
    path('user-list', UserListView.as_view({"get": "get_user_list"}), name='get_user_list'),
    path('delete-user', UserListView.as_view({"delete": "delete_user"}), name='delete_user'),
    path('allow-user', UserListView.as_view({"patch": "change_user_allowed_status"}), name='change_user_allowed_status'),
    path('update-user', UserListView.as_view({"patch": "update_user"}), name='update_user'),
    path('forgot-password', UserViewSet.as_view({'post': 'forgot_password'}), name='forgot-password'),
    path('update-password', UserListView.as_view({'post': 'update_password'}), name='update_password'),
    path('reset-password', UserViewSet.as_view({'post': 'reset_password'}),
         name='reset-password'),
    path('user-information', UserListView.as_view({"get": "get_user_information"}), name='get_user_information'),
]