from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils.timezone import now
from django.db.models import Sum, Count, F
from django.utils.dateparse import parse_date
from reportlab.lib.pagesizes import A4
from django.db.models import Sum
from django.db.models import ProtectedError
from django.db import transaction
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required, user_passes_test,permission_required
from nyondogeneralhardwareapp.models import Stock, Supplier, Sale, SaleItem, Deposit, Participant, GoodsCollection, Activity, SupplierCredit, SupplierPayment

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
    # All registered participants
    participant_count = Participant.objects.count()

    # Unique customers from sales (by phone)
    sale_customers = Sale.objects.values_list("customer_phone", flat=True).distinct()
    sale_customer_count = sale_customers.count()

    # Combine both sets (avoid double-counting)
    total_customers = Participant.objects.values_list("nin", flat=True).union(
        Sale.objects.values_list("customer_phone", flat=True)
    ).count()

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
    messages.info(request, "Logged out successfully.")
    return redirect("login")


def sales(request):
    # Fetch all sales and their related items in one go
    sales = Sale.objects.all().order_by('-date')

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
        try:
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
                stock_ids = request.POST.getlist("stock_id")
                quantities = request.POST.getlist("quantity")
                units = request.POST.getlist("unit")
                unit_prices = request.POST.getlist("unit_price")

                for i in range(len(stock_ids)):
                    stock_item = get_object_or_404(Stock, pk=stock_ids[i])
                    qty = int(quantities[i])
                    price = float(stock_item.unit_price)
                    total = qty * price

                    # ✅ Safety check: prevent overselling
                    if stock_item.quantity < qty:
                        raise ValidationError({
                            "quantity": [f"Not enough stock for {stock_item.product_name}"]
                        })

                    SaleItem.objects.create(
                        sale=sale,
                        stock=stock_item,
                        quantity=qty,
                        unit=units[i],
                        unit_price=price,
                        total_price=total,
                    )
                    stock_item.quantity -= qty
                    stock_item.save()

                # Update transport + grand total
                sale.save()

                return redirect("sale_receipt", pk=sale.pk)

        except ValidationError as e:
            # Pass field-specific errors back
            stocks = Stock.objects.all()
            return render(request, "sales-reg.html", {
                "errors": e.message_dict,
                "data": request.POST,
                "stocks": stocks
            })

        except Exception as e:
            # Pass general error back
            stocks = Stock.objects.all()
            return render(request, "sales-reg.html", {
                "general_error": str(e),
                "data": request.POST,
                "stocks": stocks
            })

    stocks = Stock.objects.all()
    return render(request, "sales-reg.html", {"stocks": stocks})
    

def sale_view(request, pk):
    sale = get_object_or_404(Sale, pk=pk)
    return render(request, "sale_view.html", {"sale": sale})

def sale_edit(request, pk):
    sale = get_object_or_404(Sale, pk=pk)
    sale_item = sale.items.first()  # assuming one item per sale
    stocks = Stock.objects.all()

    if request.method == "POST":
        # Update Sale fields
        sale.customer_name = request.POST.get("customer_name")
        sale.customer_phone = request.POST.get("customer_phone")
         # Check if product or quantity was changed
        stock_id = request.POST.get("stock_id")
        quantity = int(request.POST.get("quantity") or sale_item.quantity)

        if str(sale_item.stock.id) != stock_id or sale_item.quantity != quantity:
            # Product or quantity changed → update SaleItem
            stock_item = get_object_or_404(Stock, pk=stock_id)

            sale_item.stock = stock_item
            sale_item.quantity = quantity
            sale_item.unit = stock_item.unit
            sale_item.unit_price = stock_item.unit_price
            sale_item.save()

        # Update Sale totals
        sale.save()
        messages.success(request, "Sale updated successfully.")
        return redirect("accountssales")

    return render(request, "sale_edit.html", {"sale": sale, "sale_item": sale_item, "stocks": stocks})

@permission_required('nyondogeneralhardwareapp.delete_sale', raise_exception=True)
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
    suppliers = Supplier.objects.all().order_by("-date_added")

    credits = SupplierCredit.objects.select_related(
        "supplier",
        "stock"
    )

    payments = SupplierPayment.objects.select_related(
        "credit",
        "credit__supplier"
    ).order_by("-payment_date")

    stocks = Stock.objects.select_related(
        "supplier"
    ).order_by("-date_received")

    pending_credits = SupplierCredit.objects.exclude(
        status="Paid"
    )

    total_credit = SupplierCredit.objects.aggregate(
        total=Sum("total_amount")
    )["total"] or 0

    total_paid = SupplierCredit.objects.aggregate(
        total=Sum("amount_paid")
    )["total"] or 0

    outstanding_balance = SupplierCredit.objects.aggregate(
        total=Sum("balance")
    )["total"] or 0

    context = {
        "suppliers": suppliers,
        "credits": credits,
        "payments": payments,
        "stocks": stocks,
        "pending_credits": pending_credits,
        "total_credit": total_credit,
        "total_paid": total_paid,
        "outstanding_balance": outstanding_balance,
        "suppliers_count": suppliers.count(),
    }

    return render(
        request,
        "supplier.html",
        context
    )
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
    stocks = Stock.objects.all().order_by("-date_received")

    # Summary counts
    total_products = stocks.count()
    total_quantity = stocks.aggregate(total=Sum("quantity"))["total"] or 0
    low_stock_count = stocks.filter(quantity__gt=0, quantity__lte=10).count()
    total_stock_value = stocks.aggregate(total=Sum("total_cost"))["total"] or 0

    # Inventory alerts
    low_stock_items = stocks.filter(quantity__gt=0, quantity__lte=10)

    # Recently added stock (last 5 entries)
    recent_stock = stocks.order_by("-date_received")[:5]

    return render(request, "stock.html", {
        "stocks": stocks,
        "total_products": total_products,
        "total_quantity": total_quantity,
        "low_stock_count": low_stock_count,
        "total_stock_value": total_stock_value,
        "low_stock_items": low_stock_items,
        "recent_stock": recent_stock,
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

# This view handles generating different types of reports based on user input
# It accepts GET parameters for report type and date range, then queries the database accordingly
# Finally, it renders the same template with the report data
def generate_report(request):
    # Get parameters from the request
    report_type = request.GET.get("report_type")
    # Parse(parse means convert) dates safely (returns None if invalid)
    from_date = parse_date(request.GET.get("from_date"))
    to_date = parse_date(request.GET.get("to_date"))

    data = None
# Depending on the report type, we query different models and apply date filters if provided
    if report_type == "Sales Report":
        # Start with all sales, then filter by date if from_date/to_date are provided
        qs = Sale.objects.all()
        # Apply date filters if provided
        if from_date: qs = qs.filter(date__gte=from_date)
        if to_date: qs = qs.filter(date__lte=to_date)
        # Order by most recent first
        data = qs.order_by("-date")

# For revenue report, we calculate total deposits and sales in the given date range, then sum them up for total revenue
    elif report_type == "Revenue Report":
        # Start with all deposits and sales, then filter by date if from_date/to_date are provided
        deposits = Deposit.objects.all()
        sales = Sale.objects.all()
        # Apply date filters if provided
        if from_date:
            deposits = deposits.filter(date_registered__gte=from_date)
            sales = sales.filter(date__gte=from_date)
        if to_date:
            deposits = deposits.filter(date_registered__lte=to_date)
            sales = sales.filter(date__lte=to_date)
            # Calculate totals
            # We use aggregate to sum up the amount_paid for deposits and grand_total for sales, 
            # handling the case where there are no records (returns None) by using or 0
        data = {
            "deposits_total": deposits.aggregate(Sum("amount_paid"))["amount_paid__sum"] or 0,
            "sales_total": sales.aggregate(Sum("grand_total"))["grand_total__sum"] or 0,
        }

# For stock report, we simply fetch all stock records, but we could also apply date filters if needed
    elif report_type == "Stock Report":
        data = Stock.objects.all()

# For customer report, we annotate each participant with their total deposits and order by that amount to see who the top customers are
    elif report_type == "Customer Report":
        # Annotate each participant with the sum of their deposits and order by that total in descending order
        data = Participant.objects.annotate(
            total_deposits=Sum("deposits__amount_paid")
        ).order_by("-total_deposits")

    return render(request, "reports.html", {
        "report_type": report_type,
        "data": data,
        "from_date": request.GET.get("from_date"),
        "to_date": request.GET.get("to_date"),
    })



# Supplier registration view with error handling and activity logging
def supplier_reg(request):
    if request.method == "POST":
        payload = request.POST
        # Using a transaction to ensure atomicity - either all operations succeed or none do
        # This is important because we are creating a supplier and logging an activity, and we don't want one to succeed without the other
        # We also catch ValidationError separately to handle field-specific errors, 
        # and a general Exception catch for any other unforeseen issues
        try:
            # django's transaction.atomic() ensures that if any part of the block fails (like a validation error),
            #  the entire transaction will be rolled back, preventing partial data from being saved
            with transaction.atomic():
                supplier = Supplier.objects.create(
                    supplier_name=payload.get("supplier_name"),
                    contact_number=payload.get("contact_number"),
                    address=payload.get("address"),
                    email=payload.get("email"),
                )
# After successfully creating the supplier, we log this activity. 
# If the supplier creation fails due to validation errors, the activity log will not be created, 
# and the error will be handled in the except block.
                Activity.objects.create(
                    title=f"Supplier {supplier.supplier_name} added",
                    color="orange"
                )

                return redirect("accountssupplier")
# ValidationError is raised when model validation fails (like missing required fields or invalid formats).
        except ValidationError as e: # This will catch any validation errors raised by the Supplier model's clean() method or field validators.
            # Field-specific errors
            return render(request, "supplierReg.html", {
                "errors": e.message_dict, # This will contain a dictionary of field names to error messages, which can be displayed next to the relevant form fields in the template.
                "data": payload, # This allows us to pre-fill the form with the data the user had entered, so they don't have to retype everything after a validation error.
            })

# The general Exception catch is a safety net for any other types of errors that might occur 
# (like database errors, or unexpected issues in the code).
        except Exception as e: # This will catch any other exceptions that are not ValidationErrors, such as database errors, connection issues, or any unforeseen bugs in the code.
            # General error
            return render(request, "supplierReg.html", {
                "general_error": str(e), # This will contain a string representation of the error, which can be displayed at the top of the form as a general error message.
                "data": payload, # Again, we pass the original data back to pre-fill the form, so the user doesn't lose their input even if an unexpected error occurs.
            })

    return render(request, "supplierReg.html")


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

# This view handles recording a payment made to a supplier for a specific credit.
def pay_supplier(request, pk, slug, credit_id):
    # First, we fetch the supplier and the specific credit record using the provided IDs.
    supplier = get_object_or_404(Supplier, pk=pk, slug=slug)
    credit = get_object_or_404(SupplierCredit, id=credit_id, supplier=supplier)

# If the request method is POST, it means the form has been submitted with payment details. 
# We then extract the amount and notes from the form data.
    if request.method == "POST":
        amount = Decimal(request.POST.get("amount"))
        notes = request.POST.get("notes")

# We create a new SupplierPayment record linked to the specific credit, 
# which will automatically update the amount paid and balance in the SupplierCredit model
# (assuming the model's save() method handles this logic).
        SupplierPayment.objects.create(credit=credit, amount=amount, notes=notes)
        messages.success(request, f"Payment of UGX {amount} recorded for {supplier.supplier_name}")
        return redirect("accountssupplier")

    return render(request, "pay_supplier.html", {"credit": credit, "supplier": supplier})


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

# This view handles the deletion of a stock record. It first fetches the stock item by its primary key (ID). 
# If the request method is POST, it means the user has confirmed the deletion,
#  and we proceed to delete the record. After deletion, we log this activity and show a success message.
#  If the request method is GET, we render a confirmation page asking the user to confirm the deletion.
@permission_required('nyondogeneralhardwareapp.delete_stock', raise_exception=True)
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


# This view handles the registration of new stock items. It processes the form submission, validates the input,
#  and creates a new Stock record.
def stock_reg(request):
    if request.method == "POST":
        payload = request.POST
        # We use a try-except block to handle potential validation errors when creating the Stock record,
        try:
            sent_supplier = payload.get("supplier")
            supplier = Supplier.objects.get(id=sent_supplier)

# Before creating the stock record, we check if the selected supplier is active. 
# If the supplier is deactivated, we show an error message and redirect back to the stock registration page 
# without saving the stock record.
            # Block inactive suppliers
            if not supplier.is_active:
                messages.error(request, "This supplier is deactivated. Choose another supplier.")
                return redirect("accountsstock-reg")

# If the supplier is active, we proceed to create the Stock record with the provided details.
            stock = Stock.objects.create(
                product_name=payload.get("product_name"),
                specification=payload.get("specification"),
                supplier=supplier,  # use the Supplier object
                payment_mode=payload.get("payment_mode"),
                credit_terms=payload.get("credit_terms") if payload.get("payment_mode") == "Credit" else None,
                unit_cost=Decimal(payload.get("unit_cost")),
                unit_price=Decimal(payload.get("unit_price")),
                quantity=int(payload.get("quantity")),
                unit=payload.get("unit"),
                date_received=payload.get("date"),
            )
# After successfully creating the stock record, we log this activity. If the creation fails due to validation errors, 
# the activity log will not be created, and the error will be handled in the except block.
            Activity.objects.create(
                title=f"Stock {stock.product_name} added",
                color="orange"
            )

            return redirect("accountsstock")

# We catch ValidationError separately to handle field-specific errors, and a general Exception catch for any other unforeseen issues.
        except ValidationError as e: # This will catch any validation errors raised by the Stock model's clean() method or field validators.
            # Field-specific errors
            suppliers = Supplier.objects.filter(is_active=True)
            return render(request, "stock-reg.html", {
                "errors": e.message_dict, # This will contain a dictionary of field names to error messages, which can be displayed next to the relevant form fields in the template.
                "data": request.POST, # This allows us to pre-fill the form with the data the user had entered, so they don't have to retype everything after a validation error.
                "suppliers": suppliers
            })

        except Exception as e:
            suppliers = Supplier.objects.filter(is_active=True)
            return render(request, "stock-reg.html", {
                "general_error": str(e), # This will contain a string representation of the error, which can be displayed at the top of the form as a general error message.
                "data": request.POST,
                "suppliers": suppliers
            })

    suppliers = Supplier.objects.filter(is_active=True)
    return render(request, "stock-reg.html", {"suppliers": suppliers})

# This view displays a list of customers (participants) along with their total deposits and latest payment method.
def customer_deposit(request):
    # Fetch all participants and annotate with total deposits and latest payment method
    participants = Participant.objects.all().order_by("-registered_on")
    # We loop through each participant to calculate their total deposits and latest payment method.
    for p in participants:
        # Total deposits
        # We use aggregate to sum up the amount_paid for all deposits related to this participant.
        p.total_deposits = p.deposits.aggregate(
            # If there are no deposits, the sum will return None, so we use or 0 to default to 0 in that case.
            total=Sum("amount_paid")
        )["total"] or 0

        # Latest payment method
        # We order the deposits by date_registered in descending order and take the first one to get the latest deposit.
        latest = p.deposits.order_by("-date_registered").first()
        # If there is a latest deposit, we take its payment_method; otherwise, we use "—" to indicate no payments.
        p.latest_method = latest.payment_method if latest else "—"

    # render AFTER the loop, not inside
    return render(request, "customer-deposit.html", {"participants": participants})
     
# This view handles the deletion of a participant (customer). It first fetches the participant by its primary key (ID).     
def participant_delete(request, pk):
    participant = get_object_or_404(Participant, pk=pk)

    if request.method == "POST":
        participant.delete()
        messages.warning(request, f"Participant {participant.name} has been deleted.")
        return redirect("accountscustomer-deposit")  # back to main page

    return render(request, "participant_delete.html", {"participant": participant})

# This view handles the registration of a new customer (participant) along with their initial deposit. 
# It processes the form submission, validates the input, creates a new Participant record, 
# and then creates a related Deposit record for their first payment. 
# We also log this activity and handle any potential validation errors or general exceptions that may occur during the process.
def customer_reg(request):
    if request.method == "POST":
        # We use a try-except block to handle potential validation errors when creating the Participant and Deposit records,
        # and to catch any other unforeseen issues that might arise during the process.
        try:
            # First, we create the Participant record with the provided details from the form.
            participant = Participant.objects.create(
                name=request.POST.get("name"),
                nin=request.POST.get("nin"),
                phone=request.POST.get("phone"),
                registered_on=request.POST.get("date"),
            )

            # We then create a related Deposit record for this participant,
            #  using the participant object we just created to link the deposit to the correct participant.
            deposit = Deposit.objects.create(
                participant=participant,
                product=request.POST.get("product"),
                amount_paid=request.POST.get("amount_paid"),
                payment_method=request.POST.get("payment_method"),
                date_registered=request.POST.get("date"),
            )
# After successfully creating the participant and their initial deposit, 
# a message is displayed to confirm the successful enrollment, and we log this activity.
            messages.success(
                request,
                f"{participant.name} enrolled successfully with first deposit."
            )

            return redirect("deposit_receipt", pk=deposit.pk)

# If there are any validation errors (like missing required fields or invalid formats), 
# we catch the ValidationError and pass the specific field errors back to the template, 
# along with the original form data to pre-fill the form.
        except ValidationError as e:
            return render(request, "customer-reg.html", {
                "errors": e.message_dict,
                "data": request.POST
            })

        except Exception as e:
            return render(request, "customer-reg.html", {
                "general_error": str(e),
                "data": request.POST
            })

    return render(request, "customer-reg.html")


# This view displays the profile of a customer (participant), 
# including their total deposits, collections, and eligibility for goods based on their deposit balance.
def customer_profile(request, pk):
    participant = get_object_or_404(Participant, pk=pk)
    # Fetch all deposits and collections for this participant
    deposits = participant.deposits.order_by("-date_registered")
    total_balance = deposits.aggregate(Sum("amount_paid"))["amount_paid__sum"] or 0
    collections = participant.collections.order_by("-date_collected")

    # thresholds (unit prices)
    # We define a dictionary of products and their corresponding price thresholds.
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
    # We calculate how many units of each product the participant is eligible for based on 
    # their total deposit balance and the price thresholds defined above.
    eligibility = {}
    # We loop through each product and its price in the thresholds dictionary.
    for product, price in thresholds.items():
        # We calculate the eligibility by dividing the total balance by the price of the product,
        # but only if the total balance is greater than or equal to the price. 
        # If the total balance is less than the price, the eligibility is set to 0.
        eligibility[product] = total_balance // price if total_balance >= price else 0

# Finally, we pass all the relevant data to the template context and render the customer profile page.
    context = {
        "participant": participant,
        "deposits": deposits,
        "collections": collections,
        "total_balance": total_balance,
        "eligibility": eligibility,
    }
    return render(request, "customer_profile.html", context)


# This view handles adding a new deposit payment for an existing participant. 
# It processes the form submission, validates the input, creates a new Deposit record linked to the participant, 
# and then redirects to the receipt page for that deposit. We also log this activity.
def deposit_add_payment(request, participant_id):
    participant = get_object_or_404(Participant, pk=participant_id)
# If the request method is POST, it means the form has been submitted with the new deposit details.
#  We then create a new Deposit record linked to the participant using the provided form data.
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
        # Redirect to receipt page after saving
        return redirect("deposit_receipt", pk=deposit.pk)

    #Render the form template
    return render(request, "deposit_add_payment.html", {"participant": participant})

def goods_receipt(request, pk):
    collection = get_object_or_404(GoodsCollection, pk=pk)
    receipt = collection.receipt   #correct reverse relation
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
        # Redirect straight to final receipt
        return redirect("goods_receipt", pk=collection.pk)
        

    # Pass product and quantity to template for prefill
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

def supplier_view(request, pk, slug):
    supplier = get_object_or_404(Supplier, pk=pk, slug=slug)

    # Credits for this supplier
    credits = SupplierCredit.objects.filter(supplier=supplier).select_related("stock")

    # Totals
    total_credit = credits.aggregate(total=Sum("total_amount"))["total"] or 0
    total_paid = credits.aggregate(total=Sum("amount_paid"))["total"] or 0
    outstanding_balance = credits.aggregate(total=Sum("balance"))["total"] or 0

    # Payments for this supplier
    payments = SupplierPayment.objects.filter(credit__supplier=supplier).order_by("-payment_date")

    # Stock supplied by this supplier
    stocks = Stock.objects.filter(supplier=supplier).order_by("-date_received")

    context = {
        "supplier": supplier,
        "credits": credits,
        "payments": payments,
        "stocks": stocks,
        "total_credit": total_credit,
        "total_paid": total_paid,
        "outstanding_balance": outstanding_balance,
    }
    return render(request, "supplier_view.html", context)
    
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
