from django.db import models
from django.contrib.auth import get_user_model
import uuid
from apps.User.models import CustomUser

class AnalysisRequest(models.Model):
    STATUS_CHOICES = (
        ('progress', 'In Progress'),
        ('queue', 'Queued'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    )

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    file = models.FileField(upload_to='analysis_files/')
    uuid = models.UUIDField(default=uuid.uuid4, editable=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='queue')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, blank=True, null=True)
    result = models.FileField(upload_to='analysis_results/', blank=True, null=True)
    email_sent = models.BooleanField(default=False, blank=True, null=True)

    def __str__(self):
        return self.name