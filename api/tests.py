from django.contrib.auth.models import User
from django.test import TestCase

from django_ledger.models import EntityModel, ChartOfAccountModel, AccountModel

from api.models.company import Company
from api.models.invoice import InvoiceModel
from api.models.payment import PaymentModel


class PartialPaymentTestCase(TestCase):
    def setUp(self):
        # Clean up for a fresh test
        User.objects.filter(username='partialpayuser').delete()
        EntityModel.objects.filter(name='PartialPay Entity').delete()
        ChartOfAccountModel.objects.filter(name__icontains='PartialPay Entity').delete()
        Company.objects.all().delete()
        InvoiceModel.objects.all().delete()
        PaymentModel.objects.all().delete()

        self.user = User.objects.create(username='partialpayuser')
        self.entity = EntityModel.add_root(name='PartialPay Entity', admin=self.user)
        self.company = Company.objects.create(user=self.user, entity=self.entity)

    def test_partial_payments(self):
        # Company and COA setup runs without path conflict
        coa1 = self.company.create_account_structure()
        coa2 = self.company.create_account_structure()
        self.assertEqual(coa1.pk, coa2.pk, "COA path conflict detected!")

        # Create an invoice for $100
        invoice = InvoiceModel.objects.create(company=self.company, customer_name="Test Customer", amount=100, status="submitted")

        # First partial payment
        payment1 = PaymentModel.objects.create(company=self.company, invoice=invoice, amount=30, method="cash", status="posted")
        invoice.refresh_from_db()
        self.assertEqual(float(invoice.paid_amount), 30.0)
        self.assertEqual(float(invoice.balance_due), 70.0)
        self.assertEqual(invoice.status, "partial")

        # Second payment
        payment2 = PaymentModel.objects.create(company=self.company, invoice=invoice, amount=70, method="cash", status="posted")
        invoice.refresh_from_db()
        self.assertEqual(float(invoice.paid_amount), 100.0)
        self.assertEqual(float(invoice.balance_due), 0.0)
        self.assertEqual(invoice.status, "paid")
