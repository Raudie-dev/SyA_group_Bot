import os
import base64
from cryptography.fernet import Fernet
import hashlib

def _get_fernet():
    secret = os.environ.get('SECRET_KEY', 'fallback-insecure-key')
    key = hashlib.sha256(secret.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))

def encrypt_value(plain_text):
    if not plain_text:
        return plain_text
    return _get_fernet().encrypt(plain_text.encode()).decode()

def decrypt_value(cipher_text):
    if not cipher_text:
        return cipher_text
    try:
        return _get_fernet().decrypt(cipher_text.encode()).decode()
    except Exception:
        return cipher_text  # fallback: devuelve tal cual (keys viejas sin cifrar)