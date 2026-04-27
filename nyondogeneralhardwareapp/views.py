from django.shortcuts import render

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
    return render(request, 'supplier.html')

def stock(request):
    return render(request, 'stock.html')

def reports(request):
    return render(request, 'reports.html')


def customer_deposit(request):
    return render(request, 'customer-deposit.html')

def supplier_reg(request):
    return render(request, 'supplierReg.html')

def back(request):
    return render(request, 'index.html')

def receipt(request):
    return render(request, 'receipt.html')

def supplier_edit(request):
    return render(request, 'supplier-edit.html')

def sales_reg(request):
    return render(request, 'sales-reg.html')

def stock_edit(request):
    return render(request, 'stock-edit.html')

def stock_reg(request):
    return render(request, 'stock-reg.html')

def receipt_form(request):
    return render(request, 'receiptForm.html')

def deposit_form(request):
    if request.method == "POST":
        payload = request.POST
        
    return render(request, 'depositForm.html')


