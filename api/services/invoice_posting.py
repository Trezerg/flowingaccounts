from django_ledger.models.transactions import TransactionModel
from django_ledger.models.journal_entry import JournalEntryModel
from django_ledger.models.accounts import AccountModel
from django_ledger.models.ledger import LedgerModel
from api.utils.journal import post_journal_entry
from decimal import Decimal
from api.services.tax import calculate_and_apply_tax


def auto_post_invoice(invoice):
    try:
        from api.models.tax import TaxRule

        company = invoice.company
        coa = company.ensure_account_structure()
        receivable = AccountModel.objects.get(code="1200", coa_model=coa)  # Debit
        revenue = AccountModel.objects.get(code="4000", coa_model=coa)     # Credit
        ledger = LedgerModel.objects.get(entity=company.entity)

        # Create the Journal Entry
        journal = JournalEntryModel.objects.create(
            ledger=ledger,
            description=f"Invoice: {invoice.customer_name}",
        )

        # Add main transaction lines
        TransactionModel.objects.create(
            journal_entry=journal,
            account=receivable,
            amount=invoice.amount,
            tx_type="debit"
        )

        TransactionModel.objects.create(
            journal_entry=journal,
            account=revenue,
            amount=invoice.amount,
            tx_type="credit"
        )

        # ✅ STEP 3: Apply tax logic (if applicable)
        calculate_and_apply_tax(
            company=company,
            journal_entry=journal,
            revenue_account=revenue,
            coa_model=coa,
            base_amount=invoice.amount
        )

        # Auto-post the journal
        success = post_journal_entry(journal, user=company.user)

        if success:
            print(f"✅ Auto-posted journal for invoice: {invoice.id} — {journal.je_number or journal.uuid}")
        else:
            print(f"❌ Journal entry for invoice {invoice.id} failed to post.")

    except Exception as e:
        print(f"⚠️ Auto-posting failed: {e}")
