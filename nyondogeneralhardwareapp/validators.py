import re
from django.core.exceptions import ValidationError

def validate_phone_number(value):
    # Must start with +256 and then 9 digits (total length 13)
    pattern = r'^\+256\d{9}$'
    if not re.match(pattern, value):
        raise ValidationError('Phone number must start with +256 and contain 9 digits (e.g. +256760752349).')
    
def validate_ugandan_national_id(national_id):
    # Male IDs must start with CM, Female IDs must start with CF
    if national_id.startswith("CM"):
        pattern = r'^CM[0-9A-Z]{12}$'  # CM + 12 characters = 14 total
        if not re.match(pattern, national_id):
            raise ValidationError(
                'Male National IDs must start with "CM" followed by 12 alphanumeric characters.'
            )
    elif national_id.startswith("CF"):
        pattern = r'^CF[0-9A-Z]{12}$'  # CF + 12 characters = 14 total
        if not re.match(pattern, national_id):
            raise ValidationError(
                'Female National IDs must start with "CF" followed by 12 alphanumeric characters.'
            )
    else:
        raise ValidationError(
            'National ID must start with "CM" (male) or "CF" (female).'
        )
