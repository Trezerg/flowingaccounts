from django_ledger.models.journal_entry import JournalEntryModel

def patched_mark_as_posted(self, commit=True, verify=True, **kwargs):
    if verify:
        self.verify()

    self.posted = True
    self.locked = True

    if commit:
        self.save()

# Monkey patch
JournalEntryModel.mark_as_posted = patched_mark_as_posted
