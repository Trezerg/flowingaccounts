from api.models import TaxRuleModel
from django_ledger.models.transactions import TransactionModel
from decimal import Decimal

def calculate_and_apply_tax(company, journal_entry, revenue_account, coa_model, base_amount):
    """
    Applies active tax rules as extra transaction lines in the journal entry.

    - revenue_account: the normal revenue account used.
    - base_amount: the original invoice/bill amount.
    """
    tax_rules = TaxRuleModel.objects.filter(company=company, is_active=True)

    for tax in tax_rules:
        tax_amount = (base_amount * tax.rate) / Decimal("100.00")

        # Get or create tax liability account under liabilities
        tax_account = revenue_account  # Fallback
        try:
            tax_account = coa_model.accountmodel_set.get(code="2101")  # Example tax payable code
        except:
            pass

        # Add tax amount as a separate credit (or debit for bills)
        TransactionModel.objects.create(
            journal_entry=journal_entry,
            account=tax_account,
            amount=tax_amount,
            tx_type="credit" if revenue_account.role == "Revenue" else "debit"
        )
