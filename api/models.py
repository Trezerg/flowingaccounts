from django.db import models
from django.contrib.auth.models import User
from django_ledger.models import EntityModel, LedgerModel, ChartOfAccountModel, AccountModel
from django_ledger.models.journal_entry import JournalEntryModel
from django_ledger.models.transactions import TransactionModel
from api.utils.journal import post_journal_entry
from api.models.logging import JournalActivityLogModel



class Company(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    entity = models.ForeignKey(EntityModel, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.entity.name} - {self.user.username}"

    def create_account_structure(self):
        # Check if COA already exists for this entity
        if ChartOfAccountModel.objects.filter(entity=self.entity).exists():
            return ChartOfAccountModel.objects.get(entity=self.entity)

        # Create the Chart of Accounts
        coa = ChartOfAccountModel.objects.create(
            entity=self.entity,
            name=f"{self.entity.name} Chart of Accounts"
        )

        # Create root account with coa_model in the initial creation
        if not AccountModel.objects.filter(code='0000', coa_model=coa).exists():
            root = AccountModel.add_root(
                name="Root Account",
                code="0000",
                role="Equity",
                coa_model=coa
            )

        # Create main account categories with coa_model in the initial creation
        if not AccountModel.objects.filter(code='1000', coa_model=coa).exists():
            asset = root.add_child(
                name="Assets",
                code="1000",
                role="Asset",
                coa_model=coa
            )

        if not AccountModel.objects.filter(code='2000', coa_model=coa).exists():
            liability = root.add_child(
                name="Liabilities",
                code="2000",
                role="Liability",
                coa_model=coa
            )

        if not AccountModel.objects.filter(code='3000', coa_model=coa).exists():
            equity = root.add_child(
                name="Equity",
                code="3000",
                role="Equity",
                coa_model=coa
            )

        if not AccountModel.objects.filter(code='4000', coa_model=coa).exists():
            revenue = root.add_child(
                name="Revenue",
                code="4000",
                role="Revenue",
                coa_model=coa
            )

        if not AccountModel.objects.filter(code='5000', coa_model=coa).exists():
            expense = root.add_child(
                name="Expenses",
                code="5000",
                role="Expense",
                coa_model=coa
            )

        # Create some common sub-accounts with coa_model in the initial creation
        # Assets
        if not AccountModel.objects.filter(code='1100', coa_model=coa).exists():
            cash = asset.add_child(
                name="Cash",
                code="1100",
                role="Asset",
                coa_model=coa
            )

        if not AccountModel.objects.filter(code='1200', coa_model=coa).exists():
            accounts_receivable = asset.add_child(
                name="Accounts Receivable",
                code="1200",
                role="Asset",
                coa_model=coa
            )

        # Liabilities
        if not AccountModel.objects.filter(code='2100', coa_model=coa).exists():
            accounts_payable = liability.add_child(
                name="Accounts Payable",
                code="2100",
                role="Liability",
                coa_model=coa
            )

        # Equity
        if not AccountModel.objects.filter(code='3100', coa_model=coa).exists():
            retained_earnings = equity.add_child(
                name="Retained Earnings",
                code="3100",
                role="Equity",
                coa_model=coa
            )

        # Add more asset accounts
        if not AccountModel.objects.filter(code='1300', coa_model=coa).exists():
            inventory = asset.add_child(
                name="Inventory",
                code="1300",
                role="Asset",
                coa_model=coa
            )

        return coa

    def ensure_account_structure(self):
        """
        Safe method to ensure account structure exists.
        Will only create if it doesn't exist.
        """
        if not ChartOfAccountModel.objects.filter(entity=self.entity).exists():
            return self.create_account_structure()
        return ChartOfAccountModel.objects.get(entity=self.entity)









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
        return f"{self.journal_entry.je_number or self.journal_entry.uuid} | {self.action} by {self.performed_by}"





















from django.db import models
from django_ledger.models import LedgerModel, ChartOfAccountModel, AccountModel
from django_ledger.models.journal_entry import JournalEntryModel
from api.models import Company


class InvoiceModel(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('paid', 'Paid'),
        ('cancelled', 'Cancelled'),
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

        # 🧠 Only trigger automation if it changed to "submitted"
        if self.status == "submitted" and old_status != "submitted":
            from api.services.invoice_posting import auto_post_invoice
            print("🚀 Triggering auto_post_invoice()...")
            auto_post_invoice(self)








    





















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

        # ✅ Step 3: Apply VAT/tax (optional and configurable)
        calculate_and_apply_tax(
            company=self.company,
            journal_entry=journal,
            revenue_account=expense,  # Yes, we use the expense account for tax context
            coa_model=coa,
            base_amount=self.amount
        )

        post_journal_entry(journal, user=self.company.user)

    except Exception as e:
        print(f"⚠️ Auto-posting bill failed: {e}")


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













class PaymentModel(models.Model):
    PAYMENT_METHODS = [
        ('cash', 'Cash'),
        ('bank', 'Bank Transfer'),
        ('card', 'Card'),
        ('other', 'Other'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    invoice = models.ForeignKey("InvoiceModel", on_delete=models.CASCADE, null=True, blank=True, related_name="payments")
    bill = models.ForeignKey("BillModel", on_delete=models.CASCADE, null=True, blank=True, related_name="payments")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    method = models.CharField(max_length=50, default="cash")
    paid_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Payment of {self.amount} for Invoice {self.invoice.id} by {self.method}"

    from django_ledger.models.ledger import LedgerModel
    from django_ledger.models.accounts import AccountModel
    from django_ledger.models.journal_entry import JournalEntryModel
    from django_ledger.models.transactions import TransactionModel
    from api.utils.journal import post_journal_entry
    from decimal import Decimal
    def save(self, *args, **kwargs):

        is_new = self.pk is None
        super().save(*args, **kwargs)

        if is_new:
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

        # 🔄 Update status for Invoice or Bill
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




















class TaxRule(models.Model):
    REGION_CHOICES = [
        ('US', 'United States'),
        ('EU', 'European Union'),
        # Add more as needed
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    region = models.CharField(max_length=10, choices=REGION_CHOICES)
    rate = models.DecimalField(max_digits=5, decimal_places=2)  # e.g., 15.00 for 15%
    account = models.ForeignKey(AccountModel, on_delete=models.CASCADE)  # Tax Payable Account
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} ({self.rate}%) — {self.region}"
