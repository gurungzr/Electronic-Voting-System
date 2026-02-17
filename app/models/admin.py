from datetime import datetime
from flask_login import UserMixin
from bson import ObjectId
from app import get_db
from app.utils.security import hash_password, verify_password


class Admin(UserMixin):
    """Admin model for administrative users."""

    collection_name = 'admins'

    def __init__(self, username: str, password_hash: str,
                 created_at: datetime = None, _id=None):
        self._id = _id
        self.username = username
        self.password_hash = password_hash
        self.created_at = created_at or datetime.utcnow()
        self.is_admin = True  # Flag to distinguish from voter

    def get_id(self):
        """Return user ID for Flask-Login."""
        return str(self._id)

    def to_dict(self) -> dict:
        """Convert admin to dictionary."""
        data = {
            'username': self.username,
            'password_hash': self.password_hash,
            'created_at': self.created_at
        }
        if self._id:
            data['_id'] = self._id
        return data

    @classmethod
    def from_dict(cls, data: dict):
        """Create Admin from dictionary."""
        if not data:
            return None
        admin = cls(
            username=data.get('username'),
            password_hash=data.get('password_hash'),
            created_at=data.get('created_at'),
            _id=data.get('_id')
        )
        return admin

    def save(self):
        """Save admin to database."""
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

    @classmethod
    def create(cls, username: str, password: str):
        """Create a new admin."""
        admin = cls(
            username=username,
            password_hash=hash_password(password)
        )
        return admin.save()

    @classmethod
    def find_by_id(cls, user_id: str):
        """Find admin by MongoDB _id."""
        db = get_db()
        try:
            data = db[cls.collection_name].find_one({'_id': ObjectId(user_id)})
            return cls.from_dict(data)
        except Exception:
            return None

    @classmethod
    def find_by_username(cls, username: str):
        """Find admin by username."""
        db = get_db()
        data = db[cls.collection_name].find_one({'username': username})
        return cls.from_dict(data)

    @classmethod
    def username_exists(cls, username: str) -> bool:
        """Check if username already exists."""
        return cls.find_by_username(username) is not None
