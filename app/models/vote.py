from datetime import datetime
import hashlib
import secrets
from bson import ObjectId
from app import get_db
from app.utils.security import generate_vote_token


class Vote:
    """Vote model for storing anonymous encrypted votes (FPTP and PR ballots).

    Votes are encrypted using hybrid RSA+AES encryption. The vote choices
    (candidate_id, party_id) are stored encrypted and can only be decrypted
    using Shamir's Secret Sharing threshold scheme.
    """

    collection_name = 'votes'
    BALLOT_TYPES = ['fptp', 'pr']

    def __init__(self, election_id: str, ballot_type: str,
                 candidate_id: str = None, party_id: str = None,
                 encrypted_vote: str = None, constituency: str = None,
                 timestamp: datetime = None, token_id: str = None,
                 receipt_id: str = None, receipt_hash: str = None,
                 timestamp_str: str = None, _id=None):
        self._id = _id
        self.election_id = election_id
        self.ballot_type = ballot_type  # 'fptp' or 'pr'
        self.candidate_id = candidate_id  # For FPTP votes (encrypted in DB)
        self.party_id = party_id  # For PR votes (encrypted in DB)
        self.encrypted_vote = encrypted_vote  # Encrypted vote data (RSA+AES)
        self.constituency = constituency  # For FPTP votes (stored for filtering, not encrypted)
        self.timestamp = timestamp or datetime.utcnow()
        self.token_id = token_id or generate_vote_token()
        self.receipt_id = receipt_id  # Unique receipt for voter verification (shared for FPTP+PR)
        self.receipt_hash = receipt_hash  # Hash for integrity verification
        self.timestamp_str = timestamp_str  # Stored timestamp string for consistent hash verification

    def to_dict(self) -> dict:
        """Convert vote to dictionary."""
        data = {
            'election_id': self.election_id,
            'ballot_type': self.ballot_type,
            'encrypted_vote': self.encrypted_vote,
            'constituency': self.constituency,
            'timestamp': self.timestamp,
            'token_id': self.token_id,
            'receipt_id': self.receipt_id,
            'receipt_hash': self.receipt_hash,
            'timestamp_str': self.timestamp_str
        }
        if self._id:
            data['_id'] = self._id
        return data

    @classmethod
    def from_dict(cls, data: dict):
        """Create Vote from dictionary."""
        if not data:
            return None
        return cls(
            election_id=data.get('election_id'),
            ballot_type=data.get('ballot_type'),
            candidate_id=data.get('candidate_id'),
            party_id=data.get('party_id'),
            encrypted_vote=data.get('encrypted_vote'),
            constituency=data.get('constituency'),
            timestamp=data.get('timestamp'),
            token_id=data.get('token_id'),
            receipt_id=data.get('receipt_id'),
            receipt_hash=data.get('receipt_hash'),
            timestamp_str=data.get('timestamp_str'),
            _id=data.get('_id')
        )

    def save(self):
        """Save vote to database."""
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
    def cast_fptp_vote(cls, election_id: str, candidate_id: str,
                       constituency: str, public_key: str, token_id: str = None,
                       receipt_id: str = None, receipt_hash: str = None,
                       timestamp: datetime = None, timestamp_str: str = None):
        """Cast an encrypted FPTP vote (creates anonymous vote record).

        Args:
            election_id: The election being voted in
            candidate_id: The selected candidate
            constituency: Voter's constituency
            public_key: PEM-encoded RSA public key for encryption
            token_id: Optional voting token (if using token-based voting)
            receipt_id: Shared receipt ID (if casting dual ballot)
            receipt_hash: Shared receipt hash (if casting dual ballot)
            timestamp: Shared timestamp (if casting dual ballot)
            timestamp_str: Shared timestamp string for hash verification

        Returns:
            Vote object with receipt_id for voter verification
        """
        from app.utils.shamir_crypto import ElectionCrypto

        # Encrypt the vote choice
        crypto = ElectionCrypto()
        vote_data = {
            'ballot_type': 'fptp',
            'candidate_id': candidate_id,
            'constituency': constituency
        }
        encrypted_vote = crypto.encrypt_vote(vote_data, public_key)

        # Use provided receipt or generate new one
        if not timestamp:
            timestamp = datetime.utcnow()
        if not receipt_id:
            receipt_id, receipt_hash, timestamp_str = cls.generate_receipt(election_id, timestamp)

        vote = cls(
            election_id=election_id,
            ballot_type='fptp',
            encrypted_vote=encrypted_vote,
            constituency=constituency,
            token_id=token_id,
            timestamp=timestamp,
            receipt_id=receipt_id,
            receipt_hash=receipt_hash,
            timestamp_str=timestamp_str
        )
        return vote.save()

    @classmethod
    def cast_pr_vote(cls, election_id: str, party_id: str,
                     public_key: str, token_id: str = None,
                     receipt_id: str = None, receipt_hash: str = None,
                     timestamp: datetime = None, timestamp_str: str = None):
        """Cast an encrypted PR vote (creates anonymous vote record).

        Args:
            election_id: The election being voted in
            party_id: The selected party
            public_key: PEM-encoded RSA public key for encryption
            token_id: Optional voting token (if using token-based voting)
            receipt_id: Shared receipt ID (if casting dual ballot)
            receipt_hash: Shared receipt hash (if casting dual ballot)
            timestamp: Shared timestamp (if casting dual ballot)
            timestamp_str: Shared timestamp string for hash verification

        Returns:
            Vote object with receipt_id for voter verification
        """
        from app.utils.shamir_crypto import ElectionCrypto

        # Encrypt the vote choice
        crypto = ElectionCrypto()
        vote_data = {
            'ballot_type': 'pr',
            'party_id': party_id
        }
        encrypted_vote = crypto.encrypt_vote(vote_data, public_key)

        # Use provided receipt or generate new one
        if not timestamp:
            timestamp = datetime.utcnow()
        if not receipt_id:
            receipt_id, receipt_hash, timestamp_str = cls.generate_receipt(election_id, timestamp)

        vote = cls(
            election_id=election_id,
            ballot_type='pr',
            encrypted_vote=encrypted_vote,
            token_id=token_id,
            timestamp=timestamp,
            receipt_id=receipt_id,
            receipt_hash=receipt_hash,
            timestamp_str=timestamp_str
        )
        return vote.save()

    @classmethod
    def count_by_election(cls, election_id: str, ballot_type: str = None) -> int:
        """Count total votes in an election, optionally filtered by ballot type."""
        db = get_db()
        query = {'election_id': election_id}
        if ballot_type:
            query['ballot_type'] = ballot_type
        return db[cls.collection_name].count_documents(query)

    @classmethod
    def count_by_candidate(cls, election_id: str, candidate_id: str) -> int:
        """Count FPTP votes for a specific candidate in an election."""
        db = get_db()
        return db[cls.collection_name].count_documents({
            'election_id': election_id,
            'ballot_type': 'fptp',
            'candidate_id': candidate_id
        })

    @classmethod
    def count_by_party(cls, election_id: str, party_id: str) -> int:
        """Count PR votes for a specific party in an election."""
        db = get_db()
        return db[cls.collection_name].count_documents({
            'election_id': election_id,
            'ballot_type': 'pr',
            'party_id': party_id
        })

    @classmethod
    def get_fptp_results(cls, election_id: str) -> dict:
        """Get FPTP vote counts per candidate grouped by constituency.

        Returns: {
            'Kathmandu': {candidate_id: vote_count, ...},
            'Lalitpur': {...},
            'Bhaktapur': {...}
        }
        """
        db = get_db()
        pipeline = [
            {'$match': {'election_id': election_id, 'ballot_type': 'fptp'}},
            {'$group': {
                '_id': {'constituency': '$constituency', 'candidate_id': '$candidate_id'},
                'count': {'$sum': 1}
            }}
        ]
        results = db[cls.collection_name].aggregate(pipeline)

        # Organize by constituency
        constituency_results = {}
        for r in results:
            constituency = r['_id']['constituency']
            candidate_id = r['_id']['candidate_id']
            if constituency not in constituency_results:
                constituency_results[constituency] = {}
            constituency_results[constituency][candidate_id] = r['count']

        return constituency_results

    @classmethod
    def get_pr_results(cls, election_id: str) -> dict:
        """Get PR vote counts per party.

        Returns: {party_id: vote_count, ...}
        """
        db = get_db()
        pipeline = [
            {'$match': {'election_id': election_id, 'ballot_type': 'pr'}},
            {'$group': {
                '_id': '$party_id',
                'count': {'$sum': 1}
            }}
        ]
        results = db[cls.collection_name].aggregate(pipeline)
        return {r['_id']: r['count'] for r in results}

    @classmethod
    def get_all_by_election(cls, election_id: str, ballot_type: str = None) -> list:
        """Get all votes for an election (for audit purposes)."""
        db = get_db()
        query = {'election_id': election_id}
        if ballot_type:
            query['ballot_type'] = ballot_type
        votes = db[cls.collection_name].find(query).sort('timestamp', -1)
        return [cls.from_dict(v) for v in votes]

    @staticmethod
    def generate_receipt(election_id: str, timestamp: datetime) -> tuple:
        """Generate a unique receipt ID and hash for vote verification.

        This generates a single receipt for both FPTP and PR ballots.

        Args:
            election_id: The election ID
            timestamp: Vote timestamp

        Returns:
            (receipt_id, receipt_hash, timestamp_str)
            timestamp_str is stored to ensure hash consistency
        """
        # Create receipt ID: RCP-[random 12 chars]
        receipt_id = f"RCP-{secrets.token_hex(6).upper()}"

        # Create consistent timestamp string for hashing
        timestamp_str = timestamp.strftime('%Y-%m-%d %H:%M:%S')

        # Create hash for integrity: hash(receipt_id + election_id + timestamp_str)
        hash_input = f"{receipt_id}:{election_id}:{timestamp_str}"
        receipt_hash = hashlib.sha256(hash_input.encode()).hexdigest()

        return receipt_id, receipt_hash, timestamp_str

    @classmethod
    def find_by_receipt_id(cls, receipt_id: str):
        """Find all votes by receipt ID (both FPTP and PR share same receipt).

        Args:
            receipt_id: The receipt ID (RCP-XXXX format)

        Returns:
            List of Vote objects if found, empty list otherwise
        """
        db = get_db()
        votes_data = db[cls.collection_name].find({'receipt_id': receipt_id})
        return [cls.from_dict(v) for v in votes_data]

    @classmethod
    def verify_receipt(cls, receipt_id: str, log_verification: bool = True) -> dict:
        """Verify a vote receipt and return verification details.

        This verifies both FPTP and PR ballots that share the same receipt ID.

        Args:
            receipt_id: The receipt ID to verify
            log_verification: Whether to log this verification attempt

        Returns:
            dict with verification result including both ballot confirmations
        """
        db = get_db()
        votes = cls.find_by_receipt_id(receipt_id)

        if not votes:
            return {
                'valid': False,
                'message': 'Receipt not found. Please check your receipt ID.'
            }

        # Use the first vote for common fields (both have same receipt info)
        primary_vote = votes[0]

        # Verify hash integrity using stored timestamp_str
        if primary_vote.timestamp_str:
            hash_input = f"{primary_vote.receipt_id}:{primary_vote.election_id}:{primary_vote.timestamp_str}"
        else:
            # Fallback for old votes without timestamp_str
            hash_input = f"{primary_vote.receipt_id}:{primary_vote.election_id}:{primary_vote.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"

        expected_hash = hashlib.sha256(hash_input.encode()).hexdigest()

        if expected_hash != primary_vote.receipt_hash:
            return {
                'valid': False,
                'message': 'Receipt integrity check failed.'
            }

        # Identify ballot types present
        ballot_types = [v.ballot_type.upper() for v in votes]
        has_fptp = 'FPTP' in ballot_types
        has_pr = 'PR' in ballot_types

        # Log this verification attempt for all votes with this receipt
        verification_time = datetime.utcnow()
        if log_verification:
            db[cls.collection_name].update_many(
                {'receipt_id': receipt_id},
                {
                    '$push': {
                        'verification_history': {
                            'verified_at': verification_time,
                            'verified_at_formatted': verification_time.strftime('%B %d, %Y at %I:%M %p')
                        }
                    },
                    '$set': {
                        'last_verified_at': verification_time
                    },
                    '$inc': {
                        'verification_count': 1
                    }
                }
            )

        # Get updated vote with verification history
        updated_vote = db[cls.collection_name].find_one({'receipt_id': receipt_id})
        verification_count = updated_vote.get('verification_count', 1)
        verification_history = updated_vote.get('verification_history', [])

        # Get election name
        from app.models.election import Election
        election = Election.find_by_election_id(primary_vote.election_id)
        election_name = election.name if election else primary_vote.election_id

        return {
            'valid': True,
            'message': 'Your votes were successfully recorded.',
            'election_id': primary_vote.election_id,
            'election_name': election_name,
            'ballots': {
                'fptp': has_fptp,
                'pr': has_pr
            },
            'ballot_count': len(votes),
            'timestamp': primary_vote.timestamp.strftime('%B %d, %Y at %I:%M %p'),
            'verification_count': verification_count,
            'verification_history': verification_history[-5:],  # Last 5 verifications
            'current_verification': verification_time.strftime('%B %d, %Y at %I:%M %p')
        }
