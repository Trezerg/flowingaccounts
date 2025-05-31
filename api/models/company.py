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

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)

        if is_new:
            self.create_account_structure()
            # Ensure a LedgerModel exists for this entity
            if not LedgerModel.objects.filter(entity=self.entity).exists():
                LedgerModel.objects.create(entity=self.entity, name=f"Ledger for {self.entity.name}")

    def create_account_structure(self):
        if ChartOfAccountModel.objects.filter(entity=self.entity).exists():
            return ChartOfAccountModel.objects.get(entity=self.entity)

        coa = ChartOfAccountModel.objects.create(
            entity=self.entity,
            name=f"{self.entity.name} Chart of Accounts",
            slug=f"coa-{uuid.uuid4().hex}"
        )

        # Always check for existing root for this COA
        root = AccountModel.get_root_nodes().filter(coa_model=coa, code="0000").first()
        if not root:
            root = AccountModel.add_root(
                name="Root Account",
                code="0000",
                role="Equity",
                coa_model=coa
            )

        # Helper to ensure uniqueness by code+coa_model under parent
        def safe_get_or_create_account(parent, name, code, role, coa_model):
            parent.refresh_from_db()  # Ensure latest children from DB
            for child in parent.get_children():
                if child.code == code and child.coa_model_id == coa_model.id:
                    return child
            return parent.add_child(name=name, code=code, role=role, coa_model=coa_model)

        # Add main account categories first (use safe_get_or_create_account)
        asset = safe_get_or_create_account(root, "Assets", "1000", "Asset", coa)
        liability = safe_get_or_create_account(root, "Liabilities", "2000", "Liability", coa)
        equity = safe_get_or_create_account(root, "Equity", "3000", "Equity", coa)
        revenue = safe_get_or_create_account(root, "Revenue", "4000", "Revenue", coa)
        expense = safe_get_or_create_account(root, "Expenses", "5000", "Expense", coa)

        # Add key sub-accounts
        accounts_payable = safe_get_or_create_account(liability, "Accounts Payable", "2100", "Liability", coa)

        # Now add sub-accounts to the correct parents (use safe_get_or_create_account)
        cash = safe_get_or_create_account(asset, "Cash", "1100", "Asset", coa)
        accounts_receivable = safe_get_or_create_account(asset, "Accounts Receivable", "1200", "Asset", coa)
        sales_revenue = safe_get_or_create_account(revenue, "Sales Revenue", "4100", "Revenue", coa)


        # Add other child accounts as needed
        return coa

    def get_or_create_account(self, parent, name, code, role, coa_model):
        # Use treebeard's get_children() and filter in Python
        for child in parent.get_children():
            if child.code == code and child.coa_model == coa_model:
                return child
        return parent.add_child(name=name, code=code, role=role, coa_model=coa_model)

    def ensure_account_structure(self):
        """
        Ensure a Chart of Accounts exists. If not, create it.
        """
        existing_coa = ChartOfAccountModel.objects.filter(entity=self.entity).first()
        if existing_coa:
            return existing_coa
        return self.create_account_structure()