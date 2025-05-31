from django.db import models
from django.db.models import Sum
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
    status = models.CharField(max_length=20, choices=[('posted', 'Posted'), ('pending', 'Pending')], default='posted')

    def __str__(self):
        return f"Payment of {self.amount} for {'Invoice ' + str(self.invoice.id) if self.invoice else 'Bill ' + str(self.bill.id)} by {self.method}"

    def save(self, *args, **kwargs):
        # Prevent payments/postings if invoice or bill is voided
        if (self.invoice and self.invoice.status == "voided") or (self.bill and self.bill.status == "voided"):
            raise ValueError("Cannot make payments on a voided invoice or bill.")
        is_new = self.pk is None
        super().save(*args, **kwargs)

        if is_new:
            try:
                self._create_journal_entry()
            except Exception as e:
                print(f"Error processing payment: {e}")
        # Always update document status after save
        self._update_document_status()

    def _create_journal_entry(self):
        if self.amount is None or self.amount <= 0:
            print("Payment amount must be positive. Journal entry not created.")
            return
        coa = self.company.ensure_account_structure()
        if not coa:
            print("No Chart of Accounts found. Journal entry not created.")
            return
        ledger = LedgerModel.objects.get(entity=self.company.entity)

        if self.invoice:
            try:
                receivable = AccountModel.objects.get(code="1200", coa_model=coa)
                cash_or_bank_code = "1000" if self.method == "cash" else "1100"
                cash_or_bank = AccountModel.objects.get(code=cash_or_bank_code, coa_model=coa)
            except AccountModel.DoesNotExist:
                print("Required account for invoice payment not found. Journal entry not created.")
                return
            journal = JournalEntryModel.objects.create(
                ledger=ledger,
                description=f"Payment for Invoice {self.invoice.id}"
            )
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
            try:
                payable = AccountModel.objects.get(code="2100", coa_model=coa)
                cash_or_bank_code = "1000" if self.method == "cash" else "1100"
                cash_or_bank = AccountModel.objects.get(code=cash_or_bank_code, coa_model=coa)
            except AccountModel.DoesNotExist:
                print("Required account for bill payment not found. Journal entry not created.")
                return
            journal = JournalEntryModel.objects.create(
                ledger=ledger,
                description=f"Payment for Bill {self.bill.id}"
            )
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
            print("Payment must be linked to either an invoice or a bill. Journal entry not created.")
            return
        post_journal_entry(journal, user=self.company.user)

    def _update_document_status(self):
        # Standardize status naming: 'paid', 'partial', 'unpaid'
        if self.invoice:
            paid = self.invoice.paid_amount
            if paid >= self.invoice.amount:
                self.invoice.status = "paid"
            elif paid > 0:
                self.invoice.status = "partial"
            else:
                self.invoice.status = "unpaid"
            self.invoice.save(update_fields=["status"])
        elif self.bill:
            total_paid = self.bill.payments.filter(status="posted").aggregate(total=Sum('amount'))['total'] or 0
            if total_paid >= self.bill.amount:
                self.bill.status = "paid"
            elif total_paid > 0:
                self.bill.status = "partial"
            else:
                self.bill.status = "unpaid"
            self.bill.save(update_fields=["status"])