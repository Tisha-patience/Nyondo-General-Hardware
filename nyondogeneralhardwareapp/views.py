from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils.timezone import now
from django.db.models import Sum, Count, F
from django.utils.dateparse import parse_date
from reportlab.lib.pagesizes import A4
from django.db.models import Sum
from django.db.models import ProtectedError
from django.db import transaction
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required, user_passes_test
from nyondogeneralhardwareapp.models import Stock, Supplier, Sale, SaleItem, Deposit, Participant, GoodsCollection, Activity

# Create your views here.
def index(request):
    return render(request, 'index.html')


def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)  # logs the user in
            return redirect("login_redirect")  # send them to role-based dashboard
        else:
            return render(request, "login.html", {"error": "Invalid credentials"})

    return render(request, "login.html")


def login_redirect(request):
    user = request.user
    if user.is_superuser:
        return redirect("accountsdashboard")
    elif user.groups.filter(name="Store Manager").exists():
        return redirect("manager_dashboard")
    elif user.groups.filter(name="Sales Attendant").exists():
        return redirect("attendant_dashboard")
    else:
        return redirect("index")


@login_required
@user_passes_test(lambda u: u.is_superuser)
def dashboard(request):
    total_customers = Participant.objects.count()
    deposits_total = Deposit.objects.aggregate(Sum("amount_paid"))["amount_paid__sum"] or 0
    sales_total = Sale.objects.aggregate(Sum("grand_total"))["grand_total__sum"] or 0
    total_revenue = deposits_total + sales_total

    stock_items = Stock.objects.count()
    suppliers = Supplier.objects.count()

    # Get participants with their total deposits
    participants = Participant.objects.all()
    for p in participants:
        p.total_deposits = p.deposits.aggregate(Sum("amount_paid"))["amount_paid__sum"] or 0

    activities = Activity.objects.order_by("-timestamp")[:6]

    context = {
        "total_customers": total_customers,
        "total_revenue": total_revenue,
        "stock_items": stock_items,
        "suppliers": suppliers,
        "participants": participants,
        "activities": activities,
    }
    return render(request, "dashboard.html", context)


def is_attendant(user):
    return user.groups.filter(name="Sales Attendant").exists()

@login_required
@user_passes_test(is_attendant)
def attendant_dashboard(request):
    today = now().date()

    # Today's sales total
    today_sales = Sale.objects.filter(date__date=today).aggregate(
        Sum("grand_total")
    )["grand_total__sum"] or 0

    # Receipts issued today (GoodsCollection with receipts)
    receipts_count = GoodsCollection.objects.filter(
        date_collected__date=today,
        receipt__isnull=False
    ).count()

    # Customers served today
    customers_today = Sale.objects.filter(date__date=today).values("customer_name").distinct().count()

    # Low stock count
    low_stock = Stock.objects.filter(quantity__lte=10, quantity__gt=0).count()

    # Low stock items list
    low_stock_items = Stock.objects.filter(quantity__lte=10, quantity__gt=0)

    # Recent sales
    sales = Sale.objects.order_by("-date")[:10]

    # All stock
    stocks = Stock.objects.all()

    context = {
        "today_sales": today_sales,
        "receipts_count": receipts_count,
        "customers_today": customers_today,
        "low_stock": low_stock,
        "low_stock_items": low_stock_items,
        "sales": sales,
        "stocks": stocks,
    }
    return render(request, "attendant_dashboard.html", context)

def is_manager(user):
    return user.groups.filter(name="Store Manager").exists() or user.is_superuser

@login_required
@user_passes_test(is_manager)
def manager_dashboard(request):
    today = now().date()

    # Summary cards
    total_quantity = Stock.objects.aggregate(Sum("quantity"))["quantity__sum"] or 0
    total_stock_value = Stock.objects.aggregate(
        total_value=Sum(F("quantity") * F("unit_price"))
    )["total_value"] or 0
    credit_supplies = Stock.objects.filter(payment_mode="Credit").count()

    sales_total = Sale.objects.aggregate(Sum("grand_total"))["grand_total__sum"] or 0
    stock_cost_total = Stock.objects.aggregate(
        total_cost=Sum(F("quantity") * F("unit_cost"))
    )["total_cost"] or 0
    profit_margin = sales_total - (stock_cost_total or 0)

    # Stock levels
    low_stock_items = Stock.objects.filter(quantity__lte=10, quantity__gt=0)
    out_of_stock_items = Stock.objects.filter(quantity=0)
    available_items = Stock.objects.filter(quantity__gt=10)

    # Editable stock table
    stocks = Stock.objects.all()

    # Recent suppliers
    suppliers = Supplier.objects.order_by("-id")[:5]

    context = {
        "today": today,
        "total_quantity": total_quantity,
        "total_stock_value": total_stock_value,
        "credit_supplies": credit_supplies,
        "profit_margin": profit_margin,
        "stocks": stocks,
        "suppliers": suppliers,
        "low_stock_items": low_stock_items,
        "out_of_stock_items": out_of_stock_items,
        "available_items": available_items,
    }
    return render(request, "store_dashboard.html", context)   


def logout(request):
    messages.info(request, "You have been logged out.")
    return redirect("login")


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
            Activity.objects.create(
    title=f"New sale recorded (UGX {sale.grand_total})",
    color="blue"
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
        Activity.objects.create(
    title=f"Sale deleted for {sale.customer_name}",
    color="red"
)
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
    # Default summary stats
    deposits_total = Deposit.objects.aggregate(Sum("amount_paid"))["amount_paid__sum"] or 0
    sales_total = Sale.objects.aggregate(Sum("grand_total"))["grand_total__sum"] or 0
    total_revenue = deposits_total + sales_total
    stock_remaining = Stock.objects.aggregate(Sum("quantity"))["quantity__sum"] or 0
    total_customers = Participant.objects.count()
    sales = Sale.objects.order_by("-date")[:10]

    context = {
        "total_revenue": total_revenue,
        "total_sales": sales_total,
        "stock_remaining": stock_remaining,
        "total_customers": total_customers,
        "sales": sales,
        "report_type": None,
    }

    return render(request, 'reports.html', context)

def generate_report(request):
    report_type = request.GET.get("report_type")
    from_date = parse_date(request.GET.get("from_date"))
    to_date = parse_date(request.GET.get("to_date"))

    data = None

    if report_type == "Sales Report":
        qs = Sale.objects.all()
        if from_date: qs = qs.filter(date__gte=from_date)
        if to_date: qs = qs.filter(date__lte=to_date)
        data = qs.order_by("-date")

    elif report_type == "Revenue Report":
        deposits = Deposit.objects.all()
        sales = Sale.objects.all()
        if from_date:
            deposits = deposits.filter(date_registered__gte=from_date)
            sales = sales.filter(date__gte=from_date)
        if to_date:
            deposits = deposits.filter(date_registered__lte=to_date)
            sales = sales.filter(date__lte=to_date)
        data = {
            "deposits_total": deposits.aggregate(Sum("amount_paid"))["amount_paid__sum"] or 0,
            "sales_total": sales.aggregate(Sum("grand_total"))["grand_total__sum"] or 0,
        }

    elif report_type == "Stock Report":
        data = Stock.objects.all()

    elif report_type == "Customer Report":
        data = Participant.objects.annotate(
            total_deposits=Sum("deposits__amount_paid")
        ).order_by("-total_deposits")

    return render(request, "reports.html", {
        "report_type": report_type,
        "data": data,
        "from_date": request.GET.get("from_date"),
        "to_date": request.GET.get("to_date"),
    })




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
        Activity.objects.create(
    title=f"Supplier {supplier.supplier_name} added",
    color="orange"
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
        Activity.objects.create(
    title=f"Stock {stock.product_name} deleted",
    color="red"
)
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
        Activity.objects.create(
    title=f"Stock {stock.product_name} added",
    color="orange"
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
     
def participant_delete(request, pk):
    participant = get_object_or_404(Participant, pk=pk)

    if request.method == "POST":
        participant.delete()
        messages.warning(request, f"Participant {participant.name} has been deleted.")
        return redirect("accountscustomer-deposit")  # back to main page

    return render(request, "participant_delete.html", {"participant": participant})

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
        Activity.objects.create(
    title=f"Deposit added for {participant.name}",
    color="green"
)
        # ✅ Redirect to receipt page after saving
        return redirect("deposit_receipt", pk=deposit.pk)

    # ✅ Render the form template
    return render(request, "deposit_add_payment.html", {"participant": participant})

def goods_receipt(request, pk):
    collection = get_object_or_404(GoodsCollection, pk=pk)
    receipt = collection.receipt   # ✅ correct reverse relation
    return render(request, "goods_receipt.html", {
        "collection": collection,
        "receipt": receipt,
    })

def pick_goods(request, participant_id, product=None, quantity=None):
    participant = get_object_or_404(Participant, pk=participant_id)

    if request.method == "POST":
        collection =GoodsCollection.objects.create(
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
        Activity.objects.create(
    title=f"Deposit deleted for {deposit.participant.name}",
    color="red"
)
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
