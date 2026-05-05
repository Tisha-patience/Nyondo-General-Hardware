"""
URL configuration for nyondostockproject project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from nyondogeneralhardwareapp import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.index, name='index'),
    path('login/', views.login, name='login'),
    # Central Accounts/Admin hub
    path('accounts/dashboard/', views.dashboard, name='accountsdashboard'),
    path('accounts/sales/', views.sales, name='accountssales'),
    path("sales/<int:pk>/", views.sale_view, name="sale_view"),
    path("sales/<int:pk>/edit/", views.sale_edit, name="sale_edit"),
    path("sales/<int:pk>/delete/", views.sale_delete, name="sale_delete"),
    path('accounts/supplier/', views.supplier, name='accountssupplier'),
    # Supplier actions with ID + slug
    path("supplier/<int:pk>-<slug:slug>/deactivate/", views.deactivate_supplier, name="deactivate_supplier"),
    path("supplier/<int:pk>-<slug:slug>/activate/", views.activate_supplier, name="activate_supplier"),
    path("supplier/<int:pk>-<slug:slug>/view/", views.supplier_view, name="supplier_view"),
    path("supplier/<int:pk>-<slug:slug>/edit/", views.supplier_edit, name="supplier_edit"),
    path("supplier/<int:pk>-<slug:slug>/delete/", views.supplier_delete, name="supplier_delete"),
    path('accounts/stock/', views.stock, name='accountsstock'),
    path("stock/<int:pk>/", views.stock_view, name="stock_view"),
    path("stock/<int:pk>/edit/", views.stock_edit, name="stock_edit"),
    path("stock/<int:pk>/delete/", views.stock_delete, name="stock_delete"),
    path('accounts/reports/', views.reports, name='accountsreports'),
    path('accounts/customer-deposit/', views.customer_deposit, name='accountscustomer-deposit'),
    path('accounts/supplierReg/', views.supplier_reg, name='accountssupplierReg'),
    path('accounts/receipt/', views.receipt, name='accountsreceipt'),
    path('accounts/supplier-edit/', views.supplier_edit, name='accountssupplier-edit'),
    path('accounts/sales-reg/', views.sales_reg, name='accountssales-reg'),
    path('accounts/stock-edit/', views.stock_edit, name='accountsstock-edit'),
    path('accounts/stock-reg/', views.stock_reg, name='accountsstock-reg'),
    path('accounts/receiptForm/', views.receipt_form, name='accountsreceiptForm'),
    path('accounts/depositForm/', views.deposit_form, name='accountsdepositForm'),
   
    
]
