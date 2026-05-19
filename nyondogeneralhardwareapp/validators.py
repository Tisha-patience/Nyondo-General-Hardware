import re
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError


    
def validate_ugandan_national_id(national_id):
    # Male IDs must start with CM, Female IDs must start with CF
    if national_id.startswith("CM"):
        pattern = r'^CM[0-9A-Z]{12}$'  # CM + 12 characters = 14 total
        if not re.match(pattern, national_id) or len(national_id) != 14:
            raise ValidationError("Male National IDs must be exactly 14 characters (CM + 12 alphanumeric).")
    elif national_id.startswith("CF"):
        pattern = r'^CF[0-9A-Z]{12}$'  # CF + 12 characters = 14 total
        if not re.match(pattern, national_id) or len(national_id) != 14:
           raise ValidationError("Female National IDs must be exactly 14 characters (CF + 12 alphanumeric).")
    else:
        raise ValidationError(
            'National ID must start with "CM" (male) or "CF" (female).'
        )
