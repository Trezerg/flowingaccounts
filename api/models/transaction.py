from django.db import models
from django_ledger.models.journal_entry import JournalEntryModel
from django_ledger.models import AccountModel
from django.conf import settings
from django.core.exceptions import ValidationError

class TransactionModel(models.Model):
    journal_entry = models.ForeignKey(
        JournalEntryModel,
        on_delete=models.CASCADE,
        related_name="line_items",
        help_text="The journal entry this transaction belongs to."
    )
    account = models.ForeignKey(
        AccountModel,
        on_delete=models.PROTECT,
        related_name="transactions",
        help_text="The account affected by this transaction."
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="The amount of the transaction."
    )
    tx_type = models.CharField(
        max_length=10,
        choices=[('debit', 'Debit'), ('credit', 'Credit')],
        help_text="Type of transaction: debit or credit."
    )
    description = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Optional description for this transaction."
    )
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_transactions",
        help_text="User who created this transaction."
    )

    class Meta:
        verbose_name = "Transaction"
        verbose_name_plural = "Transactions"
        ordering = ["-created"]
        indexes = [
            models.Index(fields=["journal_entry", "account", "tx_type"]),
        ]

    def __str__(self):
        return f"{self.account.code}-{self.account.name}/: {self.amount}/{self.tx_type}"

    def clean(self):
        # Add any custom validation here
        if self.amount <= 0:
            raise ValidationError("Transaction amount must be positive.")
        if self.tx_type not in ["debit", "credit"]:
            raise ValidationError("Transaction type must be 'debit' or 'credit'.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)