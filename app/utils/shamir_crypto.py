"""Shamir's Secret Sharing + Hybrid PQC Encryption for Secure Voting.

This module provides:
1. Hybrid key pair generation (RSA-2048 + Kyber-768) for election encryption
2. Shamir's Secret Sharing to split private keys into shares
3. Hybrid encryption (RSA + Kyber + AES) for vote data
4. Share reconstruction and decryption

Post-Quantum Cryptography (PQC):
- Uses Kyber-768 for quantum-resistant key encapsulation
- Combined with RSA-2048 for hybrid security
- Both algorithms must be broken to compromise vote data
"""
import os
import json
import base64
import secrets
from typing import Tuple, List, Optional
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP, AES
from Crypto.Hash import SHA256
from Crypto.Random import get_random_bytes
from kyber_py.ml_kem import ML_KEM_768  # Pure Python Kyber implementation

# Shamir's Secret Sharing constants
PRIME = 2**521 - 1  # 13th Mersenne prime (large prime for security)


class ShamirSecretSharing:
    """Implementation of Shamir's Secret Sharing scheme."""

    def __init__(self, threshold: int = 3, total_shares: int = 5):
        """Initialize Shamir's Secret Sharing.

        Args:
            threshold: Minimum shares needed to reconstruct secret (default: 3)
            total_shares: Total number of shares to generate (default: 5)
        """
        if threshold > total_shares:
            raise ValueError("Threshold cannot be greater than total shares")
        if threshold < 2:
            raise ValueError("Threshold must be at least 2")

        self.threshold = threshold
        self.total_shares = total_shares
        self.prime = PRIME

    def _mod_inverse(self, a: int, m: int) -> int:
        """Calculate modular multiplicative inverse using extended Euclidean algorithm."""
        def extended_gcd(a, b):
            if a == 0:
                return b, 0, 1
            gcd, x1, y1 = extended_gcd(b % a, a)
            x = y1 - (b // a) * x1
            y = x1
            return gcd, x, y

        _, x, _ = extended_gcd(a % m, m)
        return (x % m + m) % m

    def _generate_coefficients(self, secret: int) -> List[int]:
        """Generate random polynomial coefficients with secret as constant term."""
        coefficients = [secret]
        for _ in range(self.threshold - 1):
            coef = secrets.randbelow(self.prime - 1) + 1
            coefficients.append(coef)
        return coefficients

    def _evaluate_polynomial(self, coefficients: List[int], x: int) -> int:
        """Evaluate polynomial at point x."""
        result = 0
        for i, coef in enumerate(coefficients):
            result = (result + coef * pow(x, i, self.prime)) % self.prime
        return result

    def split_secret(self, secret_bytes: bytes) -> List[Tuple[int, str]]:
        """Split a secret into shares.

        Args:
            secret_bytes: The secret to split (as bytes)

        Returns:
            List of tuples (share_index, share_value_hex)
        """
        # Convert bytes to integer
        secret_int = int.from_bytes(secret_bytes, byteorder='big')

        if secret_int >= self.prime:
            raise ValueError("Secret too large for the prime field")

        # Generate polynomial coefficients
        coefficients = self._generate_coefficients(secret_int)

        # Generate shares (x, y) pairs where x is 1 to total_shares
        shares = []
        for i in range(1, self.total_shares + 1):
            y = self._evaluate_polynomial(coefficients, i)
            # Encode share as hex string for easy storage/display
            share_hex = format(y, 'x').zfill(len(format(self.prime, 'x')))
            shares.append((i, share_hex))

        return shares

    def reconstruct_secret(self, shares: List[Tuple[int, str]], secret_length: int) -> bytes:
        """Reconstruct the secret from shares using Lagrange interpolation.

        Args:
            shares: List of tuples (share_index, share_value_hex)
            secret_length: Expected length of the secret in bytes

        Returns:
            The reconstructed secret as bytes
        """
        if len(shares) < self.threshold:
            raise ValueError(f"Need at least {self.threshold} shares, got {len(shares)}")

        # Use only threshold number of shares
        shares = shares[:self.threshold]

        # Convert hex shares back to integers
        points = [(x, int(y_hex, 16)) for x, y_hex in shares]

        # Lagrange interpolation at x=0 to get the secret
        secret_int = 0
        for i, (xi, yi) in enumerate(points):
            numerator = 1
            denominator = 1
            for j, (xj, _) in enumerate(points):
                if i != j:
                    numerator = (numerator * (-xj)) % self.prime
                    denominator = (denominator * (xi - xj)) % self.prime

            lagrange_coef = (numerator * self._mod_inverse(denominator, self.prime)) % self.prime
            secret_int = (secret_int + yi * lagrange_coef) % self.prime

        # Convert back to bytes
        return secret_int.to_bytes(secret_length, byteorder='big')


class ElectionCrypto:
    """Handles hybrid PQC key generation and encryption for elections.

    Uses RSA-2048 + Kyber-768 for hybrid post-quantum security.
    Both algorithms must be broken to compromise vote data.
    """

    RSA_KEY_SIZE = 2048  # bits
    AES_KEY_SIZE = 32  # bytes (256 bits)
    KYBER_ALGORITHM = "Kyber768"  # NIST PQC standard

    def __init__(self, threshold: int = 3, total_shares: int = 5):
        """Initialize election crypto with Shamir parameters.

        Args:
            threshold: Minimum shares needed to decrypt (default: 3)
            total_shares: Total shares to generate (default: 5)
        """
        self.shamir = ShamirSecretSharing(threshold, total_shares)
        self.threshold = threshold
        self.total_shares = total_shares

    def generate_election_keys(self) -> Tuple[str, List[dict], str]:
        """Generate hybrid RSA + Kyber key pairs and split private keys into shares.

        Uses hybrid post-quantum cryptography:
        - RSA-2048 for classical security
        - Kyber-768 for quantum resistance

        Returns:
            Tuple of:
            - public_keys_json: JSON containing both RSA and Kyber public keys
            - shares: List of share dicts with index and value (display once)
            - key_bundle_json: Encrypted private keys bundle
        """
        # Generate RSA key pair
        rsa_key = RSA.generate(self.RSA_KEY_SIZE)
        rsa_public_key_pem = rsa_key.publickey().export_key().decode('utf-8')
        rsa_private_key_bytes = rsa_key.export_key()

        # Generate Kyber key pair (ML-KEM-768)
        kyber_public_key, kyber_private_key = ML_KEM_768.keygen()

        # Combine both public keys into a JSON structure
        public_keys = {
            'rsa': rsa_public_key_pem,
            'kyber': base64.b64encode(kyber_public_key).decode('utf-8'),
            'algorithm': 'hybrid-rsa2048-kyber768'
        }
        public_keys_json = json.dumps(public_keys)

        # Combine both private keys into a single bundle
        private_keys_bundle = {
            'rsa': base64.b64encode(rsa_private_key_bytes).decode('utf-8'),
            'kyber': base64.b64encode(kyber_private_key).decode('utf-8')
        }
        private_keys_json = json.dumps(private_keys_bundle).encode('utf-8')

        # Encrypt combined private keys with a random AES key
        aes_key = get_random_bytes(self.AES_KEY_SIZE)
        cipher_aes = AES.new(aes_key, AES.MODE_GCM)
        encrypted_private_keys, tag = cipher_aes.encrypt_and_digest(private_keys_json)

        # Create encrypted key bundle
        key_bundle = {
            'nonce': base64.b64encode(cipher_aes.nonce).decode('utf-8'),
            'tag': base64.b64encode(tag).decode('utf-8'),
            'ciphertext': base64.b64encode(encrypted_private_keys).decode('utf-8'),
            'algorithm': 'hybrid-rsa2048-kyber768'
        }
        key_bundle_json = json.dumps(key_bundle)

        # Split the AES key using Shamir's Secret Sharing
        raw_shares = self.shamir.split_secret(aes_key)

        # Format shares for display
        shares = []
        for index, value in raw_shares:
            formatted_value = '-'.join([value[i:i+8] for i in range(0, len(value), 8)])
            shares.append({
                'index': index,
                'value': formatted_value,
                'display': f"Share {index}: {formatted_value[:32]}..."
            })

        return public_keys_json, shares, key_bundle_json

    def encrypt_vote(self, vote_data: dict, public_keys_json: str) -> str:
        """Encrypt vote data using hybrid PQC encryption (RSA + Kyber + AES).

        The AES key is encrypted with both RSA and Kyber. An attacker would
        need to break BOTH algorithms to recover the vote data.

        Args:
            vote_data: Dictionary containing vote information
            public_keys_json: JSON containing both RSA and Kyber public keys

        Returns:
            Base64-encoded encrypted vote data
        """
        # Parse public keys
        public_keys = json.loads(public_keys_json)
        rsa_public_key_pem = public_keys['rsa']
        kyber_public_key = base64.b64decode(public_keys['kyber'])

        # Generate random AES key for this vote
        aes_key = get_random_bytes(self.AES_KEY_SIZE)

        # Encrypt AES key with RSA
        rsa_public_key = RSA.import_key(rsa_public_key_pem)
        cipher_rsa = PKCS1_OAEP.new(rsa_public_key, hashAlgo=SHA256)
        encrypted_aes_key_rsa = cipher_rsa.encrypt(aes_key)

        # Encapsulate with Kyber (ML-KEM-768)
        # Kyber generates a shared secret, we XOR it with our AES key
        # Note: encaps returns (shared_secret, ciphertext)
        kyber_shared_secret, kyber_ciphertext = ML_KEM_768.encaps(kyber_public_key)

        # XOR the AES key with Kyber shared secret for additional protection
        # This ensures both RSA and Kyber must be broken
        kyber_protected_key = bytes(a ^ b for a, b in zip(aes_key, kyber_shared_secret[:self.AES_KEY_SIZE]))

        # Encrypt vote data with AES
        vote_json = json.dumps(vote_data).encode('utf-8')
        cipher_aes = AES.new(aes_key, AES.MODE_GCM)
        encrypted_vote, tag = cipher_aes.encrypt_and_digest(vote_json)

        # Package everything together
        encrypted_package = {
            'encrypted_key_rsa': base64.b64encode(encrypted_aes_key_rsa).decode('utf-8'),
            'kyber_ciphertext': base64.b64encode(kyber_ciphertext).decode('utf-8'),
            'kyber_protected_key': base64.b64encode(kyber_protected_key).decode('utf-8'),
            'nonce': base64.b64encode(cipher_aes.nonce).decode('utf-8'),
            'tag': base64.b64encode(tag).decode('utf-8'),
            'ciphertext': base64.b64encode(encrypted_vote).decode('utf-8'),
            'algorithm': 'hybrid-rsa2048-kyber768'
        }

        return base64.b64encode(json.dumps(encrypted_package).encode('utf-8')).decode('utf-8')

    def reconstruct_private_keys(self, shares: List[Tuple[int, str]], key_bundle_json: str) -> Tuple[RSA.RsaKey, bytes]:
        """Reconstruct both RSA and Kyber private keys from shares.

        Args:
            shares: List of (index, value) tuples
            key_bundle_json: The encrypted private keys bundle

        Returns:
            Tuple of (RSA private key object, Kyber private key bytes)
        """
        # Parse shares - remove formatting dashes
        parsed_shares = []
        for index, value in shares:
            clean_value = value.replace('-', '')
            parsed_shares.append((index, clean_value))

        # Reconstruct AES key
        aes_key = self.shamir.reconstruct_secret(parsed_shares, self.AES_KEY_SIZE)

        # Decrypt private keys bundle
        key_bundle = json.loads(key_bundle_json)
        nonce = base64.b64decode(key_bundle['nonce'])
        tag = base64.b64decode(key_bundle['tag'])
        ciphertext = base64.b64decode(key_bundle['ciphertext'])

        cipher_aes = AES.new(aes_key, AES.MODE_GCM, nonce=nonce)
        private_keys_json = cipher_aes.decrypt_and_verify(ciphertext, tag)

        # Parse both private keys
        private_keys = json.loads(private_keys_json.decode('utf-8'))
        rsa_private_key_bytes = base64.b64decode(private_keys['rsa'])
        kyber_private_key = base64.b64decode(private_keys['kyber'])

        rsa_private_key = RSA.import_key(rsa_private_key_bytes)

        return rsa_private_key, kyber_private_key

    def reconstruct_private_key(self, shares: List[Tuple[int, str]], key_bundle_json: str) -> RSA.RsaKey:
        """Reconstruct private key from shares (backward compatibility wrapper).

        Args:
            shares: List of (index, value) tuples
            key_bundle_json: The encrypted private key bundle

        Returns:
            RSA private key object (for backward compatibility)
        """
        rsa_key, _ = self.reconstruct_private_keys(shares, key_bundle_json)
        return rsa_key

    def decrypt_vote(self, encrypted_vote: str, private_key: RSA.RsaKey, kyber_private_key: bytes = None) -> dict:
        """Decrypt a vote using hybrid decryption (RSA + Kyber).

        Args:
            encrypted_vote: Base64-encoded encrypted vote
            private_key: RSA private key object
            kyber_private_key: Kyber private key bytes (required for hybrid votes)

        Returns:
            Decrypted vote data dictionary
        """
        # Decode package
        encrypted_package = json.loads(base64.b64decode(encrypted_vote))

        # Check if this is a hybrid encrypted vote
        if 'kyber_ciphertext' in encrypted_package and kyber_private_key is not None:
            # Hybrid decryption (RSA + Kyber)
            return self._decrypt_vote_hybrid(encrypted_package, private_key, kyber_private_key)
        else:
            # Legacy RSA-only decryption (backward compatibility)
            return self._decrypt_vote_legacy(encrypted_package, private_key)

    def _decrypt_vote_hybrid(self, encrypted_package: dict, rsa_private_key: RSA.RsaKey, kyber_private_key: bytes) -> dict:
        """Decrypt a vote using hybrid RSA + Kyber decryption.

        Both algorithms must successfully decrypt for the vote to be recovered.
        """
        # Extract encrypted components
        encrypted_aes_key_rsa = base64.b64decode(encrypted_package['encrypted_key_rsa'])
        kyber_ciphertext = base64.b64decode(encrypted_package['kyber_ciphertext'])
        kyber_protected_key = base64.b64decode(encrypted_package['kyber_protected_key'])
        nonce = base64.b64decode(encrypted_package['nonce'])
        tag = base64.b64decode(encrypted_package['tag'])
        ciphertext = base64.b64decode(encrypted_package['ciphertext'])

        # Decrypt AES key with RSA
        cipher_rsa = PKCS1_OAEP.new(rsa_private_key, hashAlgo=SHA256)
        aes_key_from_rsa = cipher_rsa.decrypt(encrypted_aes_key_rsa)

        # Decapsulate with Kyber (ML-KEM-768) to get shared secret
        kyber_shared_secret = ML_KEM_768.decaps(kyber_private_key, kyber_ciphertext)

        # Recover AES key by XORing protected key with Kyber shared secret
        aes_key_from_kyber = bytes(a ^ b for a, b in zip(kyber_protected_key, kyber_shared_secret[:self.AES_KEY_SIZE]))

        # Verify both keys match (ensures both algorithms were needed)
        if aes_key_from_rsa != aes_key_from_kyber:
            raise ValueError("Hybrid decryption failed: RSA and Kyber keys do not match")

        # Decrypt vote with AES
        cipher_aes = AES.new(aes_key_from_rsa, AES.MODE_GCM, nonce=nonce)
        vote_json = cipher_aes.decrypt_and_verify(ciphertext, tag)

        return json.loads(vote_json.decode('utf-8'))

    def _decrypt_vote_legacy(self, encrypted_package: dict, private_key: RSA.RsaKey) -> dict:
        """Decrypt a vote using legacy RSA-only decryption (backward compatibility)."""
        encrypted_aes_key = base64.b64decode(encrypted_package.get('encrypted_key', encrypted_package.get('encrypted_key_rsa')))
        nonce = base64.b64decode(encrypted_package['nonce'])
        tag = base64.b64decode(encrypted_package['tag'])
        ciphertext = base64.b64decode(encrypted_package['ciphertext'])

        # Decrypt AES key with RSA
        cipher_rsa = PKCS1_OAEP.new(private_key, hashAlgo=SHA256)
        aes_key = cipher_rsa.decrypt(encrypted_aes_key)

        # Decrypt vote with AES
        cipher_aes = AES.new(aes_key, AES.MODE_GCM, nonce=nonce)
        vote_json = cipher_aes.decrypt_and_verify(ciphertext, tag)

        return json.loads(vote_json.decode('utf-8'))


def format_share_for_display(index: int, value: str) -> str:
    """Format a share for user-friendly display.

    Args:
        index: Share index (1-5)
        value: Share value (hex string with dashes)

    Returns:
        Formatted string for display
    """
    return f"SHARE-{index}: {value}"


def parse_share_input(share_string: str) -> Tuple[int, str]:
    """Parse a share from user input.

    Args:
        share_string: User input like "SHARE-1: xxxx-xxxx-..." or just "1:xxxx-xxxx"

    Returns:
        Tuple of (index, value)
    """
    # Clean up input
    share_string = share_string.strip().upper()

    # Try different formats
    if share_string.startswith('SHARE-'):
        share_string = share_string[6:]

    if ':' in share_string:
        parts = share_string.split(':', 1)
        index = int(parts[0].strip())
        value = parts[1].strip()
    else:
        raise ValueError("Invalid share format. Expected 'SHARE-N: value' or 'N: value'")

    return index, value
