from datetime import datetime
from bson import ObjectId
from app import get_db
from app.utils.security import generate_election_id, generate_candidate_id, generate_party_id


class Election:
    """Election model for managing dual-ballot elections (FPTP + PR)."""

    collection_name = 'elections'
    VALID_CONSTITUENCIES = ["Kathmandu", "Lalitpur", "Bhaktapur"]
    DEFAULT_PR_SEATS = 110

    def __init__(self, election_id: str, name: str, description: str,
                 candidates: list, parties: list, start_date: datetime, end_date: datetime,
                 total_pr_seats: int = 110, is_active: bool = True,
                 public_key: str = None, encrypted_key_bundle: str = None,
                 created_at: datetime = None, _id=None):
        self._id = _id
        self.election_id = election_id
        self.name = name
        self.description = description
        self.candidates = candidates  # List of {candidate_id, name, party, constituency}
        self.parties = parties  # List of {party_id, name} for PR ballot
        self.total_pr_seats = total_pr_seats  # Total PR seats to allocate (default 110)
        self.start_date = start_date
        self.end_date = end_date
        self.is_active = is_active
        self.public_key = public_key  # JSON containing hybrid public keys (RSA + Kyber) for vote encryption
        self.encrypted_key_bundle = encrypted_key_bundle  # Encrypted private keys bundle (decrypt with Shamir shares)
        self.created_at = created_at or datetime.utcnow()

    def to_dict(self) -> dict:
        """Convert election to dictionary."""
        data = {
            'election_id': self.election_id,
            'name': self.name,
            'description': self.description,
            'candidates': self.candidates,
            'parties': self.parties,
            'total_pr_seats': self.total_pr_seats,
            'start_date': self.start_date,
            'end_date': self.end_date,
            'is_active': self.is_active,
            'public_key': self.public_key,
            'encrypted_key_bundle': self.encrypted_key_bundle,
            'created_at': self.created_at
        }
        if self._id:
            data['_id'] = self._id
        return data

    @classmethod
    def from_dict(cls, data: dict):
        """Create Election from dictionary."""
        if not data:
            return None
        return cls(
            election_id=data.get('election_id'),
            name=data.get('name'),
            description=data.get('description'),
            candidates=data.get('candidates', []),
            parties=data.get('parties', []),
            total_pr_seats=data.get('total_pr_seats', cls.DEFAULT_PR_SEATS),
            start_date=data.get('start_date'),
            end_date=data.get('end_date'),
            is_active=data.get('is_active', True),
            public_key=data.get('public_key'),
            encrypted_key_bundle=data.get('encrypted_key_bundle'),
            created_at=data.get('created_at'),
            _id=data.get('_id')
        )

    def save(self):
        """Save election to database."""
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

    def is_ongoing(self) -> bool:
        """Check if election is currently ongoing."""
        now = datetime.utcnow()
        return self.is_active and self.start_date <= now <= self.end_date

    def has_ended(self) -> bool:
        """Check if election has ended."""
        return datetime.utcnow() > self.end_date

    def has_started(self) -> bool:
        """Check if election has started."""
        return datetime.utcnow() >= self.start_date

    def get_candidate(self, candidate_id: str) -> dict:
        """Get candidate by ID."""
        for candidate in self.candidates:
            if candidate['candidate_id'] == candidate_id:
                return candidate
        return None

    def get_candidates_by_constituency(self, constituency: str) -> list:
        """Get all candidates for a specific constituency."""
        return [c for c in self.candidates if c.get('constituency') == constituency]

    def get_party(self, party_id: str) -> dict:
        """Get party by ID."""
        for party in self.parties:
            if party['party_id'] == party_id:
                return party
        return None

    def add_candidate(self, name: str, party: str, constituency: str) -> str:
        """Add a candidate to the election."""
        if constituency not in self.VALID_CONSTITUENCIES:
            raise ValueError(f"Invalid constituency. Must be one of: {self.VALID_CONSTITUENCIES}")
        candidate_id = generate_candidate_id()
        self.candidates.append({
            'candidate_id': candidate_id,
            'name': name,
            'party': party,
            'constituency': constituency
        })
        self.save()
        return candidate_id

    def add_party(self, name: str, symbol: str = None) -> str:
        """Add a party to the election for PR ballot."""
        party_id = generate_party_id()
        party_data = {
            'party_id': party_id,
            'name': name
        }
        if symbol:
            party_data['symbol'] = symbol
        self.parties.append(party_data)
        self.save()
        return party_id

    @classmethod
    def create(cls, name: str, description: str, start_date: datetime,
               end_date: datetime, candidates: list = None, parties: list = None,
               total_pr_seats: int = 110, public_key: str = None,
               encrypted_key_bundle: str = None):
        """Create a new dual-ballot election.

        Args:
            name: Election name
            description: Election description
            start_date: Election start datetime
            end_date: Election end datetime
            candidates: List of candidate dicts
            parties: List of party dicts
            total_pr_seats: Total PR seats to allocate
            public_key: JSON containing hybrid public keys (RSA + Kyber) for vote encryption
            encrypted_key_bundle: Encrypted private keys bundle (decrypt with Shamir shares)
        """
        election_id = generate_election_id()

        # Ensure unique election ID
        while cls.find_by_election_id(election_id):
            election_id = generate_election_id()

        # Process candidates - add IDs if not present
        processed_candidates = []
        if candidates:
            for c in candidates:
                processed_candidates.append({
                    'candidate_id': c.get('candidate_id') or generate_candidate_id(),
                    'name': c['name'],
                    'party': c.get('party', 'Independent'),
                    'constituency': c.get('constituency')
                })

        # Process parties - add IDs if not present
        processed_parties = []
        if parties:
            for p in parties:
                party_data = {
                    'party_id': p.get('party_id') or generate_party_id(),
                    'name': p['name']
                }
                if p.get('symbol'):
                    party_data['symbol'] = p['symbol']
                processed_parties.append(party_data)

        election = cls(
            election_id=election_id,
            name=name,
            description=description,
            candidates=processed_candidates,
            parties=processed_parties,
            total_pr_seats=total_pr_seats,
            start_date=start_date,
            end_date=end_date,
            public_key=public_key,
            encrypted_key_bundle=encrypted_key_bundle
        )
        return election.save()

    @classmethod
    def find_by_id(cls, doc_id: str):
        """Find election by MongoDB _id."""
        db = get_db()
        try:
            data = db[cls.collection_name].find_one({'_id': ObjectId(doc_id)})
            return cls.from_dict(data)
        except Exception:
            return None

    @classmethod
    def find_by_election_id(cls, election_id: str):
        """Find election by election ID."""
        db = get_db()
        data = db[cls.collection_name].find_one({'election_id': election_id})
        return cls.from_dict(data)

    @classmethod
    def get_active_elections(cls) -> list:
        """Get all active elections that are currently ongoing."""
        db = get_db()
        now = datetime.utcnow()
        elections = db[cls.collection_name].find({
            'is_active': True,
            'start_date': {'$lte': now},
            'end_date': {'$gte': now}
        }).sort('end_date', 1)
        return [cls.from_dict(e) for e in elections]

    @classmethod
    def get_upcoming_elections(cls) -> list:
        """Get elections that haven't started yet."""
        db = get_db()
        now = datetime.utcnow()
        elections = db[cls.collection_name].find({
            'is_active': True,
            'start_date': {'$gt': now}
        }).sort('start_date', 1)
        return [cls.from_dict(e) for e in elections]

    @classmethod
    def get_past_elections(cls) -> list:
        """Get elections that have ended."""
        db = get_db()
        now = datetime.utcnow()
        elections = db[cls.collection_name].find({
            'end_date': {'$lt': now}
        }).sort('end_date', -1)
        return [cls.from_dict(e) for e in elections]

    @classmethod
    def get_all_elections(cls) -> list:
        """Get all elections."""
        db = get_db()
        elections = db[cls.collection_name].find().sort('created_at', -1)
        return [cls.from_dict(e) for e in elections]

    @classmethod
    def count_all(cls) -> int:
        """Count all elections."""
        db = get_db()
        return db[cls.collection_name].count_documents({})

    @classmethod
    def deactivate(cls, election_id: str):
        """Deactivate an election."""
        db = get_db()
        db[cls.collection_name].update_one(
            {'election_id': election_id},
            {'$set': {'is_active': False}}
        )

    @classmethod
    def terminate(cls, election_id: str):
        """Terminate an ongoing election immediately.

        Sets the end_date to now, allowing results to be viewed.
        """
        db = get_db()
        db[cls.collection_name].update_one(
            {'election_id': election_id},
            {'$set': {'end_date': datetime.utcnow()}}
        )
