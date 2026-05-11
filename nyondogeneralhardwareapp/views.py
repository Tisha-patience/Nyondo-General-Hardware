from django.shortcuts import render, redirect
from django.contrib import messages
from django.db.models import Sum
from django.db.models import ProtectedError
from django.db import transaction
from nyondogeneralhardwareapp.models import Stock, Supplier, Sale, SaleItem, Deposit, Participant, GoodsCollection

# Create your views here.
def index(request):
    return render(request, 'index.html')

def login(request):
    
    return render(request, 'login.html')

def dashboard(request):
   # Stats
    total_customers = Participant.objects.count()

    # ✅ Revenue = deposits + sales
    deposits_total = Deposit.objects.aggregate(Sum("amount_paid"))["amount_paid__sum"] or 0
    sales_total = Sale.objects.aggregate(Sum("grand_total"))["grand_total__sum"] or 0
    total_revenue = deposits_total + sales_total

    stock_items = Stock.objects.count()
    suppliers = Supplier.objects.count()

    # Recent deposits (transactions table)
    recent_deposits = Deposit.objects.select_related("participant").order_by("-date_registered")[:5]

    # Recent activity (replace with Activity model later)
    activities = [
        {"title": "New sale recorded", "timestamp": "2 mins ago", "color": "green"},
        {"title": "Stock updated", "timestamp": "20 mins ago", "color": "orange"},
        {"title": "Supplier added", "timestamp": "1 hour ago", "color": "blue"},
    ]

    context = {
        "total_customers": total_customers,
        "total_revenue": total_revenue,
        "stock_items": stock_items,
        "suppliers": suppliers,
        "recent_deposits": recent_deposits,
        "activities": activities,
    }
    return render(request, 'dashboard.html', context)

def sales(request):
    # Fetch all sales and their related items in one go
    sales = Sale.objects.all()

    # Total number of sales
    total_sales = sales.count()

    # Total revenue = sum of grand totals (not sale.total_price, since that's per item)
    total_revenue = sum(sale.grand_total for sale in sales)

    context = {
        "sales": sales,
        "total_sales": total_sales,
        "total_revenue": total_revenue,
    }
    return render(request, "sales.html", context)

def sales_reg(request):
    
    if request.method == "POST":
        with transaction.atomic():
        # Create Sale record
            distance = request.POST.get("distance_km")
            sale = Sale.objects.create(
               customer_name=request.POST.get("customer_name"),
               customer_phone=request.POST.get("customer_phone"),
               distance_km=int(distance) if distance else 0
        )
        
        # Collect multiple items
         # Collect items
        stock_ids = request.POST.getlist("stock_id")
        quantities = request.POST.getlist("quantity") # e.g. ["10", "5", "2"]
        units = request.POST.getlist("unit") # e.g. ["bags", "pieces", "kg"]
        unit_prices = request.POST.getlist("unit_price") # e.g. ["30000", "50000", "2000"]

        # Loop through items
        for i in range(len(stock_ids)):
            stock_item = get_object_or_404(Stock, pk=stock_ids[i])
            qty = int(quantities[i])
            price = float(unit_prices[i])
            total = qty * price

            # ✅ Safety check: prevent overselling
            if stock_item.quantity < qty:
                raise ValueError(f"Not enough stock for {stock_item.product_name}")

            SaleItem.objects.create(
                sale=sale,
                stock = stock_item,
                quantity=qty,
                unit=units[i],
                unit_price=price,
                total_price=total,
            )
             # Reduce stock
            stock_item.quantity -= qty
            stock_item.save()

        # Update transport + grand total
        sale.save()

        return redirect("sale_receipt", pk=sale.pk)

    stocks = Stock.objects.all()
    return render(request, 'sales-reg.html', {"stocks": stocks})



def sale_view(request, pk):
    sale = get_object_or_404(Sale, pk=pk)
    return render(request, "sale_view.html", {"sale": sale})

def sale_edit(request, pk):
    sale = get_object_or_404(Sale, pk=pk)
    if request.method == "POST":
        # Manual update from form fields
        sale.customer_name = request.POST.get("customer_name")
        sale.customer_phone = request.POST.get("customer_phone")
        sale.product = request.POST.get("product")
        sale.quantity = request.POST.get("quantity")
        sale.unit = request.POST.get("unit")
        sale.total_price = request.POST.get("total_price")
        sale.distance_km = request.POST.get("distance_km")
        sale.transport_cost = request.POST.get("transport_cost")
        
        sale.save()
        messages.success(request, "Sale updated successfully.")
        return redirect("accountssales")

    return render(request, "sale_edit.html", {"sale": sale})

def sale_delete(request, pk):
    sale = get_object_or_404(Sale, pk=pk)
    if request.method == "POST":
        sale.delete()
        messages.success(request, "Sale deleted successfully.")
        return redirect("accountssales")
    return render(request, "sale.delete.html", {"sale": sale})

def sale_receipt(request, pk):
    sale = get_object_or_404(Sale.objects.prefetch_related("items"), pk=pk)
    return render(request, "sale_receipt.html", {"sale": sale})

def supplier(request):
     # Total suppliers
    total_suppliers = Supplier.objects.count()

    # Total supplies
    total_supplies = Stock.objects.count()

    # Cash suppliers (distinct suppliers who delivered stock on Cash)
    cash_suppliers = Stock.objects.filter(payment_mode="Cash").values("supplier").distinct().count()

    # Credit suppliers (distinct suppliers who delivered stock on Credit)
    credit_suppliers = Stock.objects.filter(payment_mode="Credit").values("supplier").distinct().count()

    context = {
        "total_suppliers": total_suppliers,
        "cash_suppliers": cash_suppliers,
        "credit_suppliers": credit_suppliers,
        "total_supplies": total_supplies,
        "suppliers": Supplier.objects.all(),
    }
    return render(request, "supplier.html", context)
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from .models import Supplier

def deactivate_supplier(request, pk,slug):
    supplier = get_object_or_404(Supplier, pk=pk, slug=slug)
    supplier.is_active = False
    supplier.save()
    messages.warning(request, f"Supplier {supplier.supplier_name} has been deactivated.")
    return redirect("accountssupplier")   # redirect back to supplier list

def activate_supplier(request, pk,slug):
    supplier = get_object_or_404(Supplier, pk=pk, slug=slug)
    supplier.is_active = True
    supplier.save()
    messages.success(request, f"Supplier {supplier.supplier_name} has been reactivated.")
    return redirect("accountssupplier")




def stock(request):
    stocks = Stock.objects.all()
     # Calculate status counts
    available_count = stocks.filter(quantity__gt=10).count()
    low_count = stocks.filter(quantity__gt=0, quantity__lte=10).count()
    out_count = stocks.filter(quantity=0).count()

    return render(request, "stock.html", {
        "stocks": stocks,
        "available_count": available_count,
        "low_count": low_count,
        "out_count": out_count,
        "total_count": stocks.count(),
    })
   

def reports(request):

    return render(request, 'reports.html')




def supplier_reg(request):
     if request.method == "POST":
        payload = request.POST
        # Supplier fields
        sent_supplier_name = payload.get("supplier_name")
        sent_contact_number = payload.get("contact_number")
        sent_address = payload.get("address")
        sent_email = payload.get("email")
        
        Supplier.objects.create(
            supplier_name= sent_supplier_name,
            contact_number= sent_contact_number,
            address= sent_address,
            email= sent_email,
           
        )
        return redirect ('accountssupplier')
     
     return render(request, 'supplierReg.html')


def back(request):
    return render(request, 'index.html')

def receipt(request):
    return render(request, 'receipt.html')

def supplier_edit(request, pk, slug):
    supplier = get_object_or_404(Supplier, pk=pk, slug=slug)
    if request.method == "POST":
        # Collect values manually from the form fields
        supplier.supplier_name = request.POST.get("supplier_name")
        supplier.contact_number = request.POST.get("contact_number")
        supplier.email = request.POST.get("email")
        supplier.address = request.POST.get("address")
       
        # Save changes
        supplier.save()
        return redirect("accountssupplier") 


    return render(request, 'supplier-edit.html', {"supplier":supplier})


def stock_edit(request,pk):
    stock = get_object_or_404(Stock, pk=pk)
    if request.method == "POST":
        stock.quantity = request.POST.get("quantity")
        stock.unit_cost = request.POST.get("unit_cost")
        stock.unit_price = request.POST.get("unit_price")
        stock.payment_mode = request.POST.get("payment_mode")
        stock.credit_terms = request.POST.get("credit_terms")
        stock.date_received = request.POST.get("date_received")


        stock.save()
        messages.success(request, "Stock updated successfully.")
        return redirect("accountsstock")

    return render(request, 'stock-edit.html', {"stock":stock})

def stock_delete(request ,pk):
    stock = get_object_or_404(Stock, pk=pk)
    if request.method == "POST":
        # Delete the record
        stock.delete()
        messages.success(request, f"{stock.product_name} deleted successfully.")
        return redirect("accountsstock")

    # If GET, show confirmation page
    return render(request, "stock.delete.html", {"stock": stock})


def stock_view(request, pk):
    # Fetch the stock record by ID
    stock = get_object_or_404(Stock, pk=pk)
    # Render the detail page
    return render(request, "stock_view.html", {"stock": stock})


def stock_reg(request):
    if request.method == "POST":
        payload = request.POST
        sent_product_name = payload.get("product_name")
        sent_specification = payload.get("specification")
        sent_supplier = payload.get("supplier")
        sent_payment_mode = payload.get("payment_mode")
        sent_credit_terms= payload.get("credit_terms") if payload.get("payment_mode") == "Credit" else None,
        sent_unit_cost = payload.get("unit_cost")
        sent_unit_price = payload.get("unit_price")
        sent_quantity = payload.get("quantity")
        sent_unit = payload.get("unit")
        sent_date_received = payload.get("date")

        # ✅ fetch the Supplier object
        supplier = Supplier.objects.get(id=sent_supplier)

 # ✅ Block inactive suppliers
        if not supplier.is_active:
            messages.error(request, "This supplier is deactivated. Choose another supplier.")
            return redirect("accountsstock-reg")

        Stock.objects.create(
            product_name = sent_product_name,
            specification= sent_specification,
            supplier= supplier,
            payment_mode= sent_payment_mode,
            credit_terms= sent_credit_terms,
            unit_cost= sent_unit_cost,
            unit_price= sent_unit_price,
            quantity= sent_quantity,
            unit=sent_unit, 
            date_received= sent_date_received,

        )
        return redirect ('accountsstock')


    suppliers = Supplier.objects.filter(is_active=True)

    return render(request, 'stock-reg.html', {"suppliers": suppliers})

def customer_deposit(request):
     participants = Participant.objects.all()
     for p in participants:
        # Total deposits
        p.total_deposits = p.deposits.aggregate(Sum("amount_paid"))["amount_paid__sum"] or 0
        # Latest payment method
        latest = p.deposits.order_by("-date_registered").first()
        p.latest_method = latest.payment_method if latest else "—"
        return render(request, "customer-deposit.html", {"participants": participants})
def customer_reg(request):
    if request.method == "POST":
        # Create participant
        participant = Participant.objects.create(
            name=request.POST.get("name"),
            nin=request.POST.get("nin"),
            phone=request.POST.get("number"),
            registered_on=request.POST.get("date"),
        )

        # Create first deposit linked to participant
        deposit = Deposit.objects.create(
            participant=participant,
            product=request.POST.get("product"),
            amount_paid=request.POST.get("amount_paid"),
            payment_method=request.POST.get("payment_method"),
            date_registered=request.POST.get("date"),
        )

        messages.success(request, f"{participant.name} enrolled successfully with first deposit.")
        # ✅ Redirect straight to receipt page
        return redirect("deposit_receipt", pk=deposit.pk)

    return render(request, 'customer-reg.html')

def customer_profile(request, pk):
    participant = get_object_or_404(Participant, pk=pk)
    # Fetch all deposits and collections for this participant
    deposits = participant.deposits.order_by("-date_registered")
    total_balance = deposits.aggregate(Sum("amount_paid"))["amount_paid__sum"] or 0
    collections = participant.collections.order_by("-date_collected")

    # thresholds (unit prices)
    thresholds = {
        "CEM II N (bag)": 50000,
        "CEM III N (bag)": 70000,
        "Iron Bar 10mm (piece)": 20000,
        "Iron Bar 12mm (piece)": 25000,
        "Iron Bar 16mm (piece)": 30000,
        "Iron Sheet Gauge 28 Red": 60000,
        "Iron Sheet Gauge 28 Blue": 60000,
        "Iron Sheet Gauge 30 Galvanized": 70000,
    }

    # eligibility calculation
    eligibility = {}
    for product, price in thresholds.items():
        eligibility[product] = total_balance // price if total_balance >= price else 0

    context = {
        "participant": participant,
        "deposits": deposits,
        "collections": collections,
        "total_balance": total_balance,
        "eligibility": eligibility,
    }
    return render(request, "customer_profile.html", context)

def deposit_add_payment(request, participant_id):
    participant = get_object_or_404(Participant, pk=participant_id)

    if request.method == "POST":
        deposit = Deposit.objects.create(
            participant=participant,
            product=request.POST.get("product"),
            amount_paid=request.POST.get("amount_paid"),
            payment_method=request.POST.get("payment_method"),
            date_registered=request.POST.get("date_registered"),
        )
        # ✅ Redirect to receipt page after saving
        return redirect("deposit_receipt", pk=deposit.pk)

    # ✅ Render the form template
    return render(request, "deposit_add_payment.html", {"participant": participant})

def goods_receipt(request, pk):
    collection = get_object_or_404(GoodsCollection, pk=pk)
    receipt = collection.receipt
    return render(request, "goods_receipt.html", {"collection": collection, "receipt": receipt})



def pick_goods(request, participant_id, product=None, quantity=None):
    participant = get_object_or_404(Participant, pk=participant_id)

    if request.method == "POST":
        GoodsCollection.objects.create(
            participant=participant,
            product=request.POST.get("product"),
            quantity=int(request.POST.get("quantity")),
        )
        # ✅ Redirect straight to final receipt
        return redirect("goods_receipt", pk=collection.pk)
        

    # ✅ Pass product and quantity to template for prefill
    return render(
        request,
        "goodsCollection_form.html",
        {"participant": participant, "product": product, "quantity": quantity},
    )


def deposit_update(request, pk):
    deposit = get_object_or_404(Deposit, pk=pk)

    if request.method == "POST":
        deposit.participant_id = request.POST.get("participant_id")
        deposit.product = request.POST.get("product")
        deposit.amount_paid = request.POST.get("amount_paid")
        deposit.payment_method = request.POST.get("payment_method")
        deposit.date_registered = request.POST.get("date_registered")
        deposit.save()

        messages.info(request, "Deposit updated successfully.")
        return redirect("deposit_receipt", pk=deposit.pk)

    participants = Participant.objects.all()
    return render(request, "deposit_update.html", {"deposit": deposit, "participants": participants})

def deposit_delete(request, pk):
    deposit = get_object_or_404(Deposit, pk=pk)

    if request.method == "POST":
        deposit.delete()
        messages.warning(request, f"Deposit for {deposit.participant.name} has been deleted.")
        return redirect("accountscustomer-deposit")

    # Confirmation page
    return render(request, "deposit_delete.html", {"deposit": deposit})


def deposit_receipt(request, pk):
    deposit = get_object_or_404(Deposit, pk=pk)
    return render(request, "deposit-receipt-detail.html", {"deposit": deposit})

def supplier_view(request, pk, slug ):
    supplier = get_object_or_404(Supplier, pk=pk,slug=slug)
    return render(request, "supplier_view.html", {"supplier": supplier})
    
def supplier_delete(request, pk, slug):
    supplier = get_object_or_404(Supplier, pk=pk, slug=slug)
    if request.method == "POST":
        try:
             supplier.delete()
             messages.success(request, f"Supplier '{supplier.supplier_name}' deleted successfully.")
        except ProtectedError:
            messages.error(
                request,
                f"Cannot delete supplier '{supplier.supplier_name}' because stock records are linked to it. "
                "Please deactivate the supplier instead."
            )

       
        return redirect("accountssupplier")  # back to supplier list
    return render(request, "supplier_delete.html", {"supplier": supplier})