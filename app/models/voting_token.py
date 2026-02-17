from datetime import datetime
from bson import ObjectId
from app import get_db
from app.utils.security import generate_vote_token


class VotingToken:
    """Model for single-use anonymous voting tokens.

    Tokens are issued to voters but stored WITHOUT any voter reference,
    maintaining anonymity between voter identity and vote records.
    """

    collection_name = 'voting_tokens'
    BALLOT_TYPES = ['fptp', 'pr']

    def __init__(self, token_id: str, election_id: str, constituency: str,
                 ballots_allowed: list = None, ballots_used: list = None,
                 is_fully_used: bool = False, created_at: datetime = None,
                 used_at: datetime = None, _id=None):
        self._id = _id
        self.token_id = token_id
        self.election_id = election_id
        self.constituency = constituency
        self.ballots_allowed = ballots_allowed or ['fptp', 'pr']
        self.ballots_used = ballots_used or []
        self.is_fully_used = is_fully_used
        self.created_at = created_at or datetime.utcnow()
        self.used_at = used_at

    def to_dict(self) -> dict:
        """Convert token to dictionary."""
        data = {
            'token_id': self.token_id,
            'election_id': self.election_id,
            'constituency': self.constituency,
            'ballots_allowed': self.ballots_allowed,
            'ballots_used': self.ballots_used,
            'is_fully_used': self.is_fully_used,
            'created_at': self.created_at,
            'used_at': self.used_at
        }
        if self._id:
            data['_id'] = self._id
        return data

    @classmethod
    def from_dict(cls, data: dict):
        """Create VotingToken from dictionary."""
        if not data:
            return None
        return cls(
            token_id=data.get('token_id'),
            election_id=data.get('election_id'),
            constituency=data.get('constituency'),
            ballots_allowed=data.get('ballots_allowed', ['fptp', 'pr']),
            ballots_used=data.get('ballots_used', []),
            is_fully_used=data.get('is_fully_used', False),
            created_at=data.get('created_at'),
            used_at=data.get('used_at'),
            _id=data.get('_id')
        )

    def save(self):
        """Save token to database."""
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

    def is_valid_for_ballot(self, ballot_type: str) -> bool:
        """Check if token can be used for a specific ballot type."""
        if self.is_fully_used:
            return False
        if ballot_type not in self.ballots_allowed:
            return False
        if ballot_type in self.ballots_used:
            return False
        return True

    def mark_ballot_used(self, ballot_type: str) -> bool:
        """Mark a ballot type as used. Uses atomic MongoDB operation.

        Returns True if successful, False if ballot was already used.
        """
        if ballot_type not in self.BALLOT_TYPES:
            return False

        db = get_db()

        # Determine if this will complete all ballots
        will_be_fully_used = len(self.ballots_used) + 1 >= len(self.ballots_allowed)

        # Atomic update: only succeeds if ballot_type not already in ballots_used
        update_fields = {
            '$push': {'ballots_used': ballot_type}
        }

        if will_be_fully_used:
            update_fields['$set'] = {
                'is_fully_used': True,
                'used_at': datetime.utcnow()
            }

        result = db[self.collection_name].update_one(
            {
                'token_id': self.token_id,
                'ballots_used': {'$ne': ballot_type},
                'is_fully_used': False
            },
            update_fields
        )

        if result.modified_count > 0:
            # Update local state
            self.ballots_used.append(ballot_type)
            if will_be_fully_used:
                self.is_fully_used = True
                self.used_at = datetime.utcnow()
            return True
        return False

    @classmethod
    def create(cls, election_id: str, constituency: str):
        """Create a new voting token.

        Note: No voter_id is stored - this maintains anonymity.
        """
        token_id = generate_vote_token()

        # Ensure unique token_id
        while cls.find_by_token_id(token_id):
            token_id = generate_vote_token()

        token = cls(
            token_id=token_id,
            election_id=election_id,
            constituency=constituency
        )
        return token.save()

    @classmethod
    def find_by_token_id(cls, token_id: str):
        """Find token by token_id."""
        db = get_db()
        data = db[cls.collection_name].find_one({'token_id': token_id})
        return cls.from_dict(data)

    @classmethod
    def find_by_id(cls, _id: str):
        """Find token by MongoDB _id."""
        db = get_db()
        try:
            data = db[cls.collection_name].find_one({'_id': ObjectId(_id)})
            return cls.from_dict(data)
        except Exception:
            return None

    @classmethod
    def count_by_election(cls, election_id: str, is_fully_used: bool = None) -> int:
        """Count tokens for an election, optionally filtered by usage status."""
        db = get_db()
        query = {'election_id': election_id}
        if is_fully_used is not None:
            query['is_fully_used'] = is_fully_used
        return db[cls.collection_name].count_documents(query)

    @classmethod
    def get_election_stats(cls, election_id: str) -> dict:
        """Get token statistics for an election.

        Returns: {
            'tokens_issued': int,
            'tokens_fully_used': int,
            'tokens_partial': int,
            'tokens_unused': int,
            'fptp_ballots_cast': int,
            'pr_ballots_cast': int
        }
        """
        db = get_db()

        # Count total tokens issued
        tokens_issued = db[cls.collection_name].count_documents({
            'election_id': election_id
        })

        # Count fully used tokens
        tokens_fully_used = db[cls.collection_name].count_documents({
            'election_id': election_id,
            'is_fully_used': True
        })

        # Count partial tokens (at least one ballot used, but not fully)
        tokens_partial = db[cls.collection_name].count_documents({
            'election_id': election_id,
            'is_fully_used': False,
            'ballots_used': {'$ne': []}
        })

        # Count unused tokens
        tokens_unused = db[cls.collection_name].count_documents({
            'election_id': election_id,
            'ballots_used': []
        })

        # Count ballots cast by type using aggregation
        pipeline = [
            {'$match': {'election_id': election_id}},
            {'$unwind': '$ballots_used'},
            {'$group': {
                '_id': '$ballots_used',
                'count': {'$sum': 1}
            }}
        ]
        ballot_counts = list(db[cls.collection_name].aggregate(pipeline))

        fptp_ballots = 0
        pr_ballots = 0
        for bc in ballot_counts:
            if bc['_id'] == 'fptp':
                fptp_ballots = bc['count']
            elif bc['_id'] == 'pr':
                pr_ballots = bc['count']

        return {
            'tokens_issued': tokens_issued,
            'tokens_fully_used': tokens_fully_used,
            'tokens_partial': tokens_partial,
            'tokens_unused': tokens_unused,
            'fptp_ballots_cast': fptp_ballots,
            'pr_ballots_cast': pr_ballots
        }

    @classmethod
    def count_all(cls) -> int:
        """Count all tokens."""
        db = get_db()
        return db[cls.collection_name].count_documents({})

    @classmethod
    def count_all_used(cls) -> int:
        """Count all fully used tokens."""
        db = get_db()
        return db[cls.collection_name].count_documents({'is_fully_used': True})
