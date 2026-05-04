from django.db import models
from django.utils.text import slugify

# Create your models here.

class Supplier(models.Model):
    supplier_name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.supplier_name)
            slug = base_slug
            counter = 1
            # Ensure uniqueness
            while Supplier.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)            
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
    is_active = models.BooleanField(default=True)   

    def __str__(self):
        return self.supplier_name 


class Stock(models.Model):
    product_name = models.CharField(max_length=100)
    specification = models.CharField(max_length=100)
    quantity = models.PositiveIntegerField()
    unit = models.CharField(max_length=20, blank=True)  # e.g. "bags"
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2)   # Buying price
    unit_price =  models.DecimalField(max_digits=10, decimal_places=2)
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT)
    payment_mode = models.CharField(
        max_length=10,
        choices=[("Cash", "Cash"), ("Credit", "Credit")],
        default="Cash"
    )
    date_received = models.DateField()

  