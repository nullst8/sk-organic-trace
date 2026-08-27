import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.crypto_chain import (  # noqa: E402
    GENESIS_HASH,
    canonical_json,
    event_hash,
    generate_keypair,
    merkle_root,
    sha256_hex,
    sign_message,
    verify_signature,
)


def test_canonical_json_is_stable():
    a = canonical_json({"b": 1, "a": [3, 2], "c": {"z": 0, "y": 1}})
    b = canonical_json({"c": {"y": 1, "z": 0}, "a": [3, 2], "b": 1})
    assert a == b
    assert a == '{"a":[3,2],"b":1,"c":{"y":1,"z":0}}'


def test_sha256_hex_is_deterministic():
    assert sha256_hex("a", "b") == sha256_hex("a", "b")
    assert len(sha256_hex("x")) == 64
    assert sha256_hex("a", "b") != sha256_hex("b", "a")


def test_keypair_sign_verify_roundtrip():
    pub, priv = generate_keypair()
    assert len(pub) == 64
    assert len(priv) == 64
    sig = sign_message(priv, "hello")
    assert verify_signature(pub, "hello", sig) is True


def test_bad_signature_or_wrong_key_fails():
    pub, priv = generate_keypair()
    _, other_priv = generate_keypair()
    sig = sign_message(priv, "hello")
    assert verify_signature(pub, "hello tampered", sig) is False
    assert verify_signature(pub, "hello", "00" * 64) is False
    other_sig = sign_message(other_priv, "hello")
    assert verify_signature(pub, "hello", other_sig) is False


def test_event_hash_uses_all_parts():
    h = event_hash(GENESIS_HASH, '{"a":1}', "aa" * 64)
    assert len(h) == 64
    assert h != event_hash("1" * 64, '{"a":1}', "aa" * 64)
    assert h != event_hash(GENESIS_HASH, '{"a":2}', "aa" * 64)
    assert h != event_hash(GENESIS_HASH, '{"a":1}', "bb" * 64)


def test_merkle_root_empty_is_genesis():
    assert merkle_root([]) == GENESIS_HASH


def test_merkle_root_single():
    h = sha256_hex("leaf")
    assert merkle_root([h]) == h


def test_merkle_root_two():
    a, b = sha256_hex("a"), sha256_hex("b")
    assert merkle_root([a, b]) == sha256_hex(a, b)


def test_merkle_root_odd_pads_last():
    a, b, c = sha256_hex("a"), sha256_hex("b"), sha256_hex("c")
    # odd -> duplicates last leaf before combining
    assert merkle_root([a, b, c]) == sha256_hex(sha256_hex(a, b), sha256_hex(c, c))
