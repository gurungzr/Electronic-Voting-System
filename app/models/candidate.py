"""Candidate model for the candidate pool."""
from datetime import datetime
from app import get_db
import secrets


def generate_candidate_id():
    """Generate unique candidate ID."""
    return f"CND-{secrets.token_hex(4).upper()}"


class Candidate:
    """Model for FPTP candidates (reusable across elections)."""

    collection_name = 'candidates'

    def __init__(self, name: str, party: str, constituency: str,
                 candidate_id: str = None, is_active: bool = True,
                 created_at: datetime = None, _id=None):
        self._id = _id
        self.candidate_id = candidate_id or generate_candidate_id()
        self.name = name
        self.party = party
        self.constituency = constituency
        self.is_active = is_active
        self.created_at = created_at or datetime.utcnow()

    def to_dict(self) -> dict:
        """Convert candidate to dictionary."""
        data = {
            'candidate_id': self.candidate_id,
            'name': self.name,
            'party': self.party,
            'constituency': self.constituency,
            'is_active': self.is_active,
            'created_at': self.created_at
        }
        if self._id:
            data['_id'] = self._id
        return data

    @classmethod
    def from_dict(cls, data: dict):
        """Create Candidate from dictionary."""
        if not data:
            return None
        return cls(
            name=data.get('name'),
            party=data.get('party'),
            constituency=data.get('constituency'),
            candidate_id=data.get('candidate_id'),
            is_active=data.get('is_active', True),
            created_at=data.get('created_at'),
            _id=data.get('_id')
        )

    def save(self):
        """Save candidate to database."""
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
    def create(cls, name: str, party: str, constituency: str):
        """Create and save a new candidate."""
        candidate = cls(name=name, party=party, constituency=constituency)
        return candidate.save()

    @classmethod
    def find_by_candidate_id(cls, candidate_id: str):
        """Find candidate by ID."""
        db = get_db()
        data = db[cls.collection_name].find_one({'candidate_id': candidate_id})
        return cls.from_dict(data)

    @classmethod
    def find_by_ids(cls, candidate_ids: list):
        """Find multiple candidates by their IDs."""
        db = get_db()
        candidates = db[cls.collection_name].find({
            'candidate_id': {'$in': candidate_ids}
        })
        return [cls.from_dict(c) for c in candidates]

    @classmethod
    def get_all_active(cls):
        """Get all active candidates."""
        db = get_db()
        candidates = db[cls.collection_name].find({'is_active': True})
        return [cls.from_dict(c) for c in candidates]

    @classmethod
    def get_by_constituency(cls, constituency: str, active_only: bool = True):
        """Get all candidates for a specific constituency."""
        db = get_db()
        query = {'constituency': constituency}
        if active_only:
            query['is_active'] = True
        candidates = db[cls.collection_name].find(query)
        return [cls.from_dict(c) for c in candidates]

    @classmethod
    def get_grouped_by_constituency(cls, active_only: bool = True):
        """Get all candidates grouped by constituency."""
        db = get_db()
        query = {'is_active': True} if active_only else {}
        candidates = db[cls.collection_name].find(query).sort('constituency', 1)

        grouped = {}
        for c in candidates:
            candidate = cls.from_dict(c)
            if candidate.constituency not in grouped:
                grouped[candidate.constituency] = []
            grouped[candidate.constituency].append(candidate)

        return grouped

    @classmethod
    def count_by_constituency(cls):
        """Count candidates per constituency."""
        db = get_db()
        pipeline = [
            {'$match': {'is_active': True}},
            {'$group': {'_id': '$constituency', 'count': {'$sum': 1}}}
        ]
        results = db[cls.collection_name].aggregate(pipeline)
        return {r['_id']: r['count'] for r in results}

    @classmethod
    def ensure_indexes(cls):
        """Create database indexes for candidates collection."""
        db = get_db()
        db[cls.collection_name].create_index('candidate_id', unique=True)
        db[cls.collection_name].create_index('constituency')
        db[cls.collection_name].create_index('party')
        db[cls.collection_name].create_index('is_active')
