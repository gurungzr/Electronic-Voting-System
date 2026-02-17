from app.models.voter import Voter
from app.models.citizen import Citizen
from app.models.admin import Admin
from app.utils.validators import (
    validate_citizenship_number,
    validate_password,
    validate_full_name,
    validate_date_of_birth,
    validate_voter_id
)


class AuthService:
    """Service for handling authentication operations."""

    @staticmethod
    def register_voter(citizenship_number: str, full_name: str,
                       date_of_birth: str, password: str,
                       confirm_password: str) -> tuple[bool, str, Voter]:
        """Register a new voter.

        Returns: (success, message, voter)
        """
        # Validate inputs
        valid, msg = validate_citizenship_number(citizenship_number)
        if not valid:
            return False, msg, None

        valid, msg = validate_full_name(full_name)
        if not valid:
            return False, msg, None

        valid, msg = validate_date_of_birth(date_of_birth)
        if not valid:
            return False, msg, None

        valid, msg = validate_password(password)
        if not valid:
            return False, msg, None

        if password != confirm_password:
            return False, "Passwords do not match", None

        # Check if already registered
        if Voter.is_already_registered(citizenship_number):
            return False, "This citizenship number is already registered", None

        # Verify against citizen database
        valid, msg = Citizen.verify_eligibility(
            citizenship_number, full_name, date_of_birth
        )
        if not valid:
            return False, msg, None

        # Get citizen's constituency
        citizen = Citizen.find_by_citizenship_number(citizenship_number)
        if not citizen or not citizen.constituency:
            return False, "Citizen constituency information not found", None

        # Create voter with constituency
        try:
            voter = Voter.create(
                citizenship_number=citizenship_number,
                password=password,
                full_name=full_name,
                constituency=citizen.constituency
            )
            return True, f"Registration successful! Your Voter ID is: {voter.voter_id}", voter
        except Exception as e:
            return False, f"Registration failed: {str(e)}", None

    @staticmethod
    def login_voter(voter_id: str, password: str) -> tuple[bool, str, Voter]:
        """Authenticate a voter.

        Returns: (success, message, voter)
        """
        valid, msg = validate_voter_id(voter_id)
        if not valid:
            return False, msg, None

        if not password:
            return False, "Password is required", None

        voter = Voter.find_by_voter_id(voter_id)
        if not voter:
            return False, "Invalid Voter ID or password", None

        if not voter.check_password(password):
            return False, "Invalid Voter ID or password", None

        return True, "Login successful", voter

    @staticmethod
    def login_admin(username: str, password: str) -> tuple[bool, str, Admin]:
        """Authenticate an admin.

        Returns: (success, message, admin)
        """
        if not username:
            return False, "Username is required", None

        if not password:
            return False, "Password is required", None

        admin = Admin.find_by_username(username)
        if not admin:
            return False, "Invalid username or password", None

        if not admin.check_password(password):
            return False, "Invalid username or password", None

        return True, "Login successful", admin

    @staticmethod
    def create_admin(username: str, password: str) -> tuple[bool, str, Admin]:
        """Create a new admin account.

        Returns: (success, message, admin)
        """
        if not username or len(username) < 3:
            return False, "Username must be at least 3 characters", None

        valid, msg = validate_password(password)
        if not valid:
            return False, msg, None

        if Admin.username_exists(username):
            return False, "Username already exists", None

        try:
            admin = Admin.create(username=username, password=password)
            return True, "Admin account created successfully", admin
        except Exception as e:
            return False, f"Failed to create admin: {str(e)}", None
