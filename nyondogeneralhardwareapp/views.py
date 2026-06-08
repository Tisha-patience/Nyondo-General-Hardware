from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils.timezone import now
from django.db.models import Sum, Count, F
from django.utils.dateparse import parse_date
from reportlab.lib.pagesizes import A4
from django.db.models import Sum
from django.db.models import ProtectedError
from django.db import transaction
from decimal import Decimal, InvalidOperation
from django.core.exceptions import ValidationError
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test,permission_required
from nyondogeneralhardwareapp.models import Stock, Supplier, Sale, SaleItem, Deposit, Participant, GoodsCollection, Activity, SupplierCredit, SupplierPayment

# Create your views here.

# The index view simply renders the homepage of the application. 
# It doesn't require any special permissions or data, so it's accessible to all users.
def index(request):
    return render(request, 'index.html')

# The login_view handles user authentication. It checks if the request method is POST (indicating a form submission),
def login_view(request):
    context = {"errors": {}, "data": {"username": ""}}
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        context["data"]["username"] = username

        if not username:
            context["errors"]["username"] = ["Username is required."]
        if not password:
            context["errors"]["password"] = ["Password is required."]

        if context["errors"]:
            return render(request, "login.html", context)

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect("login_redirect")
        else:
            context["errors"]["general"] = ["Invalid username or password."]
            return render(request, "login.html", context)

    return render(request, "login.html", context)


# This view checks the role of the logged-in user and redirects them to the appropriate dashboard based on their permissions.
def login_redirect(request):
    # We check if the user is a superuser, store manager, or sales attendant by checking their group memberships and permissions.
    user = request.user
    if user.is_superuser:
        return redirect("accountsdashboard")
    elif user.groups.filter(name="Store Manager").exists():
        return redirect("manager_dashboard")
    elif user.groups.filter(name="Sales Attendant").exists():
        return redirect("attendant_dashboard")
    else:
        return redirect("index")
    
def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out successfully.")
    return redirect("login") 

# The dashboard view is restricted to superusers only. 
# It aggregates various statistics about participants, sales, deposits, stock, and suppliers
#  to display on the admin dashboard.
@login_required
@user_passes_test(lambda u: u.is_superuser)
def dashboard(request):
    # All registered participants
    # We count the total number of participants in the system, 
    # which represents the total number of customers who have registered.
    participant_count = Participant.objects.count()

    # Unique customers from sales (by phone)
    # We fetch the distinct customer phone numbers from the Sale model to count how many unique customers have made purchases.
    sale_customers = Sale.objects.values_list("customer_phone", flat=True).distinct()
    sale_customer_count = sale_customers.count()

    # Combine both sets (avoid double-counting)
    # We take the unique NINs from the Participant model and the unique customer phone numbers from the Sale model,
    # combine them using union to get a set of all unique customers, and then count 
    # the total number of unique customers across both models.
    total_customers = Participant.objects.values_list("nin", flat=True).union(
        Sale.objects.values_list("customer_phone", flat=True)
    ).count()
# We calculate the total revenue by summing up all deposits and sales.
    deposits_total = Deposit.objects.aggregate(Sum("amount_paid"))["amount_paid__sum"] or 0
    sales_total = Sale.objects.aggregate(Sum("grand_total"))["grand_total__sum"] or 0
    total_revenue = deposits_total + sales_total
# We count the total number of stock items and suppliers in the system to display on the dashboard.
    stock_items = Stock.objects.count()
    suppliers = Supplier.objects.count()

    # Get participants with their total deposits
    participants = Participant.objects.all()
    for p in participants:
        p.total_deposits = p.deposits.aggregate(Sum("amount_paid"))["amount_paid__sum"] or 0
# We fetch the most recent activities (like sales, stock updates, etc.) to display on the dashboard activity feed.
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

# This view is for sales attendants and displays key metrics relevant to their role, 
# such as today's sales, receipts issued, customers served, low stock items, recent sales, and all stock items.
def is_attendant(user):
    return user.groups.filter(name="Sales Attendant").exists()
# The attendant_dashboard view is decorated with @login_required to ensure that only authenticated users can access it,
# and @user_passes_test with the is_attendant function to restrict access to users who are in the "Sales Attendant" group.
#  It aggregates various statistics about today's sales, receipts, customers, low stock items, and recent sales 
# to display on the attendant dashboard.
@login_required
@user_passes_test(is_attendant) # Only users in the "Sales Attendant" group can access this view
def attendant_dashboard(request):
    today = now().date() # We get the current date to filter today's sales and activities.

    # Today's sales total
    # We filter the Sale records to get only those that were made today, 
    # then we aggregate the sum of the grand_total field to get the total sales amount for today.
    #  If there are no sales, we default to 0.
    today_sales = Sale.objects.filter(date__date=today).aggregate(
        Sum("grand_total")
    )["grand_total__sum"] or 0

    # Receipts issued today (GoodsCollection with receipts)
    # We filter the GoodsCollection records to get only those that were collected today and have a receipt,
    # then we count the number of such records.
    receipts_count = GoodsCollection.objects.filter(
        date_collected__date=today,
        receipt__isnull=False
    ).count()

    # Customers served today
    # We filter the Sale records to get only those that were made today,
    # then we count the distinct customer names.
    customers_today = Sale.objects.filter(date__date=today).values("customer_name").distinct().count()

    # Low stock count
    # We filter the Stock records to get only those that have a quantity less than or equal to 10 but greater than 0
    #  (indicating low stock but not out of stock),
    low_stock = Stock.objects.filter(quantity__lte=10, quantity__gt=0).count()

    # Low stock items list
    # We fetch the actual Stock records that are low in stock (quantity <= 10 and > 0) to display on the dashboard.
    low_stock_items = Stock.objects.filter(quantity__lte=10, quantity__gt=0)

    # Recent sales
    # We fetch the most recent 10 sales records, ordered by date in descending order, to display on the dashboard.
    sales = Sale.objects.order_by("-date")[:10]

    # All stock
    # We fetch all Stock records to display on the dashboard, which may be used for quick reference or management by the sales attendant.
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


# The manager_dashboard view is decorated with @login_required to ensure that only authenticated users can access it, 
# and @user_passes_test with the is_manager function to restrict access to users who are in the "Store Manager" group or are superusers.
def is_manager(user):
    return user.groups.filter(name="Store Manager").exists() or user.is_superuser
# The manager_dashboard view aggregates various statistics about stock levels, sales, suppliers, and recent activities 
# to display on the store manager dashboard. It provides a comprehensive overview of the store's operations for managerial oversight.
@login_required
@user_passes_test(is_manager)
def manager_dashboard(request):
    today = now().date()

    # Summary cards
    # We calculate the total quantity of stock available by summing up the quantity field across all Stock records.
    # We also calculate the total stock value by summing up the product of quantity and unit_price for all Stock records.
    total_quantity = Stock.objects.aggregate(Sum("quantity"))["quantity__sum"] or 0
    total_stock_value = Stock.objects.aggregate(
        total_value=Sum(F("quantity") * F("unit_price")) # We use F expressions to calculate the total value for each stock item by multiplying quantity and unit_price, and then we sum these values across all stock items to get the total stock value.
    )["total_value"] or 0
    credit_supplies = Stock.objects.filter(payment_mode="Credit").count() # We count how many stock items were supplied on credit by filtering the Stock records where payment_mode is "Credit".

# We calculate the profit margin by taking the total sales amount and subtracting the total cost of the stock.
    sales_total = Sale.objects.aggregate(Sum("grand_total"))["grand_total__sum"] or 0
    stock_cost_total = Stock.objects.aggregate(
        total_cost=Sum(F("quantity") * F("unit_cost")) # Similar to total_stock_value, but we multiply quantity by unit_cost to get the total cost of the stock, and then sum it up across all stock items.
    )["total_cost"] or 0
    profit_margin = sales_total - (stock_cost_total or 0)

    # Stock levels
    # We categorize stock items into three groups: low stock (quantity <= 10 and > 0), out of stock (quantity = 0), 
    # and available (quantity > 10).
    low_stock_items = Stock.objects.filter(quantity__lte=10, quantity__gt=0)
    out_of_stock_items = Stock.objects.filter(quantity=0)
    available_items = Stock.objects.filter(quantity__gt=10)

    # Editable stock table
    # We fetch all Stock records to display in an editable table on the dashboard, 
    # allowing the manager to quickly view and manage stock items.
    stocks = Stock.objects.all()

    # Recent suppliers
    # We fetch the most recent 5 suppliers, ordered by their ID in descending order, to display on the dashboard.
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

# The logout view simply displays a message indicating that the user has been logged out successfully 
# and then redirects them to the login page.



# This view displays a list of all sales along with summary statistics such as total number of sales and total revenue generated.
@login_required
def sales(request):
    # Fetch all sales and their related items in one go
    # We order the sales by date in descending order to show the most recent sales first.
    sales = Sale.objects.all().order_by('-date')

    # Total number of sales
    # We simply count the number of Sale records to get the total number of sales made.
    total_sales = sales.count()

    # Total revenue = sum of grand totals (not sale.total_price, since that's per item)
    # We sum up the grand_total field for all Sale records to calculate the total revenue generated from sales.
    total_revenue = sum(sale.grand_total for sale in sales)

    context = {
        "sales": sales,
        "total_sales": total_sales,
        "total_revenue": total_revenue,
    }
    return render(request, "sales.html", context)

# This view handles the registration of a new sale. 
# It processes the form submission, validates the input, creates a new Sale record along with related SaleItem records
#  for each product sold, updates stock quantities, and logs the activity. 
# It also includes error handling to manage validation errors and other exceptions that may occur during the process.
@login_required
def sales_reg(request):
    if request.method == "POST":
        # We use a try-except block to handle potential validation errors when creating the Sale and SaleItem records,
        # as well as any other unforeseen exceptions that may occur during the process. 
        # This ensures that we can provide meaningful feedback to the user and maintain data integrity.
        try:
            data = request.POST
            errors = {}

            customer_name = data.get("customer_name", "").strip()
            customer_phone = data.get("customer_phone", "").strip()
            distance_str = data.get("distance_km", "").strip()
            stock_ids = data.getlist("stock_id")
            quantities = data.getlist("quantity")
            units = data.getlist("unit")
            unit_prices = data.getlist("unit_price")

            if not customer_name:
                errors["customer_name"] = ["Customer name is required."]

            if not customer_phone:
                errors["customer_phone"] = ["Phone number is required."]
            
            if distance_str == "":
                errors["distance_km"] = ["Delivery distance is required."]
            else:
                try:
                    distance_km = int(distance_str)
                    if distance_km < 0:
                        errors["distance_km"] = ["Delivery distance cannot be negative."]
                except (ValueError, TypeError):
                    errors["distance_km"] = ["Delivery distance must be a number."]

            if not stock_ids:
                errors["stock_id"] = ["Product selection is required."]
            else:
                for idx, stock_id in enumerate(stock_ids):
                    if not stock_id or not stock_id.strip():
                        errors.setdefault("stock_id", []).append(f"Product selection is required for item {idx + 1}.")
                    elif not stock_id.isdigit():
                        errors.setdefault("stock_id", []).append(f"Invalid product selected for item {idx + 1}.")

            if not quantities:
                errors["quantity"] = ["Quantity is required."]
            else:
                for idx, qty_str in enumerate(quantities):
                    qty_value = qty_str.strip()
                    if qty_value == "":
                        errors.setdefault("quantity", []).append(f"Quantity is required for item {idx + 1}.")
                    else:
                        try:
                            qty = int(qty_value)
                            if qty <= 0:
                                errors.setdefault("quantity", []).append(f"Quantity must be greater than zero for item {idx + 1}.")
                        except (ValueError, TypeError):
                            errors.setdefault("quantity", []).append(f"Quantity must be a number for item {idx + 1}.")

            if not units:
                errors["unit"] = ["Unit is required."]
            else:
                for idx, unit in enumerate(units):
                    if not unit or not unit.strip():
                        errors.setdefault("unit", []).append(f"Unit is required for item {idx + 1}.")

            if not unit_prices:
                errors["unit_price"] = ["Unit price is required."]
            else:
                for idx, price_str in enumerate(unit_prices):
                    price_value = price_str.strip()
                    if price_value == "":
                        errors.setdefault("unit_price", []).append(f"Unit price is required for item {idx + 1}.")
                    else:
                        try:
                            price = float(price_value)
                            if price < 0:
                                errors.setdefault("unit_price", []).append(f"Unit price cannot be negative for item {idx + 1}.")
                        except (ValueError, TypeError):
                            errors.setdefault("unit_price", []).append(f"Unit price must be a number for item {idx + 1}.")

            if stock_ids and quantities and len(stock_ids) != len(quantities):
                errors.setdefault("general", []).append("Each item must include a product and quantity.")
            if stock_ids and units and len(stock_ids) != len(units):
                errors.setdefault("general", []).append("Each item must include a product and unit.")
            if stock_ids and unit_prices and len(stock_ids) != len(unit_prices):
                errors.setdefault("general", []).append("Each item must include a product and unit price.")

            if errors:
                raise ValidationError(errors)

            distance_km = int(distance_str) if distance_str else 0

            with transaction.atomic():
                sale = Sale.objects.create(
                    customer_name=customer_name,
                    customer_phone=customer_phone,
                    distance_km=distance_km
                )
# After successfully creating the Sale record, we log this activity. If the creation fails due to validation errors,
# the activity log will not be created, and the error will be handled in the except block.
                Activity.objects.create(
                    title=f"New sale recorded (UGX {sale.grand_total})",
                    color="blue"
                )

                # Collect multiple items
                # We get the list of stock IDs, quantities, units, and unit prices from the form data.
                # The form is designed to allow multiple items to be sold in one transaction, 
                # so we use getlist to retrieve all values for these fields.
                stock_ids = data.getlist("stock_id")
                quantities = data.getlist("quantity")
                units = data.getlist("unit")
                unit_prices = data.getlist("unit_price")

# We loop through each item in the sale, create a SaleItem record for it, and update the corresponding Stock quantity.
# We also perform a safety check to prevent overselling by ensuring that the stock quantity is sufficient for the requested quantity.
                for i in range(len(stock_ids)):
                    stock_item = get_object_or_404(Stock, pk=stock_ids[i])
                    try:
                        qty = int(quantities[i])
                    except (ValueError, TypeError):
                        raise ValidationError({"quantity": ["Quantity must be a number."]})
                    price = float(stock_item.unit_price)
                    total = qty * price

                    #Safety check: prevent overselling
                    # Before creating the SaleItem record and updating the stock quantity, 
                    # we check if the requested quantity (qty) exceeds the available stock quantity (stock_item.quantity).
                    #  If it does, we raise a ValidationError with a message indicating that there is not enough stock for that product.
                    #  This prevents the system from allowing sales that cannot be fulfilled due to insufficient stock.
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

                return redirect("sale_receipt", pk=sale.pk)
# If the creation of the Sale record fails due to validation errors, we catch the ValidationError and pass it back to the template.
        except ValidationError as e:
            # Pass field-specific errors back
            stocks = Stock.objects.all()
            return render(request, "sales-reg.html", {
                "errors": e.message_dict, # e.message_dict contains field-specific validation errors
                "data": request.POST, # Pass the form data back
                "stocks": stocks
            })
# If the creation of the Sale record fails for any other reason, we catch the Exception and pass it back to the template.
        except Exception as e:
            # Pass general error back
            stocks = Stock.objects.all()
            return render(request, "sales-reg.html", {
                "general_error": str(e), # Pass the general error message
                "data": request.POST, # Pass the form data back
                "stocks": stocks
            })

    stocks = Stock.objects.all()
    return render(request, "sales-reg.html", {"stocks": stocks})
    
@login_required
def sale_view(request, pk):
    sale = get_object_or_404(Sale, pk=pk)
    return render(request, "sale_view.html", {"sale": sale})

# We use the login_required decorator to ensure that only logged-in users can access this view.
# This prevents unauthenticated users from accessing the view and potentially accessing sensitive data or functionality.
@login_required
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

# We use the login_required and permission_required decorators to ensure that only users with the 'delete_sale' permission can access this view.
@login_required
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

@login_required
@user_passes_test(lambda u: u.is_superuser)
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



@login_required
@user_passes_test(is_manager)
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
@login_required
@user_passes_test(lambda u: u.is_superuser)
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
@login_required
@user_passes_test(lambda u: u.is_superuser)
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
@login_required
@user_passes_test(lambda u: u.is_superuser)
def supplier_reg(request):
    if request.method == "POST":
        payload = request.POST
        try:
            errors = {}
            supplier_name = payload.get("supplier_name", "").strip()
            contact_number = payload.get("contact_number", "").strip()
            email = payload.get("email", "").strip()
            address = payload.get("address", "").strip()

            if not supplier_name:
                errors["supplier_name"] = ["Supplier name is required."]
            if not contact_number:
                errors["contact_number"] = ["Contact number is required."]
            if not email:
                errors["email"] = ["Email is required."]
            elif "@" not in email or "." not in email:
                errors["email"] = ["Enter a valid email address."]
            if not address:
                errors["address"] = ["Address is required."]

            if errors:
                raise ValidationError(errors)

            with transaction.atomic():
                supplier = Supplier.objects.create(
                    supplier_name=supplier_name,
                    contact_number=contact_number,
                    address=address,
                    email=email,
                )
# After successfully creating the supplier, we log this activity. 
# If the supplier creation fails due to validation errors, the activity log will not be created, 
# and the error will be handled in the except block.
                Activity.objects.create(
                    title=f"Supplier {supplier.supplier_name} added",
                    color="orange"
                )

                return redirect("accountssupplier")
        except ValidationError as e:
            return render(request, "supplierReg.html", {
                "errors": e.message_dict,
                "data": payload,
            })
        except Exception as e:
            return render(request, "supplierReg.html", {
                "general_error": str(e),
                "data": payload,
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

    if request.method == "POST":
        data = request.POST
        errors = {}
        amount_str = data.get("amount", "").strip()
        notes = data.get("notes", "").strip()

        if amount_str == "":
            errors["amount"] = ["Payment amount is required."]
        else:
            try:
                amount = Decimal(amount_str)
                if amount <= 0:
                    errors["amount"] = ["Payment amount must be greater than zero."]
                elif amount > credit.balance:
                    errors["amount"] = ["Payment amount cannot exceed the remaining balance."]
            except (ValueError, TypeError, InvalidOperation):
                errors["amount"] = ["Payment amount must be a number."]

        if errors:
            return render(request, "pay_supplier.html", {
                "credit": credit,
                "supplier": supplier,
                "errors": errors,
                "data": data,
            })

        SupplierPayment.objects.create(credit=credit, amount=amount, notes=notes)
        messages.success(request, f"Payment of UGX {amount} recorded for {supplier.supplier_name}")
        return redirect("accountssupplier")

    return render(request, "pay_supplier.html", {"credit": credit, "supplier": supplier, "data": {}})


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
@login_required
@user_passes_test(is_manager)
def stock_reg(request):
    if request.method == "POST":
        payload = request.POST
        try:
            errors = {}
            product_name = payload.get("product_name", "").strip()
            specification = payload.get("specification", "").strip()
            supplier_id = payload.get("supplier", "").strip()
            payment_mode = payload.get("payment_mode", "").strip()
            credit_terms = payload.get("credit_terms", "").strip()
            unit_cost_str = payload.get("unit_cost", "").strip()
            unit_price_str = payload.get("unit_price", "").strip()
            quantity_str = payload.get("quantity", "").strip()
            unit = payload.get("unit", "").strip()
            date_received = payload.get("date", "").strip()

            if not product_name:
                errors["product_name"] = ["Product name is required."]
            if not specification:
                errors["specification"] = ["Specification is required."]

            supplier = None
            if not supplier_id:
                errors["supplier"] = ["Supplier is required."]
            else:
                if not supplier_id.isdigit():
                    errors.setdefault("supplier", []).append("Invalid supplier selected.")
                else:
                    try:
                        supplier = Supplier.objects.get(id=supplier_id)
                        if not supplier.is_active:
                            errors.setdefault("supplier", []).append("This supplier is deactivated. Choose another supplier.")
                    except Supplier.DoesNotExist:
                        errors.setdefault("supplier", []).append("Supplier not found.")

            if not payment_mode:
                errors["payment_mode"] = ["Mode of payment is required."]
            elif payment_mode not in ["Cash", "Credit"]:
                errors["payment_mode"] = ["Mode of payment must be Cash or Credit."]

            if payment_mode == "Credit" and not credit_terms:
                errors["credit_terms"] = ["Credit terms are required when payment mode is Credit."]

            if unit_cost_str == "":
                errors["unit_cost"] = ["Unit cost is required."]
            else:
                try:
                    unit_cost = Decimal(unit_cost_str)
                    if unit_cost < 0:
                        errors["unit_cost"] = ["Unit cost cannot be negative."]
                except (InvalidOperation, ValueError, TypeError):
                    errors["unit_cost"] = ["Unit cost must be a number."]

            if unit_price_str == "":
                errors["unit_price"] = ["Unit price is required."]
            else:
                try:
                    unit_price = Decimal(unit_price_str)
                    if unit_price < 0:
                        errors["unit_price"] = ["Unit price cannot be negative."]
                except (InvalidOperation, ValueError, TypeError):
                    errors["unit_price"] = ["Unit price must be a number."]

            if quantity_str == "":
                errors["quantity"] = ["Quantity is required."]
            else:
                try:
                    quantity = int(quantity_str)
                    if quantity <= 0:
                        errors["quantity"] = ["Quantity must be greater than zero."]
                except (ValueError, TypeError):
                    errors["quantity"] = ["Quantity must be a number."]

            if not unit:
                errors["unit"] = ["Unit is required."]
            if not date_received:
                errors["date"] = ["Date received is required."]

            if errors:
                raise ValidationError(errors)

            stock = Stock.objects.create(
                product_name=product_name,
                specification=specification,
                supplier=supplier,
                payment_mode=payment_mode,
                credit_terms=credit_terms if payment_mode == "Credit" else None,
                unit_cost=unit_cost,
                unit_price=unit_price,
                quantity=quantity,
                unit=unit,
                date_received=date_received,
            )
# After successfully creating the stock record, we log this activity. If the creation fails due to validation errors, 
# the activity log will not be created, and the error will be handled in the except block.
            Activity.objects.create(
                title=f"Stock {stock.product_name} added",
                color="orange"
            )

            return redirect("accountsstock")

        except ValidationError as e:
            suppliers = Supplier.objects.filter(is_active=True)
            return render(request, "stock-reg.html", {
                "errors": e.message_dict,
                "data": request.POST,
                "suppliers": suppliers
            })

        except Exception as e:
            suppliers = Supplier.objects.filter(is_active=True)
            return render(request, "stock-reg.html", {
                "general_error": str(e),
                "data": request.POST,
                "suppliers": suppliers
            })

    suppliers = Supplier.objects.filter(is_active=True)
    return render(request, "stock-reg.html", {"suppliers": suppliers})

# This view displays a list of customers (participants) along with their total deposits and latest payment method.
@login_required
@user_passes_test(lambda u: u.is_superuser)
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

@login_required
@user_passes_test(lambda u: u.is_superuser)
def customer_reg(request):
    if request.method == "POST":
        # We wrap the entire processing logic in a try block to catch any potential exceptions.
        try:
            # We start by initializing an empty dictionary called errors to collect
            #  any validation errors that may occur during the processing of the form data.
            # We then extract the form data from the POST request and perform validation checks on each field. 
            # If any validation fails, we add an appropriate error message to the errors dictionary.
            errors = {}
            data = request.POST
            # We use the get method with a default empty string and strip to ensure we have clean input for validation.
            # The strip method is used to remove leading and trailing whitespace from the input strings.
            # We validate that the name, NIN, phone number, product, amount paid, payment method, and date 
            # are all provided and in the correct format.
            name = data.get("name", "").strip()
            nin = data.get("nin", "").strip()
            phone = data.get("phone", "").strip()
            product = data.get("product", "").strip()
            amount_paid_str = data.get("amount_paid", "").strip()
            payment_method = data.get("payment_method", "").strip()
            date_registered = data.get("date", "").strip()

            if not name:
                errors["name"] = ["Full name is required."]
            if not nin:
                errors["nin"] = ["NIN is required."]
            if not phone:
                errors["phone"] = ["Phone number is required."]
            
            if not product:
                errors["product"] = ["Product is required."]
            elif product not in ["cement", "ironSheets", "bars"]:
                errors["product"] = ["Choose a valid product."]

            if amount_paid_str == "":
                errors["amount_paid"] = ["Amount paid is required."]
            else:
                try:
                    amount_paid = Decimal(amount_paid_str)
                    if amount_paid <= 0:
                        errors["amount_paid"] = ["Amount paid must be greater than zero."]
                except (InvalidOperation, ValueError, TypeError):
                    errors["amount_paid"] = ["Amount paid must be a number."]

            if not payment_method:
                errors["payment_method"] = ["Payment method is required."]
            elif payment_method not in ["cash", "mobile"]:
                errors["payment_method"] = ["Choose a valid payment method."]

            if not date_registered:
                errors["date"] = ["Date registered is required."]

            if errors:
                raise ValidationError(errors)

            participant = Participant.objects.create(
                name=name,
                nin=nin,
                phone=phone,
            )

            deposit = Deposit.objects.create(
                participant=participant,
                product=product,
                amount_paid=amount_paid,
                payment_method=payment_method,
                date_registered=date_registered,
            )

            messages.success(
                request,
                f"{participant.name} enrolled successfully with first deposit."
            )

            return redirect("deposit_receipt", pk=deposit.pk)

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
@login_required
def customer_profile(request, pk):
    participant = get_object_or_404(Participant, pk=pk)
    # Fetch all deposits and collections for this participant
    deposits = participant.deposits.order_by("-date_registered")
    total_balance = deposits.aggregate(Sum("amount_paid"))["amount_paid__sum"] or 0
    collections = participant.collections.order_by("-date_collected")


    # eligibility calculation
    # We calculate how many units of each product the participant is eligible for based on 
    # their total deposit balance and the price thresholds defined above.
     # eligibility calculation using Stock objects
    eligibility = {}
    for stock in Stock.objects.all():
        # eligible quantity = balance // unit_price
        eligible_qty = total_balance // stock.unit_price if total_balance >= stock.unit_price else 0
        eligibility[stock] = eligible_qty   # store Stock object as key

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
    if request.method == "POST":
        data = request.POST
        errors = {}
        product = data.get("product", "").strip()
        amount_paid_str = data.get("amount_paid", "").strip()
        payment_method = data.get("payment_method", "").strip()
        date_registered = data.get("date_registered", "").strip()

        if not product:
            errors["product"] = ["Product is required."]
        elif product not in ["cement", "ironSheets", "bars"]:
            errors["product"] = ["Select a valid product."]

        if amount_paid_str == "":
            errors["amount_paid"] = ["Amount paid is required."]
        else:
            try:
                amount_paid = Decimal(amount_paid_str)
                if amount_paid <= 0:
                    errors["amount_paid"] = ["Amount paid must be greater than zero."]
            except (ValueError, TypeError, InvalidOperation):
                errors["amount_paid"] = ["Amount paid must be a number."]

        if not payment_method:
            errors["payment_method"] = ["Payment method is required."]
        elif payment_method not in ["cash", "mobile"]:
            errors["payment_method"] = ["Select a valid payment method."]

        if not date_registered:
            errors["date_registered"] = ["Date registered is required."]

        if errors:
            return render(request, "deposit_add_payment.html", {
                "participant": participant,
                "errors": errors,
                "data": data,
            })

        deposit = Deposit.objects.create(
            participant=participant,
            product=product,
            amount_paid=amount_paid,
            payment_method=payment_method,
            date_registered=date_registered,
        )
        Activity.objects.create(
            title=f"Deposit added for {participant.name}",
            color="green"
        )
        return redirect("deposit_receipt", pk=deposit.pk)

    return render(request, "deposit_add_payment.html", {"participant": participant, "data": {}})

def goods_receipt(request, pk):
    collection = get_object_or_404(GoodsCollection, pk=pk)
    receipt = collection.receipt   #correct reverse relation
    return render(request, "goods_receipt.html", {
        "collection": collection,
        "receipt": receipt,
    })

@login_required
def pick_goods(request, participant_id, stock_id=None, quantity=None):
    participant = get_object_or_404(Participant, pk=participant_id)
    stock = get_object_or_404(Stock, pk=stock_id)

    # Calculate current balance
    current_balance = participant.deposits.aggregate(Sum("amount_paid"))["amount_paid__sum"] or 0

    if request.method == "POST":
        try:
            qty = int(request.POST.get("quantity"))
            if qty <= 0:
                messages.error(request, "Quantity must be greater than zero.")
                return render(
                    request,
                    "goodsCollection_form.html",
                    {"participant": participant, "stock": stock, "quantity": quantity, "current_balance": current_balance},
                )
        except (ValueError, TypeError):
            messages.error(request, "Invalid quantity entered.")
            return render(
                request,
                "goodsCollection_form.html",
                {"participant": participant, "stock": stock, "quantity": quantity, "current_balance": current_balance},
            )

        total_price = stock.unit_price * qty

        # Check if participant has sufficient balance
        if current_balance < total_price:
            remaining_needed = total_price - current_balance
            messages.error(
                request,
                f"Insufficient balance. Current balance: UGX {current_balance}. "
                f"Amount needed for {qty} units: UGX {total_price}. "
                f"Additional deposit required: UGX {remaining_needed}."
            )
            return render(
                request,
                "goodsCollection_form.html",
                {"participant": participant, "stock": stock, "quantity": quantity, "current_balance": current_balance},
            )

        # Record goods collection
        collection = GoodsCollection.objects.create(
            participant=participant,
            stock=stock,
            quantity=qty,
        )

        # Deduct from balance by creating a negative deposit
        deduction = Deposit.objects.create(
            participant=participant,
            product=stock.product_name,
            amount_paid=-total_price,
            payment_method="deduction"
        )

        # Log activity
        Activity.objects.create(
            title=f"Goods collection: {qty} units of {stock.product_name} for {participant.name} (Balance reduced by UGX {total_price})",
            color="blue"
        )

        # Calculate new balance after deduction
        new_balance = participant.deposits.aggregate(Sum("amount_paid"))["amount_paid__sum"] or 0
        messages.success(
            request,
            f"Goods picked successfully! Previous balance: UGX {current_balance}. "
            f"Deducted: UGX {total_price}. New balance: UGX {new_balance}."
        )

        return redirect("goods_receipt", pk=collection.pk)

    return render(
        request,
        "goodsCollection_form.html",
        {"participant": participant, "stock": stock, "quantity": quantity, "current_balance": current_balance},
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

@login_required
@user_passes_test(lambda u: u.is_superuser)
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
