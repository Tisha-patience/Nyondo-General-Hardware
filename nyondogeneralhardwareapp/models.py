from django.db import models

# Create your models here.

class Supplier(models.Model):
    supplier_name = models.CharField(max_length=100)                # Supplier name (e.g., Nile Cement Ltd.)
    contact_number = models.CharField(max_length=15, blank=True)    # Contact phone number
    address = models.TextField(blank=True)                 # Physical or mailing address
    email = models.EmailField(blank=True)                  # Optional email contact
    PAYMENT_CHOICES = [
        ("Cash", "Cash"),
        ("Credit", "Credit"),
    ]
    payment_terms = models.CharField(max_length=10, choices=PAYMENT_CHOICES, default="Cash")
    credit_terms = models.CharField(max_length=50, blank=True, null=True)  # e.g., "30 days", "Cash on Delivery"
    date_added = models.DateTimeField(auto_now_add=True) 


class Stock(models.Model):
    product_name = models.CharField(max_length=100)
    specification = models.CharField(max_length=100)
    quantity = models.PositiveIntegerField()
    unit = models.CharField(max_length=20, blank=True)  # e.g. "bags"
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2)   # Buying price
    unit_price =  models.DecimalField(max_digits=10, decimal_places=2)
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE)
    payment_mode = models.CharField(
        max_length=10,
        choices=[("Cash", "Cash"), ("Credit", "Credit")],
        default="Cash"
    )
    date_received = models.DateField()

  