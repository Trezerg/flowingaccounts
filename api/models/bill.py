from django.db import models
from django_ledger.models import LedgerModel, AccountModel, JournalEntryModel, TransactionModel
from .company import Company
from api.utils.journal import post_journal_entry

class BillModel(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('paid', 'Paid'),
        ('cancelled', 'Cancelled'),
        ('voided', 'Voided'),
        ('partial_refund', 'Partially Refunded'),
        ('refunded', 'Refunded'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    vendor_name = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Bill to {self.vendor_name} for {self.amount} — {self.status}"

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        old_status = None

        if not is_new:
            try:
                old = BillModel.objects.get(pk=self.pk)
                old_status = old.status
            except BillModel.DoesNotExist:
                pass

        super().save(*args, **kwargs)

        if self.status == 'submitted' and old_status != 'submitted':
            self.auto_post_bill()

    def auto_post_bill(self):
        try:
            from api.services.tax import calculate_and_apply_tax
            
            coa = self.company.ensure_account_structure()
            expense = AccountModel.objects.get(code="5000", coa_model=coa)
            payable = AccountModel.objects.get(code="2100", coa_model=coa)
            ledger = LedgerModel.objects.get(entity=self.company.entity)

            journal = JournalEntryModel.objects.create(
                ledger=ledger,
                description=f"Bill: {self.vendor_name}"
            )

            # Base expense debit
            TransactionModel.objects.create(
                journal_entry=journal,
                account=expense,
                amount=self.amount,
                tx_type="debit"
            )

            # Payable credit
            TransactionModel.objects.create(
                journal_entry=journal,
                account=payable,
                amount=self.amount,
                tx_type="credit"
            )

            # Apply VAT/tax (optional and configurable)
            calculate_and_apply_tax(
                company=self.company,
                journal_entry=journal,
                revenue_account=expense,  # Yes, we use the expense account for tax context
                coa_model=coa,
                base_amount=self.amount
            )

            post_journal_entry(journal, user=self.company.user)

        except Exception as e:
            print(f"Auto-posting bill failed: {e}")
            # Consider adding retry logic or admin notification here

    def void(self, user=None):
        """
        Void the bill if it is not fully paid. Sets status to 'voided' and prevents future payments/postings.
        Automatically creates a reversal journal entry if posted.
        """
        if self.status not in ["draft", "submitted", "partial"]:
            raise ValueError("Only draft, submitted, or partial bills can be voided.")
        self.status = "voided"
        self.save(update_fields=["status"])
        # Create reversal journal entry if posted
        orig_journal = JournalEntryModel.objects.filter(description__icontains=f"Bill: {self.vendor_name}", posted=True).last()
        if orig_journal:
            reversal = JournalEntryModel.objects.create(
                ledger=orig_journal.ledger,
                description=f"REVERSAL of {orig_journal.description}",
                posted=False,
                reversal_of=orig_journal
            )
            for tx in orig_journal.get_transaction_queryset():
                TransactionModel.objects.create(
                    journal_entry=reversal,
                    account=tx.account,
                    amount=tx.amount,
                    tx_type="credit" if tx.tx_type == "debit" else "debit",
                    description=f"Reversal of: {tx.description or ''}"
                )
            from api.utils.journal import post_journal_entry
            post_journal_entry(reversal, user=user)

    def refund(self, amount=None, user=None):
        """
        Refund a paid bill. Creates a negative journal entry and records refund as a PaymentModel with negative amount.
        If amount is None, refund the full paid amount.
        """
        if self.status != "paid":
            raise ValueError("Only fully paid bills can be refunded.")
        refund_amount = amount or sum(p.amount for p in self.payments.filter(status="posted"))
        if refund_amount <= 0 or refund_amount > sum(p.amount for p in self.payments.filter(status="posted")):
            raise ValueError("Invalid refund amount.")
        from api.models.payment import PaymentModel
        PaymentModel.objects.create(
            company=self.company,
            bill=self,
            amount=-refund_amount,
            method="cash",
            status="posted"
        )
        self.refresh_from_db()
        # Create reversal journal entry for the refund
        orig_journal = JournalEntryModel.objects.filter(description__icontains=f"Bill: {self.vendor_name}", posted=True).last()
        if orig_journal:
            reversal = JournalEntryModel.objects.create(
                ledger=orig_journal.ledger,
                description=f"REFUND REVERSAL of {orig_journal.description}",
                posted=False,
                reversal_of=orig_journal
            )
            for tx in orig_journal.get_transaction_queryset():
                TransactionModel.objects.create(
                    journal_entry=reversal,
                    account=tx.account,
                    amount=refund_amount * (tx.amount / self.amount),
                    tx_type="credit" if tx.tx_type == "debit" else "debit",
                    description=f"Refund reversal of: {tx.description or ''}"
                )
            from api.utils.journal import post_journal_entry
            post_journal_entry(reversal, user=user)
        total_paid = sum(p.amount for p in self.payments.filter(status="posted"))
        if total_paid == 0:
            self.status = "refunded"
        else:
            self.status = "partial_refund"
        self.save(update_fields=["status"])