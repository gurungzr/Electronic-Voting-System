import bcrypt
import secrets
import hashlib
import base64
import os
import json
from datetime import datetime
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# Encryption key management
_encryption_key = None


def _get_encryption_key() -> bytes:
    """Get or generate the encryption key for vote data.

    Uses VOTE_ENCRYPTION_KEY from environment or derives from SECRET_KEY.
    """
    global _encryption_key
    if _encryption_key is not None:
        return _encryption_key

    # Try to get dedicated encryption key from environment
    key = os.environ.get('VOTE_ENCRYPTION_KEY')
    if key:
        # Ensure it's valid Fernet key (32 bytes, base64 encoded)
        try:
            _encryption_key = key.encode('utf-8')
            Fernet(_encryption_key)  # Validate key
            return _encryption_key
        except Exception:
            pass

    # Derive key from SECRET_KEY using PBKDF2
    secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    salt = b'secure_voting_system_salt_v1'  # Static salt for consistent key derivation

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key_bytes = kdf.derive(secret_key.encode('utf-8'))
    _encryption_key = base64.urlsafe_b64encode(key_bytes)
    return _encryption_key


def hash_password(password: str) -> str:
    """Hash a password using bcrypt with salt."""
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against its hash."""
    return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))


def generate_voter_id() -> str:
    """Generate a unique voter ID.

    Format: VTR-XXXXXXXX (8 random alphanumeric characters)
    """
    random_part = secrets.token_hex(4).upper()
    return f"VTR-{random_part}"


def hash_citizenship_number(citizenship_number: str) -> str:
    """Hash citizenship number for privacy.

    Uses SHA-256 for one-way hashing to prevent reverse lookup
    while still allowing verification.
    """
    return hashlib.sha256(citizenship_number.encode('utf-8')).hexdigest()


def generate_election_id() -> str:
    """Generate a unique election ID.

    Format: ELC-YYYYMMDD-XXXX
    """
    date_part = datetime.now().strftime('%Y%m%d')
    random_part = secrets.token_hex(2).upper()
    return f"ELC-{date_part}-{random_part}"


def generate_candidate_id() -> str:
    """Generate a unique candidate ID.

    Format: CND-XXXXXX
    """
    random_part = secrets.token_hex(3).upper()
    return f"CND-{random_part}"


def generate_party_id() -> str:
    """Generate a unique party ID for PR ballot.

    Format: PTY-XXXXXX
    """
    random_part = secrets.token_hex(3).upper()
    return f"PTY-{random_part}"


def generate_vote_token() -> str:
    """Generate a unique vote token for future blockchain integration.

    Format: 64-character hex string
    """
    return secrets.token_hex(32)


def encrypt_vote(vote_data: dict, encryption_key: bytes = None) -> dict:
    """Encrypt sensitive vote data using Fernet symmetric encryption.

    Encrypts the candidate_id and party_id fields while preserving
    non-sensitive metadata for aggregation queries.

    Args:
        vote_data: Dictionary containing vote information
        encryption_key: Optional custom encryption key (uses default if not provided)

    Returns:
        Dictionary with encrypted sensitive fields and 'is_encrypted' flag
    """
    if not vote_data:
        return vote_data

    key = encryption_key or _get_encryption_key()
    fernet = Fernet(key)

    # Create a copy to avoid modifying original
    encrypted_data = vote_data.copy()

    # Fields to encrypt (sensitive vote choices)
    sensitive_fields = ['candidate_id', 'party_id']

    for field in sensitive_fields:
        if field in encrypted_data and encrypted_data[field]:
            # Encrypt the field value
            plaintext = str(encrypted_data[field]).encode('utf-8')
            encrypted_data[field] = fernet.encrypt(plaintext).decode('utf-8')

    # Mark as encrypted for verification
    encrypted_data['is_encrypted'] = True

    return encrypted_data


def decrypt_vote(encrypted_vote: dict, encryption_key: bytes = None) -> dict:
    """Decrypt vote data that was encrypted with encrypt_vote.

    Args:
        encrypted_vote: Dictionary containing encrypted vote information
        encryption_key: Optional custom encryption key (uses default if not provided)

    Returns:
        Dictionary with decrypted sensitive fields
    """
    if not encrypted_vote:
        return encrypted_vote

    # If not encrypted, return as-is
    if not encrypted_vote.get('is_encrypted'):
        return encrypted_vote

    key = encryption_key or _get_encryption_key()
    fernet = Fernet(key)

    # Create a copy to avoid modifying original
    decrypted_data = encrypted_vote.copy()

    # Fields to decrypt
    sensitive_fields = ['candidate_id', 'party_id']

    for field in sensitive_fields:
        if field in decrypted_data and decrypted_data[field]:
            try:
                # Decrypt the field value
                ciphertext = decrypted_data[field].encode('utf-8')
                decrypted_data[field] = fernet.decrypt(ciphertext).decode('utf-8')
            except Exception:
                # If decryption fails, field might not be encrypted
                pass

    # Remove encryption flag
    decrypted_data.pop('is_encrypted', None)

    return decrypted_data


def generate_encryption_key() -> str:
    """Generate a new Fernet encryption key.

    Use this to generate a VOTE_ENCRYPTION_KEY for production.

    Returns:
        Base64-encoded encryption key string
    """
    return Fernet.generate_key().decode('utf-8')
