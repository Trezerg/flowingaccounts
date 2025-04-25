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