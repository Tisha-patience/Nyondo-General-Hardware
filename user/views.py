from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from .forms import UserRegistrationForm

# Create your views here.

def is_admin(user):
    return user.is_superuser or user.groups.filter(name="Store Manager").exists()

@login_required
@user_passes_test(is_admin)
def register_user(request):
    if request.method == "POST":
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            role = form.cleaned_data.get("role")
            user.groups.add(role)
            messages.success(request, f"User {user.username} registered successfully!")
            return redirect("accountsdashboard")
    else:
        form = UserRegistrationForm()
    return render(request, "register.html", {"form": form})