from django.db import models
from .company import Company
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../django-ledger')))
from djangoledger.django_ledger.models.journal_entry import JournalEntryModel
from django_ledger.django_ledger.models.transactions import TransactionModel

class InvoiceModel(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('paid', 'Paid'),
        ('cancelled', 'Cancelled'),
        ('voided', 'Voided'),
        ('refunded', 'Refunded'),
        ('partial_refund', 'Partial Refund'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    customer_name = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Invoice to {self.customer_name} for {self.amount} — {self.status}"

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        old_status = None

        if not is_new:
            try:
                old = InvoiceModel.objects.get(pk=self.pk)
                old_status = old.status
            except InvoiceModel.DoesNotExist:
                pass

        super().save(*args, **kwargs)

        # Only trigger automation if it changed to "submitted"
        if self.status == "submitted" and old_status != "submitted":
            from api.services.invoice_posting import auto_post_invoice
            print("Triggering auto_post_invoice()...")
            auto_post_invoice(self)

    @property
    def paid_amount(self):
        return sum(payment.amount for payment in self.payments.filter(status="posted"))

    @property
    def balance_due(self):
        return self.amount - self.paid_amount

    def void(self, user=None):
        """
        Void the invoice if it is not fully paid. Sets status to 'voided' and prevents future payments/postings.
        Automatically creates a reversal journal entry if posted.
        """
        if self.status not in ["draft", "submitted", "partial"]:
            raise ValueError("Only draft, submitted, or partial invoices can be voided.")
        self.status = "voided"
        self.save(update_fields=["status"])
        # Create reversal journal entry if posted
        orig_journal = JournalEntryModel.objects.filter(description__icontains=f"Invoice: {self.customer_name}", posted=True).last()
        if orig_journal:
            reversal = JournalEntryModel.objects.create(
                ledger=orig_journal.ledger,
                description=f"REVERSAL of {orig_journal.description}",
                posted=False
            )
            for tx in orig_journal.get_transaction_queryset():
                TransactionModel.objects.create(
                    journal_entry=reversal,
                    account=tx.account,
                    amount=tx.amount,
                    tx_type="credit" if tx.tx_type == "debit" else "debit",
                    description=f"Reversal of: {tx.description or ''}"
                )
            # Set reversal_of after reversal is saved and has an id
            reversal.reversal_of = orig_journal
            reversal.save()
            from api.utils.journal import post_journal_entry
            post_journal_entry(reversal, user=user)

    def refund(self, amount=None, user=None):
        """
        Refund a paid invoice. Creates a negative journal entry and records refund as a PaymentModel with negative amount.
        If amount is None, refund the full paid amount.
        """
        if self.status != "paid":
            raise ValueError("Only fully paid invoices can be refunded.")
        refund_amount = amount or self.paid_amount
        if refund_amount <= 0 or refund_amount > self.paid_amount:
            raise ValueError("Invalid refund amount.")
        # Create a negative payment to represent the refund
        from api.models.payment import PaymentModel
        PaymentModel.objects.create(
            company=self.company,
            invoice=self,
            amount=-refund_amount,
            method="cash",
            status="posted"
        )
        self.refresh_from_db()
        # Create reversal journal entry for the refund
        orig_journal = JournalEntryModel.objects.filter(description__icontains=f"Invoice: {self.customer_name}", posted=True).last()
        if orig_journal:
            reversal = JournalEntryModel.objects.create(
                ledger=orig_journal.ledger,
                description=f"REFUND REVERSAL of {orig_journal.description}",
                posted=False
            )
            for tx in orig_journal.get_transaction_queryset():
                TransactionModel.objects.create(
                    journal_entry=reversal,
                    account=tx.account,
                    amount=refund_amount * (tx.amount / self.amount),
                    tx_type="credit" if tx.tx_type == "debit" else "debit",
                    description=f"Refund reversal of: {tx.description or ''}"
                )
            # Set reversal_of after reversal is saved and has an id
            reversal.reversal_of = orig_journal
            reversal.save()
            from api.utils.journal import post_journal_entry
            post_journal_entry(reversal, user=user)
        if self.paid_amount == 0:
            self.status = "refunded"
        else:
            self.status = "partial_refund"
        self.save(update_fields=["status"])