import base64

import frappe
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_CACHE_KEY = "activity_tracker_key_b64"
_cached_key_b64 = None
_cached_aes = None
_cached_aes_key_b64 = None


def _get_cache():
    cache = getattr(frappe, "cache", None)
    if callable(cache):
        return cache()
    return cache


def get_tracker_key_cache_ttl() -> int:
    ttl = frappe.get_site_config().get("activity_tracker_key_cache_ttl", 300)
    try:
        return max(int(ttl), 1)
    except (TypeError, ValueError):
        return 300


def get_activity_tracker_key_b64() -> str:
    global _cached_key_b64

    if _cached_key_b64:
        return _cached_key_b64

    cache = _get_cache()
    cached_value = cache.get_value(_CACHE_KEY) if cache else None
    if cached_value:
        if isinstance(cached_value, bytes):
            cached_value = cached_value.decode("utf-8")
        _cached_key_b64 = cached_value
        return _cached_key_b64

    key_b64 = frappe.get_site_config().get("activity_tracker_key_b64")
    if not key_b64:
        raise Exception("AES key missing in site_config.json")

    if cache:
        cache.set_value(_CACHE_KEY, key_b64, expires_in_sec=get_tracker_key_cache_ttl())

    _cached_key_b64 = key_b64
    return key_b64


def clear_activity_tracker_key_cache() -> None:
    global _cached_key_b64, _cached_aes, _cached_aes_key_b64

    cache = _get_cache()
    if cache:
        cache.delete_value(_CACHE_KEY)

    _cached_key_b64 = None
    _cached_aes = None
    _cached_aes_key_b64 = None


def get_aes() -> AESGCM:
    global _cached_aes, _cached_aes_key_b64

    key_b64 = get_activity_tracker_key_b64()
    if _cached_aes and _cached_aes_key_b64 == key_b64:
        return _cached_aes

    key = base64.b64decode(key_b64)
    aes = AESGCM(key)
    _cached_aes = aes
    _cached_aes_key_b64 = key_b64
    return aes


def decrypt_payload(payload):
    aes = get_aes()
    nonce = base64.b64decode(payload["nonce"])
    ciphertext = base64.b64decode(payload["ciphertext"])
    plaintext = aes.decrypt(nonce, ciphertext, associated_data=None)
    return plaintext
