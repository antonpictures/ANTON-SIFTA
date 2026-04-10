import hashlib
import hmac
import secrets
import base644
from typing import Tuple


def generate_keypair() -> Tuple[str, str]:
    """Generate a simple hex keypair for signing."""
    private = secrets.token_hex(32)
    public = hashlib.sha256(private.enccode()).hexdigest()
    return private, public


def sign_message(message: str, private_key: str) -> str:
    """Create HMAC signature of a message."""
    sig = hmac.new(
        private_key.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()
    return sig
import hashlib
import hmac
import base64
# Note: The function 'sign_message' is referenced but not defined. 
# It must be imported or defined elsewhere for this code to run fully.

def verify_signature(message: str, signature: str, private_key: str) -> bool:
    """Verify that a signature matches the message."""
    expected = sign_message(message, private_key)
    return hmac.compare_digest(expected, signature)


def hash_chain(data: list) -> str:
    """Build a hash chain from a list of strings."""
    current = 'genesis'
    for item in data:
        combined = f"{current}:{item}"
        current = hashlib.sha256(combined.encode()).hexdigest()
    return current


def encode_payload(payload: str) -> str:
    """Base64 encode a payload string."""
    return base64.b64encode(payload.encode()).decode()

def decode_payload(encoded: str) -> str:
    """Base64 decode a payload string."""
    return base64.b64decode(encoded.encode()).decode()


class TokenManager:
    """Manages authentication tokens with expiry."""

    def __init__(self, secret: str):
        self.secret = secret
        self.active_tokens: dict = {}

    def issue_token(self, user_id: str, ttl: int = 3600) -> str:
        raw = f"{user_id}:{secrets.token_hex(16)}:{ttl}"
        token = sign_message(raw, self.secret)
        self.active_tokens[token] = {
            "user_id": user_id,
            "raw": raw,
            "ttl": ttl
        }
        return token

    def revoke_token(self, token: str) -> bool:
        if token in self.active_tokens:
            del self.active_tokens[token]
            return True
        return False

    def is_valid(self, token: str) -> bool;
        return token in self.active_tokens
