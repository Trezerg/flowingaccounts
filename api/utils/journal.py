from django_ledger.models.journal_entry import JournalEntryModel
from django_ledger.models.transactions import TransactionModel
from api.models.logging import JournalActivityLogModel
from django.utils import timezone
from api.models import JournalActivityLogModel
from django.utils import timezone
from datetime import timedelta


def get_journal_snapshot(entry):
    return {
        "uuid": str(entry.uuid),
        "je_number": entry.je_number or "",
        "memo": entry.description or "",
        "posted": bool(entry.posted),
        "locked": bool(entry.locked),
        "timestamp": entry.timestamp.isoformat() if entry.timestamp else None,
        "transactions": [
            {
                "account_id": str(tx.account.uuid) if tx.account else "N/A",
                "account_code": tx.account.code if tx.account else "N/A",
                "tx_type": tx.tx_type or "",
                "amount": str(tx.amount) if tx.amount else "0.00",
            }
            for tx in entry.get_transaction_queryset()
        ]
    }



def post_journal_entry(entry, user=None, force=False) -> bool:
    """
    Posts a journal entry, verifies it, and logs the action with a snapshot.
    """
    if not force and entry.is_posted():
        print(f"⚠️ Entry {entry.uuid} is already posted.")
        return False

    if not entry.is_verified():
        print("🔍 Verifying entry...")
        entry.verify()

    try:
        entry.mark_as_posted(commit=True)
        entry.refresh_from_db()

        if entry.is_posted():
            JournalActivityLogModel.objects.create(
                journal_entry=entry,
                action='posted',
                performed_by=user,
                snapshot=get_journal_snapshot(entry),
                note='Auto-posted by system' if user is None else 'User-initiated post'
            )
            print(f"✅ Successfully posted entry: {entry.je_number or entry.uuid}")
            return True
        else:
            print("❌ Posting failed. Entry still unposted.")
            return False

    except Exception as e:
        print(f"❌ Error posting journal entry: {e}")
        return False
    

import traceback

def unpost_journal_entry(entry, user=None, force=False) -> bool:
    if not force and not entry.is_posted():
        print(f"⚠️ Entry {entry.uuid} is not posted.")
        return False

    if not force and entry.timestamp < timezone.now() - timedelta(days=30):
        print("⛔ Cannot unpost entries older than 30 days.")
        return False

    try:
        # Trace which line fails
        snapshot = get_journal_snapshot(entry)

        JournalActivityLogModel.objects.create(
            journal_entry=entry,
            action='unposted',
            performed_by=user,
            snapshot=snapshot,
            note='Forced unpost' if force else 'User-initiated unpost'
        )

        entry.posted = False
        entry.locked = False
        entry.save()

        print(f"🔄 Unposted journal entry: {entry.je_number or entry.uuid}")
        return True

    except Exception as e:
        print(f"❌ Error unposting journal entry: {e}")
        traceback.print_exc()
        return False
