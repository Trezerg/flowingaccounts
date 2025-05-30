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
        ledger = LedgerModel.objects.get(entity=self.company.entity)

        if self.invoice:
            # Incoming payment (customer invoice)
            receivable = AccountModel.objects.get(code="1200", coa_model=coa)
            cash_or_bank_code = "1000" if self.method == "cash" else "1100"
            cash_or_bank = AccountModel.objects.get(code=cash_or_bank_code, coa_model=coa)
            journal = JournalEntryModel.objects.create(
                ledger=ledger,
                description=f"Payment for Invoice {self.invoice.id}"
            )
            # DR: Cash/Bank, CR: Accounts Receivable
            from api.models.transaction import TransactionModel
            TransactionModel.objects.create(
                journal_entry=journal,
                account=cash_or_bank,
                amount=self.amount,
                tx_type="debit",
                description=f"Payment received for Invoice {self.invoice.id}"
            )
            TransactionModel.objects.create(
                journal_entry=journal,
                account=receivable,
                amount=self.amount,
                tx_type="credit",
                description=f"Payment received for Invoice {self.invoice.id}"
            )
        elif self.bill:
            # Outgoing payment (vendor bill)
            payable = AccountModel.objects.get(code="2100", coa_model=coa)
            cash_or_bank_code = "1000" if self.method == "cash" else "1100"
            cash_or_bank = AccountModel.objects.get(code=cash_or_bank_code, coa_model=coa)
            journal = JournalEntryModel.objects.create(
                ledger=ledger,
                description=f"Payment for Bill {self.bill.id}"
            )
            # DR: Accounts Payable, CR: Cash/Bank
            from api.models.transaction import TransactionModel
            TransactionModel.objects.create(
                journal_entry=journal,
                account=payable,
                amount=self.amount,
                tx_type="debit",
                description=f"Vendor payment for Bill {self.bill.id}"
            )
            TransactionModel.objects.create(
                journal_entry=journal,
                account=cash_or_bank,
                amount=self.amount,
                tx_type="credit",
                description=f"Vendor payment for Bill {self.bill.id}"
            )
        else:
            raise ValueError("Payment must be linked to either an invoice or a bill.")

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