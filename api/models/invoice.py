from django.db import models
from .company import Company

class InvoiceModel(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('paid', 'Paid'),
        ('cancelled', 'Cancelled'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    customer_name = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Invoice to {self.customer_name} for {self.amount} — {self.status}"

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        old_status = None

        if not is_new:
            try:
                old = InvoiceModel.objects.get(pk=self.pk)
                old_status = old.status
            except InvoiceModel.DoesNotExist:
                pass

        super().save(*args, **kwargs)

        # Only trigger automation if it changed to "submitted"
        if self.status == "submitted" and old_status != "submitted":
            from api.services.invoice_posting import auto_post_invoice
            print("Triggering auto_post_invoice()...")
            auto_post_invoice(self)

    @property
    def paid_amount(self):
        return sum(payment.amount for payment in self.payments.filter(status="posted"))

    @property
    def balance_due(self):
        return self.amount - self.paid_amount