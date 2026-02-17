from datetime import datetime
from bson import ObjectId
from app import get_db


class Citizen:
    """Citizen model for mock citizen database verification."""

    collection_name = 'citizens'

    VALID_CONSTITUENCIES = ["Kathmandu", "Lalitpur", "Bhaktapur"]

    def __init__(self, citizenship_number: str, full_name: str,
                 date_of_birth: datetime, address: str, constituency: str,
                 is_eligible: bool = True, _id=None):
        self._id = _id
        self.citizenship_number = citizenship_number
        self.full_name = full_name
        self.date_of_birth = date_of_birth
        self.address = address
        self.constituency = constituency  # Kathmandu, Lalitpur, or Bhaktapur
        self.is_eligible = is_eligible

    def to_dict(self) -> dict:
        """Convert citizen to dictionary."""
        data = {
            'citizenship_number': self.citizenship_number,
            'full_name': self.full_name,
            'date_of_birth': self.date_of_birth,
            'address': self.address,
            'constituency': self.constituency,
            'is_eligible': self.is_eligible
        }
        if self._id:
            data['_id'] = self._id
        return data

    @classmethod
    def from_dict(cls, data: dict):
        """Create Citizen from dictionary."""
        if not data:
            return None
        return cls(
            citizenship_number=data.get('citizenship_number'),
            full_name=data.get('full_name'),
            date_of_birth=data.get('date_of_birth'),
            address=data.get('address'),
            constituency=data.get('constituency'),
            is_eligible=data.get('is_eligible', True),
            _id=data.get('_id')
        )

    def save(self):
        """Save citizen to database."""
        db = get_db()
        if self._id:
            db[self.collection_name].update_one(
                {'_id': self._id},
                {'$set': self.to_dict()}
            )
        else:
            result = db[self.collection_name].insert_one(self.to_dict())
            self._id = result.inserted_id
        return self

    @classmethod
    def find_by_citizenship_number(cls, citizenship_number: str):
        """Find citizen by citizenship number."""
        db = get_db()
        data = db[cls.collection_name].find_one({
            'citizenship_number': citizenship_number
        })
        return cls.from_dict(data)

    @classmethod
    def verify_eligibility(cls, citizenship_number: str, full_name: str,
                           date_of_birth: str) -> tuple[bool, str]:
        """Verify citizen eligibility for voter registration.

        Returns: (is_eligible, message)
        """
        citizen = cls.find_by_citizenship_number(citizenship_number)

        if not citizen:
            return False, "Citizenship number not found in records"

        if citizen.full_name.lower() != full_name.lower():
            return False, "Name does not match records"

        # Convert date_of_birth string to compare
        if isinstance(date_of_birth, str):
            from datetime import datetime as dt
            dob = dt.strptime(date_of_birth, '%Y-%m-%d')
        else:
            dob = date_of_birth

        # Compare dates (ignoring time component)
        if citizen.date_of_birth.date() != dob.date():
            return False, "Date of birth does not match records"

        if not citizen.is_eligible:
            return False, "You are not eligible to vote"

        return True, "Verification successful"

    @classmethod
    def count_all(cls) -> int:
        """Count all citizens."""
        db = get_db()
        return db[cls.collection_name].count_documents({})
