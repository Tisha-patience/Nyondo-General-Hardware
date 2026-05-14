from django.utils import timezone

def current_date(request):
    return {
        "today": timezone.now().date()
    }

def user_role(request):
    if not request.user.is_authenticated:
        return {"role": "Guest"}

    if request.user.is_superuser:
        role = "System Admin"
    elif request.user.groups.filter(name="Store Manager").exists():
        role = "Store Manager"
    elif request.user.groups.filter(name="Sales Attendant").exists():
        role = "Sales Attendant"
    else:
        role = "User"

    return {"role": role}
