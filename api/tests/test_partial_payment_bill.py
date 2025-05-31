from django.contrib.auth.models import User
from django.test import TestCase
from django_ledger.models import EntityModel, ChartOfAccountModel, AccountModel
from api.models.company import Company
from api.models.invoice import InvoiceModel
from api.models.payment import PaymentModel
from api.models.bill import BillModel

class TestPartialPaymentBill(TestCase):
    def setUp(self):
        User.objects.filter(username='partialpayuser').delete()
        EntityModel.objects.filter(name='PartialPay Entity').delete()
        ChartOfAccountModel.objects.filter(name__icontains='PartialPay Entity').delete()
        Company.objects.all().delete()
        InvoiceModel.objects.all().delete()
        PaymentModel.objects.all().delete()
        BillModel.objects.all().delete()

        self.user = User.objects.create(username='partialpayuser')
        self.entity = EntityModel.add_root(name='PartialPay Entity', admin=self.user)
        self.company = Company.objects.create(user=self.user, entity=self.entity)

    def test_partial_payments_bill(self):
        coa1 = self.company.create_account_structure()
        coa2 = self.company.create_account_structure()
        self.assertEqual(coa1.pk, coa2.pk, "COA path conflict detected!")

        bill = BillModel.objects.create(company=self.company, vendor_name="Test Vendor", amount=200, status="submitted")
        payment1 = PaymentModel.objects.create(company=self.company, bill=bill, amount=80, method="cash", status="posted")
        bill.refresh_from_db()
        total_paid = sum(p.amount for p in bill.payments.filter(status="posted"))
        self.assertEqual(float(total_paid), 80.0)
        self.assertEqual(bill.status, "partial")
        payment2 = PaymentModel.objects.create(company=self.company, bill=bill, amount=120, method="cash", status="posted")
        bill.refresh_from_db()
        total_paid = sum(p.amount for p in bill.payments.filter(status="posted"))
        self.assertEqual(float(total_paid), 200.0)
        self.assertEqual(bill.status, "paid")
