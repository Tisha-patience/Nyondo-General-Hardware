from django.utils import timezone

def current_date(request):
    return {
        "today": timezone.now().date()
    }
