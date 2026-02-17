"""Audit log model for tracking security-relevant events."""
import hashlib
import json
from datetime import datetime
from bson import ObjectId
from app import get_db


class AuditLog:
    """Model for storing audit trail of security-relevant events.

    Tracks actions like login attempts, vote casting, election creation,
    and administrative actions for security monitoring and compliance.
    """

    collection_name = 'audit_logs'

    # Event categories
    CATEGORY_AUTH = 'authentication'
    CATEGORY_VOTE = 'voting'
    CATEGORY_ELECTION = 'election'
    CATEGORY_ADMIN = 'administration'
    CATEGORY_SECURITY = 'security'

    # Event types
    EVENT_LOGIN_SUCCESS = 'login_success'
    EVENT_LOGIN_FAILED = 'login_failed'
    EVENT_LOGOUT = 'logout'
    EVENT_REGISTER = 'register'
    EVENT_VOTE_CAST = 'vote_cast'
    EVENT_TOKEN_ISSUED = 'token_issued'
    EVENT_ELECTION_CREATED = 'election_created'
    EVENT_ELECTION_DEACTIVATED = 'election_deactivated'
    EVENT_RATE_LIMIT_TRIGGERED = 'rate_limit_triggered'
    EVENT_ADMIN_ACTION = 'admin_action'

    # Genesis hash for the first entry in the chain
    GENESIS_HASH = "GENESIS"

    def __init__(self, category: str, event_type: str, message: str,
                 user_id: str = None, user_type: str = None,
                 ip_address: str = None, user_agent: str = None,
                 details: dict = None, timestamp: datetime = None,
                 entry_hash: str = None, previous_hash: str = None,
                 _id=None):
        self._id = _id
        self.category = category
        self.event_type = event_type
        self.message = message
        self.user_id = user_id  # voter_id or admin username
        self.user_type = user_type  # 'voter', 'admin', or None
        self.ip_address = ip_address
        self.user_agent = user_agent
        self.details = details or {}  # Additional event-specific data
        self.timestamp = timestamp or datetime.utcnow()
        self.entry_hash = entry_hash  # SHA-256 hash of this entry
        self.previous_hash = previous_hash  # Hash of the previous entry (chain link)

    def to_dict(self) -> dict:
        """Convert audit log entry to dictionary."""
        data = {
            'category': self.category,
            'event_type': self.event_type,
            'message': self.message,
            'user_id': self.user_id,
            'user_type': self.user_type,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'details': self.details,
            'timestamp': self.timestamp,
            'entry_hash': self.entry_hash,
            'previous_hash': self.previous_hash
        }
        if self._id:
            data['_id'] = self._id
        return data

    @classmethod
    def from_dict(cls, data: dict):
        """Create AuditLog from dictionary."""
        if not data:
            return None
        return cls(
            category=data.get('category'),
            event_type=data.get('event_type'),
            message=data.get('message'),
            user_id=data.get('user_id'),
            user_type=data.get('user_type'),
            ip_address=data.get('ip_address'),
            user_agent=data.get('user_agent'),
            details=data.get('details'),
            timestamp=data.get('timestamp'),
            entry_hash=data.get('entry_hash'),
            previous_hash=data.get('previous_hash'),
            _id=data.get('_id')
        )

    def _compute_hash(self) -> str:
        """Compute SHA-256 hash of this entry's data including previous hash."""
        # Normalize timestamp to seconds (consistent format for hashing)
        if self.timestamp:
            normalized_ts = self.timestamp.replace(microsecond=0).strftime('%Y-%m-%dT%H:%M:%S')
        else:
            normalized_ts = None

        data = {
            'category': self.category,
            'event_type': self.event_type,
            'message': self.message,
            'user_id': self.user_id,
            'user_type': self.user_type,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'details': self.details,
            'timestamp': normalized_ts,
            'previous_hash': self.previous_hash
        }
        data_str = json.dumps(data, sort_keys=True)
        return hashlib.sha256(data_str.encode()).hexdigest()

    @classmethod
    def _get_latest_hash(cls) -> str:
        """Get the hash of the most recent audit log entry."""
        db = get_db()
        latest = db[cls.collection_name].find_one(
            {'entry_hash': {'$exists': True}},
            sort=[('timestamp', -1)]
        )
        if latest and latest.get('entry_hash'):
            return latest['entry_hash']
        return cls.GENESIS_HASH

    def save(self):
        """Save audit log entry to database with hash chain."""
        db = get_db()

        # Set previous hash if not already set
        if self.previous_hash is None:
            self.previous_hash = self._get_latest_hash()

        # Compute this entry's hash
        self.entry_hash = self._compute_hash()

        result = db[self.collection_name].insert_one(self.to_dict())
        self._id = result.inserted_id
        return self

    @classmethod
    def log(cls, category: str, event_type: str, message: str,
            user_id: str = None, user_type: str = None,
            ip_address: str = None, user_agent: str = None,
            details: dict = None):
        """Create and save an audit log entry.

        Args:
            category: Event category (auth, vote, election, admin, security)
            event_type: Specific event type
            message: Human-readable event description
            user_id: ID of the user who triggered the event
            user_type: Type of user ('voter' or 'admin')
            ip_address: Client IP address
            user_agent: Client user agent string
            details: Additional event-specific data

        Returns:
            The created AuditLog instance
        """
        entry = cls(
            category=category,
            event_type=event_type,
            message=message,
            user_id=user_id,
            user_type=user_type,
            ip_address=ip_address,
            user_agent=user_agent,
            details=details
        )
        return entry.save()

    @classmethod
    def get_by_user(cls, user_id: str, limit: int = 100) -> list:
        """Get audit logs for a specific user."""
        db = get_db()
        logs = db[cls.collection_name].find(
            {'user_id': user_id}
        ).sort('timestamp', -1).limit(limit)
        return [cls.from_dict(log) for log in logs]

    @classmethod
    def get_by_category(cls, category: str, limit: int = 100) -> list:
        """Get audit logs for a specific category."""
        db = get_db()
        logs = db[cls.collection_name].find(
            {'category': category}
        ).sort('timestamp', -1).limit(limit)
        return [cls.from_dict(log) for log in logs]

    @classmethod
    def get_by_event_type(cls, event_type: str, limit: int = 100) -> list:
        """Get audit logs for a specific event type."""
        db = get_db()
        logs = db[cls.collection_name].find(
            {'event_type': event_type}
        ).sort('timestamp', -1).limit(limit)
        return [cls.from_dict(log) for log in logs]

    @classmethod
    def get_recent(cls, limit: int = 100) -> list:
        """Get the most recent audit logs."""
        db = get_db()
        logs = db[cls.collection_name].find().sort('timestamp', -1).limit(limit)
        return [cls.from_dict(log) for log in logs]

    @classmethod
    def get_security_events(cls, limit: int = 100) -> list:
        """Get security-related events (failed logins, rate limits, etc.)."""
        db = get_db()
        logs = db[cls.collection_name].find({
            '$or': [
                {'category': cls.CATEGORY_SECURITY},
                {'event_type': cls.EVENT_LOGIN_FAILED},
                {'event_type': cls.EVENT_RATE_LIMIT_TRIGGERED}
            ]
        }).sort('timestamp', -1).limit(limit)
        return [cls.from_dict(log) for log in logs]

    @classmethod
    def get_by_ip(cls, ip_address: str, limit: int = 100) -> list:
        """Get audit logs from a specific IP address."""
        db = get_db()
        logs = db[cls.collection_name].find(
            {'ip_address': ip_address}
        ).sort('timestamp', -1).limit(limit)
        return [cls.from_dict(log) for log in logs]

    @classmethod
    def count_failed_logins(cls, hours: int = 24) -> int:
        """Count failed login attempts in the last N hours."""
        from datetime import timedelta
        db = get_db()
        since = datetime.utcnow() - timedelta(hours=hours)
        return db[cls.collection_name].count_documents({
            'event_type': cls.EVENT_LOGIN_FAILED,
            'timestamp': {'$gte': since}
        })

    @classmethod
    def get_login_stats(cls, hours: int = 24) -> dict:
        """Get login statistics for the last N hours."""
        from datetime import timedelta
        db = get_db()
        since = datetime.utcnow() - timedelta(hours=hours)

        pipeline = [
            {'$match': {
                'event_type': {'$in': [cls.EVENT_LOGIN_SUCCESS, cls.EVENT_LOGIN_FAILED]},
                'timestamp': {'$gte': since}
            }},
            {'$group': {
                '_id': '$event_type',
                'count': {'$sum': 1}
            }}
        ]

        results = list(db[cls.collection_name].aggregate(pipeline))
        stats = {cls.EVENT_LOGIN_SUCCESS: 0, cls.EVENT_LOGIN_FAILED: 0}
        for r in results:
            stats[r['_id']] = r['count']

        return {
            'successful_logins': stats[cls.EVENT_LOGIN_SUCCESS],
            'failed_logins': stats[cls.EVENT_LOGIN_FAILED],
            'period_hours': hours
        }

    # Hash chain verification methods

    @classmethod
    def verify_chain(cls, limit: int = None) -> dict:
        """Verify the integrity of the hash chain.

        Args:
            limit: Maximum number of entries to verify (None = all)

        Returns:
            dict with:
                - valid: bool - whether the chain is intact
                - entries_checked: int - number of entries verified
                - first_invalid_id: ObjectId or None - ID of first tampered entry
                - error: str or None - error message if invalid
        """
        db = get_db()

        # Get entries in chronological order (oldest first)
        query = {'entry_hash': {'$exists': True}}
        cursor = db[cls.collection_name].find(query).sort('timestamp', 1)

        if limit:
            cursor = cursor.limit(limit)

        entries = list(cursor)
        entries_checked = 0
        expected_previous_hash = cls.GENESIS_HASH

        for entry in entries:
            entries_checked += 1

            # Check if previous_hash matches expected
            if entry.get('previous_hash') != expected_previous_hash:
                return {
                    'valid': False,
                    'entries_checked': entries_checked,
                    'first_invalid_id': entry.get('_id'),
                    'error': f"Chain break: previous_hash mismatch at entry {entry.get('_id')}"
                }

            # Recompute hash and verify
            log_entry = cls.from_dict(entry)
            computed_hash = log_entry._compute_hash()

            if computed_hash != entry.get('entry_hash'):
                return {
                    'valid': False,
                    'entries_checked': entries_checked,
                    'first_invalid_id': entry.get('_id'),
                    'error': f"Hash mismatch: entry {entry.get('_id')} was tampered with"
                }

            # Update expected previous hash for next iteration
            expected_previous_hash = entry.get('entry_hash')

        return {
            'valid': True,
            'entries_checked': entries_checked,
            'first_invalid_id': None,
            'error': None
        }

    @classmethod
    def get_chain_status(cls) -> dict:
        """Get the current status of the hash chain.

        Returns:
            dict with:
                - total_entries: int - total audit log entries
                - chain_entries: int - entries with hash chain
                - legacy_entries: int - entries without hash chain (pre-implementation)
                - latest_hash: str - hash of the most recent entry
                - chain_intact: bool - whether verification passed
        """
        db = get_db()

        total_entries = db[cls.collection_name].count_documents({})
        chain_entries = db[cls.collection_name].count_documents({'entry_hash': {'$exists': True}})
        legacy_entries = total_entries - chain_entries

        latest_hash = cls._get_latest_hash()

        # Verify chain integrity (limit to last 1000 for performance)
        verification = cls.verify_chain(limit=1000)

        return {
            'total_entries': total_entries,
            'chain_entries': chain_entries,
            'legacy_entries': legacy_entries,
            'latest_hash': latest_hash,
            'chain_intact': verification['valid'],
            'verification_details': verification
        }
