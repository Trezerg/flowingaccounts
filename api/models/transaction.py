from django.db import models
from django_ledger.models.journal_entry import JournalEntryModel

class TransactionModel(models.Model):
    # ...existing code...
    journal_entry = models.ForeignKey(JournalEntryModel, on_delete=models.CASCADE, related_name="line_items")
    # ...existing code...