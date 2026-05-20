import base64
import frappe
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

def get_aes():
    """Load AES key from site_config.json and return AESGCM instance."""
    key_b64 = frappe.get_site_config().get("activity_tracker_key_b64")
    if not key_b64:
        raise Exception("AES key missing in site_config.json")

    key = base64.b64decode(key_b64)
    aes = AESGCM(key)
    return aes

def decrypt_payload(payload):
    """
    payload = { "nonce": "...", "ciphertext": "..." }
    return plaintext bytes
    """
    aes = get_aes()
    nonce = base64.b64decode(payload["nonce"])
    ciphertext = base64.b64decode(payload["ciphertext"])
    plaintext = aes.decrypt(nonce, ciphertext, associated_data=None)
    return plaintext
