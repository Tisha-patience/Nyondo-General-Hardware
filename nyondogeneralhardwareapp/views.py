from django.shortcuts import render

# Create your views here.
def index(request):
    return render(request, 'index.html')

def login(request):
    return render(request, 'login.html')

def dashboard(request):
    return render(request, 'dashboard.html')

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


