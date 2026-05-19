from django.db import models
from django.utils import timezone
from django.utils.text import slugify
from .validators import validate_ugandan_national_id
from django.core.validators import RegexValidator, ValidationError


# Create your models here.
validate_phone_number = RegexValidator(
    regex=r'^\+256\d{9}$',
    message='Phone number must start with +256 and contain 9 digits (e.g. +256760752349).'
)



def validate_positive(value):
    if value < 0:
        raise ValidationError("Quantity must be a positive number.")

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

def generate_goods_receipt_number():
    last_receipt = GoodsReceipt.objects.order_by("id").last()
    if not last_receipt:
        return "NYONDO-0001"
    last_number = int(last_receipt.receipt_number.split("-")[-1])
    return f"NYONDO-{last_number+1:04d}"


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
    contact_number = models.CharField(max_length=9, blank=True, validators=[validate_phone_number])    # Contact phone number
    address = models.TextField(blank=True)                 # Physical or mailing address
    email = models.EmailField(blank=True)                  # Optional email contact
    date_added = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)   

    def save(self, *args, **kwargs):
        self.full_clean()     # Runs validators
        super().save(*args, **kwargs)

    def __str__(self):
        return self.supplier_name 


class Stock(models.Model):
    product_name = models.CharField(max_length=100)
    specification = models.CharField(max_length=100)
    quantity = models.IntegerField(validators=[validate_positive])
    unit = models.CharField(max_length=20, blank=True)  # e.g. "bags"
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, validators=[validate_positive])   # Buying price
    unit_price =  models.DecimalField(max_digits=10, decimal_places=2, validators=[validate_positive])  # Selling price
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT)
    payment_mode = models.CharField(
        max_length=10,
        choices=[("Cash", "Cash"), ("Credit", "Credit")],
        default="Cash"
    )
    credit_terms = models.CharField(max_length=50, blank=True, null=True)  # e.g., "30 days", "Cash on Delivery"
    total_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    date_received = models.DateField()
    def save(self, *args, **kwargs):
        # ✅ Run validators before saving
        self.full_clean()
        self.total_cost = self.quantity * self.unit_cost
        super().save(*args, **kwargs)

class SupplierCredit(models.Model):

    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.CASCADE
    )

    stock = models.ForeignKey(
        Stock,
        on_delete=models.CASCADE
    )

    total_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[validate_positive]
    )

    amount_paid = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    balance = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    due_date = models.DateField(
        blank=True,
        null=True
    )

    status = models.CharField(
        max_length=20,
        choices=[
            ("Pending", "Pending"),
            ("Partial", "Partial"),
            ("Paid", "Paid"),
        ],
        default="Pending"
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def save(self, *args, **kwargs):

        self.balance = self.total_amount - self.amount_paid

        if self.balance <= 0:
            self.status = "Paid"

        elif self.amount_paid > 0:
            self.status = "Partial"

        else:
            self.status = "Pending"

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.supplier} - {self.balance}"


class SupplierPayment(models.Model):

    credit = models.ForeignKey(
        SupplierCredit,
        on_delete=models.CASCADE,
        related_name="payments"
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[validate_positive]
    )

    payment_date = models.DateField(
        auto_now_add=True
    )

    notes = models.TextField(
        blank=True,
        null=True
    )

    def save(self, *args, **kwargs):

        # Save payment first
        super().save(*args, **kwargs)

        # Get related supplier credit
        credit = self.credit

        # Calculate all payments
        total_paid = credit.payments.aggregate(
            total=models.Sum("amount")
        )["total"] or 0

        # Update credit
        credit.amount_paid = total_paid

        # Save updated balance/status
        credit.save()

    def __str__(self):
        return f"{self.amount}"

class Sale(models.Model):

    customer_name = models.CharField(max_length=100)
    customer_phone = models.CharField(max_length=15, validators=[validate_phone_number])
    distance_km = models.IntegerField(default=0, validators=[validate_positive])
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

        super().save(*args, **kwargs)

        self.transport_cost = self.calculate_transport()
        self.grand_total = self.total_amount() + self.transport_cost

        super().save(
            update_fields=[
            "transport_cost",
            "grand_total"
            ]
        )

class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, related_name="items", on_delete=models.CASCADE)
    stock = models.ForeignKey(Stock, on_delete=models.PROTECT)
    quantity = models.IntegerField(validators=[validate_positive])
    unit = models.CharField(max_length=20)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, validators=[validate_positive])
    total_price = models.DecimalField(max_digits=12, decimal_places=2)
    def save(self, *args, **kwargs):
        if not self.pk:
            # New SaleItem → reduce stock
            if self.stock.quantity < self.quantity:
                raise ValueError("Not enough stock available")
            self.stock.quantity -= self.quantity
        else:
            # Editing existing SaleItem → adjust stock difference
            old_item = SaleItem.objects.get(pk=self.pk)
            difference = self.quantity - old_item.quantity

            if difference > 0:  # increasing quantity
                if self.stock.quantity < difference:
                    raise ValueError("Not enough stock available")
                self.stock.quantity -= difference
            elif difference < 0:  # decreasing quantity
                self.stock.quantity += abs(difference)
            # if difference == 0 → no change, stock untouched

        self.stock.save()

        # Always enforce unit, price, total from stock
        self.unit = self.stock.unit
        self.unit_price = self.stock.unit_price
        self.total_price = self.quantity * self.unit_price

        super().save(*args, **kwargs)
@property
def profit(self):

    return (
        self.stock.unit_price
        - self.stock.unit_cost
    ) * self.quantity


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
    nin = models.CharField(max_length=14, unique=True, validators=[validate_ugandan_national_id])  # National ID with validation
    phone = models.CharField(max_length=13, validators=[validate_phone_number])
    registered_on = models.DateTimeField(default=timezone.now)

    def save(self, *args, **kwargs):
        self.full_clean()     # Runs validators
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.nin})"


class Deposit(models.Model):
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE, related_name="deposits")
    product = models.CharField(max_length=100)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, validators=[validate_positive])
    payment_method = models.CharField(max_length=50, default="Cash")
    date_registered = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.participant.name} - {self.product} ({self.amount_paid})"


class DepositReceipt(models.Model):
    deposit = models.OneToOneField(Deposit, on_delete=models.CASCADE, related_name="receipt")
    receipt_number = models.CharField(max_length=20, unique=True)
    issued_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # Generate receipt number if not already set
        if not self.receipt_number:
            # Get the last receipt from the database, ordered by ID
            last_receipt = DepositReceipt.objects.order_by("id").last()
            # If no receipts exist, start with the first one
            if not last_receipt:
                # Format: DEP-2026-0001, where 2026 is the year and 0001 is the sequential number
                self.receipt_number = "DEP-2026-0001"
            else:
                # Extract the last sequential number, increment it, and format the new receipt number
                last_number = int(last_receipt.receipt_number.split("-")[-1])
                # Format the new receipt number with leading zeros (e.g., 0002, 0003, etc.)
                self.receipt_number = f"DEP-2026-{last_number+1:04d}"
                # This will ensure that the receipt numbers are sequential and unique, even if some receipts are deleted later on.
        super().save(*args, **kwargs)

    def __str__(self):
        return self.receipt_number


class GoodsCollection(models.Model):
    participant = models.ForeignKey(
        Participant,
        on_delete=models.CASCADE,
        related_name="collections"
    )
    stock = models.ForeignKey(  # ✅ link to Stock instead of plain product name
        Stock,
        on_delete=models.CASCADE,
        related_name="collections",
        null=True
    )
    quantity = models.IntegerField(validators=[validate_positive])
    date_collected = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.participant.name} - {self.stock.product_name} ({self.quantity})"
    

    def get_total_price(self):
        return self.stock.unit_price * self.quantity
    


class GoodsReceipt(models.Model):
    collection = models.OneToOneField(
        GoodsCollection,
        on_delete=models.CASCADE,
        related_name="receipt"  #  makes it accessible as collection.receipt
    )
    receipt_number = models.CharField(max_length=20, unique=True)
    date_issued = models.DateTimeField(auto_now_add=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def save(self, *args, **kwargs):

        if not self.receipt_number:
            self.receipt_number = (
                generate_goods_receipt_number()
            )

        self.total_amount = (
            self.collection.get_total_price()
        )

        super().save(*args, **kwargs)

    def __str__(self):
        return self.receipt_number
    

class Activity(models.Model):
    title = models.CharField(max_length=255)
    color = models.CharField(max_length=20, default="blue")
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} ({self.timestamp})"
