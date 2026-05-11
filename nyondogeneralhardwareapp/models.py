from django.db import models
from django.utils import timezone
from django.utils.text import slugify

# Create your models here.

def generate_receipt_number():
    # 1. Get the last receipt saved in the database, ordered by ID
    last_receipt = SaleReceipt.objects.order_by("id").last()

    # 2. If no receipts exist yet, start with the very first one
    if not last_receipt:
        return "RCPT-2026-0001"

    # 3. Otherwise, take the last receipt’s number, split it by "-" and grab the last part
    # Example: "RCPT-2026-0007" → "0007"
    last_number = int(last_receipt.receipt_number.split("-")[-1])

    # 4. Increment that number by 1 and format it with leading zeros
    # Example: 7 → "0008"
    return f"RCPT-2026-{last_number+1:04d}"


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
    credit_terms = models.CharField(max_length=50, blank=True, null=True)  # e.g., "30 days", "Cash on Delivery"
    date_received = models.DateField()

class Sale(models.Model):

    customer_name = models.CharField(max_length=100)
    customer_phone = models.CharField(max_length=15)
    distance_km = models.PositiveIntegerField(default=0)
    transport_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    grand_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    date = models.DateTimeField(auto_now_add=True)

    def total_amount(self):
        return sum(item.total_price for item in self.items.all())

    def calculate_transport(self):
        if self.distance_km <= 10 and self.total_amount() >= 500000:
            return 0
        return 30000

    def save(self, *args, **kwargs):
        # ✅ Only recalc if Sale already exists in DB
        if self.pk:
            self.transport_cost = self.calculate_transport()
            self.grand_total = self.total_amount() + self.transport_cost
        super().save(*args, **kwargs)


class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, related_name="items", on_delete=models.CASCADE)
    stock = models.ForeignKey(Stock, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()
    unit = models.CharField(max_length=20)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    total_price = models.DecimalField(max_digits=12, decimal_places=2)



class SaleReceipt(models.Model):
    sale = models.OneToOneField(Sale, on_delete=models.CASCADE)
    receipt_number = models.CharField(max_length=20, unique=True)
    issued_at = models.DateTimeField(auto_now_add=True)
    def save(self, *args, **kwargs):
        if not self.receipt_number:
            self.receipt_number = generate_receipt_number()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.receipt_number

class Participant(models.Model):
    name = models.CharField(max_length=100)
    nin = models.CharField(max_length=20, unique=True)
    phone = models.CharField(max_length=15)
    registered_on = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.name} ({self.nin})"


class Deposit(models.Model):
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE, related_name="deposits")
    product = models.CharField(max_length=100)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=50, default="Cash")
    date_registered = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.participant.name} - {self.product} ({self.amount_paid})"


class DepositReceipt(models.Model):
    deposit = models.OneToOneField(Deposit, on_delete=models.CASCADE, related_name="receipt")
    receipt_number = models.CharField(max_length=20, unique=True)
    issued_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.receipt_number:
            last_receipt = DepositReceipt.objects.order_by("id").last()
            if not last_receipt:
                self.receipt_number = "DEP-2026-0001"
            else:
                last_number = int(last_receipt.receipt_number.split("-")[-1])
                self.receipt_number = f"DEP-2026-{last_number+1:04d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.receipt_number


class GoodsCollection(models.Model):
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE, related_name="collections")
    product = models.CharField(max_length=100)   # e.g. "CEM II N", "Iron Bar 12mm", "Gauge 28 Red"
    quantity = models.PositiveIntegerField()
    date_collected = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.participant.name} - {self.product} ({self.quantity})"
    
class GoodsReceipt(models.Model):
    collection = models.OneToOneField("GoodsCollection", on_delete=models.CASCADE, related_name="receipt")
    receipt_number = models.CharField(max_length=20, unique=True)
    date_issued = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Receipt {self.receipt_number} for {self.collection.participant.name}"
