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
        """
        Create the Chart of Accounts and Root Account for this company if it doesn't exist.
        """
    # First check if a Chart of Accounts already exists for this entity
        existing_coa = ChartOfAccountModel.objects.filter(entity=self.entity).first()
        if existing_coa:
            return existing_coa

        # Generate a guaranteed unique slug without relying on entity.id
        unique_id = uuid.uuid4().hex
        slug = f"coa-{unique_id}"
        
        # Create Chart of Accounts with the guaranteed unique slug
        coa = ChartOfAccountModel.objects.create(
            entity=self.entity,
            name=f"{self.entity.name} Chart of Accounts",
            slug=slug
        )

    # Rest of the code remains the same
    # ...

        # Create the Root Account
        root = AccountModel.add_root(
            name="Root Account",
            code="0000",
            role="Equity",
            coa_model=coa
        )

        # Create main categories
        asset = root.add_child(name="Assets", code="1000", role="Asset", coa_model=coa)
        liability = root.add_child(name="Liabilities", code="2000", role="Liability", coa_model=coa)
        equity = root.add_child(name="Equity", code="3000", role="Equity", coa_model=coa)
        revenue = root.add_child(name="Revenue", code="4000", role="Revenue", coa_model=coa)
        expense = root.add_child(name="Expenses", code="5000", role="Expense", coa_model=coa)

        return coa

    def ensure_account_structure(self):
        """
        Ensure a Chart of Accounts exists. If not, create it.
        """
        existing_coa = ChartOfAccountModel.objects.filter(entity=self.entity).first()
        if existing_coa:
            return existing_coa
        return self.create_account_structure()