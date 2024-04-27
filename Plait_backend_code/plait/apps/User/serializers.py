from rest_framework import serializers
from .models import CustomUser


class UserSignupSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    class Meta:
        model = CustomUser
        fields = ['username', 'first_name', 'last_name', 'email', 'password', 'confirm_password']

    def validate(self, data):
        if data.get('password') != data.get('confirm_password'):
            raise serializers.ValidationError("Passwords do not match")
        return data

    def create(self, validated_data):
        validated_data.pop('confirm_password')
        user = CustomUser.objects.create_user(**validated_data)
        return user


class UserSerializer(serializers.ModelSerializer):
    date_joined = serializers.DateTimeField(format="%Y-%m-%d %H:%M")  # Format datetime as desired
    last_login = serializers.DateTimeField(format="%Y-%m-%d %H:%M")  # Format datetime as desired

    class Meta:
        model = CustomUser
        fields = ['id', 'is_superuser', 'first_name', 'last_name', 'is_staff', 'is_active',
                  'date_joined', 'username', 'email', 'verified', 'last_login', 'is_allowed']
