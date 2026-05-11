from django.db.models.signals import post_save
from django.dispatch import receiver
import uuid
from .models import Sale, SaleReceipt, SaleItem, Stock, Deposit, DepositReceipt, GoodsCollection, GoodsReceipt 

# Auto-create receipt when a Sale is made
@receiver(post_save, sender=Sale)
def create_sale_receipt(sender, instance, created, **kwargs):
    if created:
        SaleReceipt.objects.create(sale=instance)

# Auto-update stock and totals when a SaleItem is added
@receiver(post_save, sender=SaleItem)
def update_sale_and_stock(sender, instance, created, **kwargs):
    if created:
        # Safety check: prevent overselling
        if instance.stock.quantity < instance.quantity:
            raise ValueError(f"Not enough stock for {instance.stock.product_name}")

        # Reduce stock
        stock = instance.stock
        stock.quantity -= instance.quantity
        stock.save()

        # Update sale totals
        sale = instance.sale
        sale.transport_cost = sale.calculate_transport()
        sale.grand_total = sale.total_amount() + sale.transport_cost
        sale.save()

# --- Deposit signals ---
@receiver(post_save, sender=Deposit)
def create_deposit_receipt(sender, instance, created, **kwargs):
    if created:
        DepositReceipt.objects.create(deposit=instance)

@receiver(post_save, sender=GoodsCollection)
def create_goods_receipt(sender, instance, created, **kwargs):
    if created:
        GoodsReceipt.objects.create(
            collection=instance,
            receipt_number=str(uuid.uuid4())[:8]  # short unique code
        )        