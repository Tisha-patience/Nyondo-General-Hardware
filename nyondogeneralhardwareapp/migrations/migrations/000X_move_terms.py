# migrations/000X_move_terms.py
from django.db import migrations

def move_terms(apps, schema_editor):
    Supplier = apps.get_model("nyondogeneralhardwareapp", "Supplier")
    Stock = apps.get_model("nyondogeneralhardwareapp", "Stock")

    for supplier in Supplier.objects.all():
        for stock in Stock.objects.filter(supplier=supplier):
            if hasattr(supplier, "payment_terms"):
                stock.payment_mode = supplier.payment_terms
            if hasattr(supplier, "credit_terms"):
                stock.credit_terms = supplier.credit_terms
            stock.save()

class Migration(migrations.Migration):

    dependencies = [
        ("nyondogeneralhardwareapp", "0009_sale_remove_supplier_credit_terms_and_more"),  # replace with your last migration
    ]

    operations = [
        migrations.RunPython(move_terms),
    ]
