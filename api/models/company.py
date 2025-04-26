from django.db import models
from django.contrib.auth.models import User
from django_ledger.models import EntityModel, LedgerModel, ChartOfAccountModel, AccountModel
from django.utils.text import slugify
import uuid

class Company(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    entity = models.ForeignKey(EntityModel, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.entity.name} - {self.user.username}"

    def create_account_structure(self):
        if ChartOfAccountModel.objects.filter(entity=self.entity).exists():
            return ChartOfAccountModel.objects.get(entity=self.entity)

        coa = ChartOfAccountModel.objects.create(
            entity=self.entity,
            name=f"{self.entity.name} Chart of Accounts",
            slug=slugify(f"{self.entity.name}-{self.entity.id}")
        )

        # Create Root
        root = AccountModel.add_root(
            name="Root Account",
            code="0000",
            role="Equity",
            coa_model=coa
        )

        # Main categories
        asset = root.add_child(name="Assets", code="1000", role="Asset", coa_model=coa)
        liability = root.add_child(name="Liabilities", code="2000", role="Liability", coa_model=coa)
        equity = root.add_child(name="Equity", code="3000", role="Equity", coa_model=coa)
        revenue = root.add_child(name="Revenue", code="4000", role="Revenue", coa_model=coa)
        expense = root.add_child(name="Expenses", code="5000", role="Expense", coa_model=coa)

        # ✅ Sub-accounts needed for system
        if asset:
            asset.add_child(name="Cash", code="1100", role="Asset", coa_model=coa)
            asset.add_child(name="Accounts Receivable", code="1200", role="Asset", coa_model=coa)
        if liability:
            liability.add_child(name="Accounts Payable", code="2100", role="Liability", coa_model=coa)
        if revenue:
            revenue.add_child(name="Sales Revenue", code="4100", role="Revenue", coa_model=coa)

        return coa


    def ensure_account_structure(self):
        """
        Ensure a Chart of Accounts exists. If not, create it.
        """
        existing_coa = ChartOfAccountModel.objects.filter(entity=self.entity).first()
        if existing_coa:
            return existing_coa
        return self.create_account_structure()