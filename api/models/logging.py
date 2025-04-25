from django.db import models
from django.contrib.auth.models import User
from django_ledger.models.journal_entry import JournalEntryModel

class JournalActivityLogModel(models.Model):
    ACTION_CHOICES = [
        ('posted', 'Posted'),
        ('unposted', 'Unposted'),
        ('locked', 'Locked'),
        ('unlocked', 'Unlocked'),
        ('created', 'Created'),
        ('updated', 'Updated'),
    ]

    journal_entry = models.ForeignKey(JournalEntryModel, on_delete=models.CASCADE, related_name='activity_logs')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    performed_at = models.DateTimeField(auto_now_add=True)
    note = models.TextField(blank=True, null=True)
    snapshot = models.JSONField(blank=True, null=True)

    def __str__(self):
        return f"{self.journal_entry} - {self.action} by {self.performed_by} at {self.performed_at}" 