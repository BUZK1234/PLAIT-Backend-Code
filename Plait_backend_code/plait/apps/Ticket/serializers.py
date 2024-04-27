from rest_framework import serializers
from .models import AnalysisRequest

class AnalysisRequestSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    created_at = serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S', read_only=True)
    updated_at = serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S', read_only=True)
    status = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = AnalysisRequest
        fields = ['id', 'name', 'description', 'file', 'uuid', 'status', 'created_at', 'updated_at', 'user_email', 'result']