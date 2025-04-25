from django.db import models
from django.contrib.auth.models import User
from django_ledger.models import EntityModel, ChartOfAccountModel, AccountModel
from django.utils.text import slugify
from django.db import transaction

class Company(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    entity = models.ForeignKey(EntityModel, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.entity.name} - {self.user.username}"



    def create_account_structure(self):
        from django_ledger.models.accounts import AccountModel
        from django_ledger.models.coa import ChartOfAccountModel

        # Check if COA already exists
        existing_coa = ChartOfAccountModel.objects.filter(entity=self.entity).first()
        if existing_coa:
            return existing_coa

        # Generate unique slug
        base_slug = slugify(f"{self.entity.name}-{self.entity.id}")
        slug = base_slug
        i = 1
        while ChartOfAccountModel.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{i}"
            i += 1

        # Create the Chart of Accounts with the unique slug
        coa = ChartOfAccountModel.objects.create(
            entity=self.entity,
            name=f"{self.entity.name} Chart of Accounts",
            slug=slug  # ✅ Now guaranteed to be unique and not blank
)

        with transaction.atomic():
            # ✅ Create Root
            root = AccountModel.add_root(
                name="Root Account",
                code="0000",
                role="Equity",
                coa_model=coa
            )

            # ✅ Core Account Groups
            groups = {
                "Assets": {"code": "1000", "role": "Asset"},
                "Liabilities": {"code": "2000", "role": "Liability"},
                "Equity": {"code": "3000", "role": "Equity"},
                "Revenue": {"code": "4000", "role": "Revenue"},
                "Expenses": {"code": "5000", "role": "Expense"},
            }

            group_nodes = {}

            for name, config in groups.items():
                group_nodes[name] = root.add_child(
                    name=name,
                    code=config["code"],
                    role=config["role"],
                    coa_model=coa
                )

            # ✅ Sub-accounts
            sub_accounts = {
                "Assets": [
                    ("Cash", "1100"),
                    ("Accounts Receivable", "1200"),
                    ("Inventory", "1300"),
                ],
                "Liabilities": [
                    ("Accounts Payable", "2100"),
                ],
                "Equity": [
                    ("Retained Earnings", "3100"),
                ],
            }

            for group, accounts in sub_accounts.items():
                for name, code in accounts:
                    if not AccountModel.objects.filter(code=code, coa_model=coa).exists():
                        group_nodes[group].add_child(
                            name=name,
                            code=code,
                            role=group_nodes[group].role,
                            coa_model=coa
                        )

        return coa

