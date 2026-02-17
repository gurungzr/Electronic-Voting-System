from datetime import datetime
from flask_login import UserMixin
from bson import ObjectId
from app import get_db
from app.utils.security import hash_password, verify_password, generate_voter_id, hash_citizenship_number


class Voter(UserMixin):
    """Voter model for registered voters."""

    collection_name = 'voters'

    def __init__(self, voter_id: str, citizenship_number_hash: str,
                 password_hash: str, full_name: str, constituency: str,
                 registered_at: datetime = None,
                 elections_voted: list = None, token_issued_for: list = None,
                 _id=None):
        self._id = _id
        self.voter_id = voter_id
        self.citizenship_number_hash = citizenship_number_hash
        self.password_hash = password_hash
        self.full_name = full_name
        self.constituency = constituency  # Voter's assigned constituency
        self.registered_at = registered_at or datetime.utcnow()
        self.elections_voted = elections_voted or []
        self.token_issued_for = token_issued_for or []  # Elections with issued tokens
        self.is_admin = False  # Flag to distinguish from admin

    def get_id(self):
        """Return user ID for Flask-Login."""
        return str(self._id)

    def to_dict(self) -> dict:
        """Convert voter to dictionary."""
        data = {
            'voter_id': self.voter_id,
            'citizenship_number_hash': self.citizenship_number_hash,
            'password_hash': self.password_hash,
            'full_name': self.full_name,
            'constituency': self.constituency,
            'registered_at': self.registered_at,
            'elections_voted': self.elections_voted,
            'token_issued_for': self.token_issued_for
        }
        if self._id:
            data['_id'] = self._id
        return data

    @classmethod
    def from_dict(cls, data: dict):
        """Create Voter from dictionary."""
        if not data:
            return None
        voter = cls(
            voter_id=data.get('voter_id'),
            citizenship_number_hash=data.get('citizenship_number_hash'),
            password_hash=data.get('password_hash'),
            full_name=data.get('full_name'),
            constituency=data.get('constituency'),
            registered_at=data.get('registered_at'),
            elections_voted=data.get('elections_voted', []),
            token_issued_for=data.get('token_issued_for', []),
            _id=data.get('_id')
        )
        return voter

    def save(self):
        """Save voter to database."""
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

    def check_password(self, password: str) -> bool:
        """Verify password."""
        return verify_password(password, self.password_hash)

    def has_voted_in(self, election_id: str) -> bool:
        """Check if voter has voted in a specific election."""
        return election_id in self.elections_voted

    def mark_voted(self, election_id: str):
        """Mark voter as having voted in an election."""
        if election_id not in self.elections_voted:
            self.elections_voted.append(election_id)
            db = get_db()
            db[self.collection_name].update_one(
                {'_id': self._id},
                {'$push': {'elections_voted': election_id}}
            )

    def has_token_for(self, election_id: str) -> bool:
        """Check if voter has been issued a token for an election."""
        return election_id in self.token_issued_for

    def mark_token_issued(self, election_id: str):
        """Mark that a token was issued for an election.

        Uses atomic $addToSet to prevent duplicates.
        Note: This only records that a token was issued, not which token.
        """
        if election_id not in self.token_issued_for:
            self.token_issued_for.append(election_id)
            db = get_db()
            db[self.collection_name].update_one(
                {'_id': self._id},
                {'$addToSet': {'token_issued_for': election_id}}
            )

    @classmethod
    def create(cls, citizenship_number: str, password: str, full_name: str, constituency: str):
        """Create a new voter with generated voter ID."""
        voter_id = generate_voter_id()

        # Ensure unique voter ID
        while cls.find_by_voter_id(voter_id):
            voter_id = generate_voter_id()

        voter = cls(
            voter_id=voter_id,
            citizenship_number_hash=hash_citizenship_number(citizenship_number),
            password_hash=hash_password(password),
            full_name=full_name,
            constituency=constituency
        )
        return voter.save()

    @classmethod
    def find_by_id(cls, user_id: str):
        """Find voter by MongoDB _id."""
        db = get_db()
        try:
            data = db[cls.collection_name].find_one({'_id': ObjectId(user_id)})
            return cls.from_dict(data)
        except Exception:
            return None

    @classmethod
    def find_by_voter_id(cls, voter_id: str):
        """Find voter by voter ID."""
        db = get_db()
        data = db[cls.collection_name].find_one({'voter_id': voter_id})
        return cls.from_dict(data)

    @classmethod
    def find_by_citizenship_hash(cls, citizenship_number: str):
        """Find voter by citizenship number hash."""
        db = get_db()
        citizenship_hash = hash_citizenship_number(citizenship_number)
        data = db[cls.collection_name].find_one({
            'citizenship_number_hash': citizenship_hash
        })
        return cls.from_dict(data)

    @classmethod
    def is_already_registered(cls, citizenship_number: str) -> bool:
        """Check if citizenship number is already registered."""
        return cls.find_by_citizenship_hash(citizenship_number) is not None

    @classmethod
    def count_all(cls) -> int:
        """Count all registered voters."""
        db = get_db()
        return db[cls.collection_name].count_documents({})

    @classmethod
    def count_voted_in_election(cls, election_id: str) -> int:
        """Count voters who have voted in a specific election."""
        db = get_db()
        return db[cls.collection_name].count_documents({
            'elections_voted': election_id
        })
