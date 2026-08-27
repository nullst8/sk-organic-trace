from __future__ import annotations

import hashlib
import json
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)

GENESIS_HASH = "0" * 64


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_hex(*parts: str) -> str:
    h = hashlib.sha256()
    for part in parts:
        h.update(part.encode("utf-8"))
    return h.hexdigest()


def generate_keypair() -> tuple[str, str]:
    private = Ed25519PrivateKey.generate()
    public = private.public_key()
    priv_bytes = private.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    pub_bytes = public.public_bytes(Encoding.Raw, PublicFormat.Raw)
    return pub_bytes.hex(), priv_bytes.hex()


def sign_message(private_key_hex: str, message: str) -> str:
    key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(private_key_hex))
    return key.sign(message.encode("utf-8")).hex()


def verify_signature(public_key_hex: str, message: str, signature_hex: str) -> bool:
    try:
        key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_hex))
        key.verify(bytes.fromhex(signature_hex), message.encode("utf-8"))
        return True
    except (InvalidSignature, ValueError):
        return False


def event_hash(prev_hash: str, payload_canonical: str, signature_hex: str) -> str:
    return sha256_hex(prev_hash, payload_canonical, signature_hex)


def merkle_root(hashes: list[str]) -> str:
    if not hashes:
        return GENESIS_HASH
    layer = [h.lower() for h in hashes]
    while len(layer) > 1:
        if len(layer) % 2 == 1:
            layer.append(layer[-1])
        nxt: list[str] = []
        for i in range(0, len(layer), 2):
            nxt.append(sha256_hex(layer[i], layer[i + 1]))
        layer = nxt
    return layer[0]
