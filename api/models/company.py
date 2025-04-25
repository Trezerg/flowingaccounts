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
    # Check if COA already exists for this entity
    if ChartOfAccountModel.objects.filter(entity=self.entity).exists():
        return ChartOfAccountModel.objects.get(entity=self.entity)

    # Create the Chart of Accounts with a unique slug
    coa = ChartOfAccountModel.objects.create(
        entity=self.entity,
        name=f"{self.entity.name} Chart of Accounts",
        slug=slugify(f"{self.entity.name}-{self.entity.id}")
    )

    # Create the root account
    root = AccountModel.add_root(
        name="Root",
        code="0000",
        role="Root",
        coa_model=coa
    )

    # Create main account categories under the root
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

    return coa
