from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Sale, SaleReceipt, SaleItem, Stock, Deposit, DepositReceipt, GoodsCollection, GoodsReceipt, generate_goods_receipt_number 

# Auto-create receipt when a Sale is made
@receiver(post_save, sender=Sale)
def create_sale_receipt(sender, instance, created, **kwargs):
    if created:
        SaleReceipt.objects.create(sale=instance)

# Auto-update sale totals when a SaleItem is added
@receiver(post_save, sender=SaleItem)
def update_sale_totals(sender, instance, created, **kwargs):
    if created:
        # ✅ Stock reduction is already handled in SaleItem.save()
        # Only update sale totals here
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
            receipt_number=generate_goods_receipt_number(),
            total_amount=instance.get_total_price()  # ✅ uses Stock price
        )
