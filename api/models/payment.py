from django.db import models
from django_ledger.models import LedgerModel, AccountModel, JournalEntryModel, TransactionModel
from .company import Company
from .invoice import InvoiceModel
from .bill import BillModel
from api.utils.journal import post_journal_entry

class PaymentModel(models.Model):
    PAYMENT_METHODS = [
        ('cash', 'Cash'),
        ('bank', 'Bank Transfer'),
        ('card', 'Card'),
        ('other', 'Other'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    invoice = models.ForeignKey(InvoiceModel, on_delete=models.CASCADE, null=True, blank=True, related_name="payments")
    bill = models.ForeignKey(BillModel, on_delete=models.CASCADE, null=True, blank=True, related_name="payments")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    method = models.CharField(max_length=50, choices=PAYMENT_METHODS, default="cash")
    paid_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Payment of {self.amount} for {'Invoice ' + str(self.invoice.id) if self.invoice else 'Bill ' + str(self.bill.id)} by {self.method}"

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)

        if is_new:
            try:
                self._create_journal_entry()
                self._update_document_status()
            except Exception as e:
                # Log the error and potentially notify administrators
                print(f"Error processing payment: {e}")
                # Consider adding a retry mechanism or admin notification here

    def _create_journal_entry(self):
        coa = self.company.ensure_account_structure()
        receivable = AccountModel.objects.get(code="1200", coa_model=coa)
        cash_or_bank_code = "1000" if self.method == "cash" else "1100"
        cash_or_bank = AccountModel.objects.get(code=cash_or_bank_code, coa_model=coa)
        ledger = LedgerModel.objects.get(entity=self.company.entity)

        journal = JournalEntryModel.objects.create(
            ledger=ledger,
            description=f"Payment for {'Invoice ' + str(self.invoice.id) if self.invoice else 'Bill ' + str(self.bill.id)}"
        )

        TransactionModel.objects.create(
            journal_entry=journal,
            account=cash_or_bank,
            amount=self.amount,
            tx_type="debit"
        )

        TransactionModel.objects.create(
            journal_entry=journal,
            account=receivable,
            amount=self.amount,
            tx_type="credit"
        )

        post_journal_entry(journal, user=self.company.user)

    def _update_document_status(self):
        if self.invoice:
            total_paid = sum(p.amount for p in self.invoice.payments.all())
            if total_paid >= self.invoice.amount:
                self.invoice.status = "paid"
            elif total_paid > 0:
                self.invoice.status = "partially_paid"
            self.invoice.save()

        elif self.bill:
            total_paid = sum(p.amount for p in self.bill.payments.all())
            if total_paid >= self.bill.amount:
                self.bill.status = "paid"
            elif total_paid > 0:
                self.bill.status = "partially_paid"
            self.bill.save() 