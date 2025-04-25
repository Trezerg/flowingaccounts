from django.db import models
from django_ledger.models import AccountModel
from api.models import Company

class TaxRule(models.Model):
    REGION_CHOICES = [
        ('US', 'United States'),
        ('EU', 'European Union'),
        # Add more as needed
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    region = models.CharField(max_length=10, choices=REGION_CHOICES)
    rate = models.DecimalField(max_digits=5, decimal_places=2)  # e.g., 15.00 for 15%
    account = models.ForeignKey(AccountModel, on_delete=models.CASCADE)  # Tax Payable Account
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} ({self.rate}%) — {self.region}" 