from django.shortcuts import render, redirect
from django.contrib import messages
from nyondogeneralhardwareapp.models import Stock, Supplier

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
    return render(request, 'sales.html')

def supplier(request):
    # Total suppliers
    total_suppliers = Supplier.objects.count()

    # Cash suppliers
    cash_suppliers = Supplier.objects.filter(credit_terms="Cash").count()

    # Credit suppliers (anything not Cash)
    credit_suppliers = Supplier.objects.exclude(credit_terms="Cash").count()

   
    context = {
        "total_suppliers": total_suppliers,
        "cash_suppliers": cash_suppliers,
        "credit_suppliers": credit_suppliers,
        "suppliers": Supplier.objects.all(),
        
    }
    return render(request, "supplier.html", context)
    return render(request, 'supplier.html')

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
        sent_payment_terms = payload.get("payment_terms")
        sent_credit_terms = payload.get("credit_terms") if sent_payment_terms == "Credit" else None

        Supplier.objects.create(
            supplier_name= sent_supplier_name,
            contact_number= sent_contact_number,
            address= sent_address,
            email= sent_email,
            payment_terms = sent_payment_terms,
            credit_terms= sent_credit_terms,
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
        supplier.payment_terms = request.POST.get("payment_terms")
        supplier.credit_terms = request.POST.get("credit_terms")

        # Save changes
        supplier.save()
        return redirect("accountssupplier") 


    return render(request, 'supplier-edit.html', {"supplier":supplier})

def sales_reg(request):
    return render(request, 'sales-reg.html')

def stock_edit(request):
    return render(request, 'stock-edit.html')

def stock_reg(request):
    if request.method == "POST":
        payload = request.POST
        sent_product_name = payload.get("product_name")
        sent_specification = payload.get("specification")
        sent_supplier = payload.get("supplier")
        sent_payment_mode = payload.get("payment_mode")
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
        supplier.delete()
        return redirect("accountssupplier")  # back to supplier list
    return render(request, "supplier_delete.html", {"supplier": supplier})