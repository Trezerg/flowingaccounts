from django.contrib.auth.models import User
from django.test import TestCase
from django_ledger.models import EntityModel, ChartOfAccountModel
from api.models.company import Company
from api.models.invoice import InvoiceModel
from api.models.payment import PaymentModel
from api.models.bill import BillModel

class TestVoidAndRefundInvoice(TestCase):
    def setUp(self):
        User.objects.filter(username='voidrefunduser').delete()
        EntityModel.objects.filter(name='VoidRefund Entity').delete()
        ChartOfAccountModel.objects.filter(name__icontains='VoidRefund Entity').delete()
        Company.objects.all().delete()
        InvoiceModel.objects.all().delete()
        PaymentModel.objects.all().delete()
        BillModel.objects.all().delete()

        self.user = User.objects.create(username='voidrefunduser')
        self.entity = EntityModel.add_root(name='VoidRefund Entity', admin=self.user)
        self.company = Company.objects.create(user=self.user, entity=self.entity)

    def test_void_invoice(self):
        invoice = InvoiceModel.objects.create(company=self.company, customer_name="Test Customer", amount=100, status="submitted")
        invoice.void()
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, "voided")
        with self.assertRaises(ValueError):
            PaymentModel.objects.create(company=self.company, invoice=invoice, amount=10, method="cash", status="posted")

    def test_refund_paid_invoice(self):
        invoice = InvoiceModel.objects.create(company=self.company, customer_name="Test Customer", amount=100, status="submitted")
        PaymentModel.objects.create(company=self.company, invoice=invoice, amount=100, method="cash", status="posted")
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, "paid")
        invoice.refund()
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, "refunded")
        self.assertEqual(float(invoice.paid_amount), 0.0)
        self.assertEqual(float(invoice.balance_due), 100.0)

    def test_partial_refund_invoice(self):
        invoice = InvoiceModel.objects.create(company=self.company, customer_name="Test Customer", amount=100, status="submitted")
        PaymentModel.objects.create(company=self.company, invoice=invoice, amount=100, method="cash", status="posted")
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, "paid")
        invoice.refund(amount=40)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, "partial_refund")
        self.assertEqual(float(invoice.paid_amount), 60.0)
        self.assertEqual(float(invoice.balance_due), 40.0)

class TestVoidAndRefundBill(TestCase):
    def setUp(self):
        User.objects.filter(username='voidrefunduser').delete()
        EntityModel.objects.filter(name='VoidRefund Entity').delete()
        ChartOfAccountModel.objects.filter(name__icontains='VoidRefund Entity').delete()
        Company.objects.all().delete()
        InvoiceModel.objects.all().delete()
        PaymentModel.objects.all().delete()
        BillModel.objects.all().delete()

        self.user = User.objects.create(username='voidrefunduser')
        self.entity = EntityModel.add_root(name='VoidRefund Entity', admin=self.user)
        self.company = Company.objects.create(user=self.user, entity=self.entity)

    def test_void_bill(self):
        bill = BillModel.objects.create(company=self.company, vendor_name="Test Vendor", amount=200, status="submitted")
        bill.void()
        bill.refresh_from_db()
        self.assertEqual(bill.status, "voided")
        with self.assertRaises(ValueError):
            PaymentModel.objects.create(company=self.company, bill=bill, amount=10, method="cash", status="posted")

    def test_refund_paid_bill(self):
        bill = BillModel.objects.create(company=self.company, vendor_name="Test Vendor", amount=200, status="submitted")
        PaymentModel.objects.create(company=self.company, bill=bill, amount=200, method="cash", status="posted")
        bill.refresh_from_db()
        self.assertEqual(bill.status, "paid")
        bill.refund()
        bill.refresh_from_db()
        self.assertEqual(bill.status, "refunded")
        total_paid = sum(p.amount for p in bill.payments.filter(status="posted"))
        self.assertEqual(float(total_paid), 0.0)

    def test_partial_refund_bill(self):
        bill = BillModel.objects.create(company=self.company, vendor_name="Test Vendor", amount=200, status="submitted")
        PaymentModel.objects.create(company=self.company, bill=bill, amount=200, method="cash", status="posted")
        bill.refresh_from_db()
        self.assertEqual(bill.status, "paid")
        bill.refund(amount=80)
        bill.refresh_from_db()
        total_paid = sum(p.amount for p in bill.payments.filter(status="posted"))
        self.assertEqual(bill.status, "partial_refund")
        self.assertEqual(float(total_paid), 120.0)
