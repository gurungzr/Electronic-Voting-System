import re
from datetime import datetime, date


def validate_citizenship_number(citizenship_number: str) -> tuple[bool, str]:
    """Validate citizenship number format.

    Expected format: Alphanumeric, 8-15 characters
    Returns: (is_valid, error_message)
    """
    if not citizenship_number:
        return False, "Citizenship number is required"

    if not re.match(r'^[A-Za-z0-9]{8,15}$', citizenship_number):
        return False, "Citizenship number must be 8-15 alphanumeric characters"

    return True, ""


def validate_password(password: str) -> tuple[bool, str]:
    """Validate password strength.

    Requirements:
    - Minimum 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - At least one special character

    Returns: (is_valid, error_message)
    """
    if not password:
        return False, "Password is required"

    if len(password) < 8:
        return False, "Password must be at least 8 characters long"

    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"

    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"

    if not re.search(r'\d', password):
        return False, "Password must contain at least one digit"

    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False, "Password must contain at least one special character"

    return True, ""


def validate_full_name(full_name: str) -> tuple[bool, str]:
    """Validate full name.

    Returns: (is_valid, error_message)
    """
    if not full_name:
        return False, "Full name is required"

    if len(full_name) < 2:
        return False, "Full name must be at least 2 characters"

    if len(full_name) > 100:
        return False, "Full name must be less than 100 characters"

    # Allow letters, spaces, hyphens, and apostrophes
    if not re.match(r"^[A-Za-z\s\-']+$", full_name):
        return False, "Full name can only contain letters, spaces, hyphens, and apostrophes"

    return True, ""


def validate_date_of_birth(dob_str: str) -> tuple[bool, str]:
    """Validate date of birth.

    Expected format: YYYY-MM-DD
    Must be at least 18 years old

    Returns: (is_valid, error_message)
    """
    if not dob_str:
        return False, "Date of birth is required"

    try:
        dob = datetime.strptime(dob_str, '%Y-%m-%d').date()
    except ValueError:
        return False, "Invalid date format. Use YYYY-MM-DD"

    today = date.today()
    age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

    if age < 18:
        return False, "You must be at least 18 years old to register"

    if age > 120:
        return False, "Invalid date of birth"

    return True, ""


def validate_voter_id(voter_id: str) -> tuple[bool, str]:
    """Validate voter ID format.

    Expected format: VTR-XXXXXXXX

    Returns: (is_valid, error_message)
    """
    if not voter_id:
        return False, "Voter ID is required"

    if not re.match(r'^VTR-[A-F0-9]{8}$', voter_id):
        return False, "Invalid Voter ID format"

    return True, ""


def validate_election_dates(start_date: str, end_date: str) -> tuple[bool, str]:
    """Validate election dates.

    Start date must be before end date

    Returns: (is_valid, error_message)
    """
    try:
        start = datetime.strptime(start_date, '%Y-%m-%dT%H:%M')
        end = datetime.strptime(end_date, '%Y-%m-%dT%H:%M')
    except ValueError:
        return False, "Invalid date format"

    if start >= end:
        return False, "Start date must be before end date"

    return True, ""


# Valid constituencies for the dual-ballot system
VALID_CONSTITUENCIES = ["Kathmandu", "Lalitpur", "Bhaktapur"]


def validate_constituency(constituency: str) -> tuple[bool, str]:
    """Validate constituency.

    Returns: (is_valid, error_message)
    """
    if not constituency:
        return False, "Constituency is required"

    if constituency not in VALID_CONSTITUENCIES:
        return False, f"Invalid constituency. Must be one of: {', '.join(VALID_CONSTITUENCIES)}"

    return True, ""


def validate_party_id(party_id: str) -> tuple[bool, str]:
    """Validate party ID format.

    Expected format: PTY-XXXXXX

    Returns: (is_valid, error_message)
    """
    if not party_id:
        return False, "Party selection is required"

    if not re.match(r'^PTY-[A-F0-9]{6}$', party_id):
        return False, "Invalid party ID format"

    return True, ""


def validate_candidate_id(candidate_id: str) -> tuple[bool, str]:
    """Validate candidate ID format.

    Expected format: CND-XXXXXX

    Returns: (is_valid, error_message)
    """
    if not candidate_id:
        return False, "Candidate selection is required"

    if not re.match(r'^CND-[A-F0-9]{6}$', candidate_id):
        return False, "Invalid candidate ID format"

    return True, ""


def sanitize_input(text: str) -> str:
    """Sanitize text input to prevent XSS.

    Removes or escapes potentially dangerous characters.
    """
    if not text:
        return ""

    # Remove any script tags
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.IGNORECASE | re.DOTALL)

    # Escape HTML special characters
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    text = text.replace('"', '&quot;')
    text = text.replace("'", '&#x27;')

    return text.strip()
