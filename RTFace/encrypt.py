"""Encryption module to encrypt blurred faces if enabled.
"""

from Crypto.Cipher import AES
import os

# the block size for the cipher object; must be 16, 24, or 32 for AES
BLOCK_SIZE = 32
# the character used for padding--with a block cipher such as AES, the value
# you encrypt must be a multiple of BLOCK_SIZE in length.  This character is
# used to ensure that your value is always a multiple of BLOCK_SIZE
PADDING = '{'
# one-liner to sufficiently pad the text to be encrypted


def pad(s): return s + (BLOCK_SIZE - len(s) % BLOCK_SIZE) * PADDING


# one-liners to encrypt/encode and decrypt/decode a string
# encrypt with AES, encode with base64
def encode_aes(c, s): return c.encrypt(pad(s))


def decode_aes(c, e): return c.decrypt(e).rstrip(PADDING)


def create_cipher(secret): return AES.new(secret)


def create_secret(output_path=None):
    secret = os.urandom(BLOCK_SIZE)
    if output_path:
        with open(output_path, 'w+') as f:
            f.write(secret)
    return secret
