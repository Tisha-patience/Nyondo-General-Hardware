from django.shortcuts import render, redirect
from django.contrib import messages
from django.db.models import ProtectedError
from nyondogeneralhardwareapp.models import Stock, Supplier, Sale, SaleItem

# Create your views here.
def index(request):
    return render(request, 'index.html')

def login(request):
    
    return render(request, 'login.html')

def dashboard(request):
    context = {
        "total_deposits" : 1200000
    }
    return render(request, 'dashboard.html', context)

def sales(request):
    # Fetch all sales and their related items in one go
    sales = Sale.objects.prefetch_related("items").all()

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

def sale_view(request, pk):
    sale = get_object_or_404(Sale, pk=pk)
    return render(request, "sale_view.html", {"sale": sale})

def sale_edit(request, pk):
    sale = get_object_or_404(Sale, pk=pk)
    if request.method == "POST":
        # Manual update from form fields
        sale.customer_name = request.POST.get("customer_name")
        sale.customer_phone = request.POST.get("customer_phone")
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
    return render(request, "sale_delete.html", {"sale": sale})



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

def deactivate_supplier(request, supplier_id):
    supplier = get_object_or_404(Supplier, id=supplier_id)
    supplier.is_active = False
    supplier.save()
    messages.warning(request, f"Supplier {supplier.supplier_name} has been deactivated.")
    return redirect("accountssupplier")   # redirect back to supplier list

def activate_supplier(request, supplier_id):
    supplier = get_object_or_404(Supplier, id=supplier_id)
    supplier.is_active = True
    supplier.save()
    messages.success(request, f"Supplier {supplier.supplier_name} has been reactivated.")
    return redirect("accountssupplier")




def stock(request):
    stocks = Stock.objects.all()
    return render(request, 'stock.html', {"stocks" : stocks})

def reports(request):

    return render(request, 'reports.html')


def customer_deposit(request):
    return render(request, 'customer-deposit.html')

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

def sales_reg(request):
    
    if request.method == "POST":
        # Create Sale record
        sale = Sale.objects.create(
            customer_name=request.POST.get("customer_name"),
            customer_phone=request.POST.get("customer_phone"),
            distance_km=request.POST.get("distance_km") or 0,
        )

        # Collect multiple items
        products = request.POST.getlist("product")  # e.g. ["cement", "ironbars", "nails"]
        specs = request.POST.getlist("specification") # e.g. ["CEM II N", "10mm", "Inch 4"]
        quantities = request.POST.getlist("quantity") # e.g. ["10", "5", "2"]
        units = request.POST.getlist("unit") # e.g. ["bags", "pieces", "kg"]
        unit_prices = request.POST.getlist("unit_price") # e.g. ["30000", "50000", "2000"]

        # Loop through items
        for i in range(len(products)):
            qty = int(quantities[i])
            price = float(unit_prices[i])
            total = qty * price

            SaleItem.objects.create(
                sale=sale,
                product=products[i],
                specification=specs[i],
                quantity=qty,
                unit=units[i],
                unit_price=price,
                total_price=total,
            )

        # Update transport + grand total
        sale.save()

        return redirect("sale_receipt", pk=sale.pk)

   
    return render(request, 'sales-reg.html')

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

def receipt_form(request):
    return render(request, 'receiptForm.html')

def deposit_form(request):
    if request.method == "POST":
        payload = request.POST
        
    return render(request, 'depositForm.html')

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