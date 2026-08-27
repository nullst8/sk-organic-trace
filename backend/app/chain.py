from __future__ import annotations

import json
import re
import threading
from pathlib import Path

from eth_account import Account
from web3 import Web3

from .settings import settings

CONTRACT_SOURCE = """
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract ProvenanceAnchor {
    mapping(uint256 => bytes32) public roots;
    uint256 public count;

    event Anchored(uint256 indexed id, bytes32 root, uint256 timestamp);

    function anchor(bytes32 root) external {
        roots[count] = root;
        emit Anchored(count, root, block.timestamp);
        count++;
    }
}
"""

ANCHOR_ABI = [
    {
        "inputs": [{"internalType": "bytes32", "name": "root", "type": "bytes32"}],
        "name": "anchor",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "count",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "internalType": "uint256", "name": "id", "type": "uint256"},
            {"indexed": False, "internalType": "bytes32", "name": "root", "type": "bytes32"},
            {"indexed": False, "internalType": "uint256", "name": "timestamp", "type": "uint256"},
        ],
        "name": "Anchored",
        "type": "event",
    },
]

_lock = threading.Lock()
_local_w3: Web3 | None = None
_local_address: str | None = None
_local_key: str | None = None
_BACKEND = Path(__file__).resolve().parent.parent
_STATE_PATH = _BACKEND / ".anchor_local.json"
_ENV_PATH = _BACKEND / ".env"

EXPLORERS = {
    1: "https://etherscan.io",
    11155111: "https://sepolia.etherscan.io",
    80002: "https://amoy.polygonscan.com",
}


def explorer_base(chain_id: int | None = None) -> str | None:
    cid = chain_id if chain_id is not None else settings.anchor_chain_id
    if cid is None:
        return None
    return EXPLORERS.get(int(cid))


def explorer_tx_url(tx_hash: str | None, chain_id: int | None = None) -> str | None:
    if not tx_hash:
        return None
    base = explorer_base(chain_id)
    if not base:
        return None
    return f"{base}/tx/{tx_hash}"


def explorer_address_url(address: str | None, chain_id: int | None = None) -> str | None:
    if not address:
        return None
    base = explorer_base(chain_id)
    if not base:
        return None
    return f"{base}/address/{address}"


def funding_address() -> str | None:
    if not settings.anchor_private_key:
        return None
    key = settings.anchor_private_key
    if not key.startswith("0x"):
        key = "0x" + key
    return Account.from_key(key).address


def _compile_bytecode() -> str:
    from solcx import compile_source, install_solc, set_solc_version

    install_solc("0.8.20")
    set_solc_version("0.8.20")
    compiled = compile_source(
        CONTRACT_SOURCE,
        output_values=["abi", "bin"],
        solc_version="0.8.20",
    )
    _, artifact = next(iter(compiled.items()))
    return "0x" + artifact["bin"]


def _deploy(w3: Web3, private_key: str) -> str:
    account = Account.from_key(private_key)
    bytecode = _compile_bytecode()
    contract = w3.eth.contract(abi=ANCHOR_ABI, bytecode=bytecode)
    tx = contract.constructor().build_transaction(
        {
            "from": account.address,
            "nonce": w3.eth.get_transaction_count(account.address),
            "chainId": w3.eth.chain_id,
            "gas": 800_000,
            "gasPrice": w3.eth.gas_price,
        }
    )
    signed = account.sign_transaction(tx)
    raw = getattr(signed, "raw_transaction", None) or signed.rawTransaction
    tx_hash = w3.eth.send_raw_transaction(raw)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    if not receipt.contractAddress:
        raise RuntimeError("Contract deploy failed")
    return receipt.contractAddress


def _ensure_local_chain() -> tuple[Web3, str, str]:
    global _local_w3, _local_address, _local_key
    with _lock:
        if _local_w3 and _local_address and _local_key:
            return _local_w3, _local_address, _local_key

        from web3 import EthereumTesterProvider

        w3 = Web3(EthereumTesterProvider())
        key = "0x" + "11" * 32
        account = Account.from_key(key)
        funded = w3.eth.accounts[0]
        w3.eth.send_transaction(
            {
                "from": funded,
                "to": account.address,
                "value": w3.to_wei(100, "ether"),
            }
        )
        address = _deploy(w3, key)
        _local_w3, _local_address, _local_key = w3, address, key
        _STATE_PATH.write_text(
            json.dumps({"mode": "eth-tester", "address": address}),
            encoding="utf-8",
        )
        return w3, address, key


def _rpc_web3() -> tuple[Web3, str, str]:
    assert settings.anchor_rpc_url and settings.anchor_private_key and settings.anchor_contract_address
    w3 = Web3(Web3.HTTPProvider(settings.anchor_rpc_url))
    if not w3.is_connected():
        raise RuntimeError(f"Cannot connect to RPC: {settings.anchor_rpc_url}")
    key = settings.anchor_private_key
    if not key.startswith("0x"):
        key = "0x" + key
    address = Web3.to_checksum_address(settings.anchor_contract_address)
    return w3, address, key


def chain_status() -> dict:
    fund = funding_address()
    balance_eth = None
    if settings.anchor_rpc_url and fund:
        try:
            w3 = Web3(Web3.HTTPProvider(settings.anchor_rpc_url))
            if w3.is_connected():
                balance_eth = float(w3.from_wei(w3.eth.get_balance(fund), "ether"))
        except Exception:
            balance_eth = None

    if settings.rpc_configured:
        return {
            "mode": "sepolia" if settings.anchor_chain_id == 11155111 else "rpc",
            "rpc_url": settings.anchor_rpc_url,
            "contract": settings.anchor_contract_address,
            "chain_id": settings.anchor_chain_id,
            "funding_address": fund,
            "balance_eth": balance_eth,
            "explorer_contract": explorer_address_url(settings.anchor_contract_address),
            "explorer_address": explorer_address_url(fund),
        }

    return {
        "mode": "local-eth-tester",
        "contract": _local_address,
        "chain_id": settings.anchor_chain_id,
        "funding_address": fund,
        "balance_eth": balance_eth,
        "explorer_address": explorer_address_url(fund),
        "note": (
            "Anchors use an in-process Ethereum tester until ANCHOR_CONTRACT_ADDRESS "
            "is set. Fund the funding_address on Sepolia, then run: python deploy_anchor.py"
        ),
        "faucet_urls": [
            "https://www.alchemy.com/faucets/ethereum-sepolia",
            "https://faucet.quicknode.com/ethereum/sepolia",
            "https://cloud.google.com/application/web3/faucet/ethereum/sepolia",
        ],
    }


def submit_merkle_root(root_hex: str) -> tuple[str, bool, int | None]:
    root_hex = root_hex.lower().removeprefix("0x")
    if len(root_hex) != 64:
        raise ValueError("merkle root must be 32 bytes hex")
    root_bytes = bytes.fromhex(root_hex)

    if settings.rpc_configured:
        w3, address, key = _rpc_web3()
        chain_id = w3.eth.chain_id
    else:
        w3, address, key = _ensure_local_chain()
        chain_id = None

    account = Account.from_key(key)
    contract = w3.eth.contract(address=address, abi=ANCHOR_ABI)
    tx = contract.functions.anchor(root_bytes).build_transaction(
        {
            "from": account.address,
            "nonce": w3.eth.get_transaction_count(account.address),
            "chainId": w3.eth.chain_id,
            "gas": 200_000,
            "gasPrice": w3.eth.gas_price,
        }
    )
    signed = account.sign_transaction(tx)
    raw = getattr(signed, "raw_transaction", None) or signed.rawTransaction
    tx_hash = w3.eth.send_raw_transaction(raw)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    if receipt.status != 1:
        raise RuntimeError("anchor transaction failed")
    hex_hash = tx_hash.to_0x_hex() if hasattr(tx_hash, "to_0x_hex") else w3.to_hex(tx_hash)
    return hex_hash, False, chain_id


def write_contract_to_env(address: str) -> None:
    text = _ENV_PATH.read_text(encoding="utf-8") if _ENV_PATH.exists() else ""
    line = f"ANCHOR_CONTRACT_ADDRESS={address}"
    if re.search(r"^ANCHOR_CONTRACT_ADDRESS=.*$", text, flags=re.M):
        text = re.sub(r"^ANCHOR_CONTRACT_ADDRESS=.*$", line, text, flags=re.M)
    elif re.search(r"^#\s*ANCHOR_CONTRACT_ADDRESS=.*$", text, flags=re.M):
        text = re.sub(r"^#\s*ANCHOR_CONTRACT_ADDRESS=.*$", line, text, flags=re.M)
    else:
        text = text.rstrip() + "\n" + line + "\n"
    _ENV_PATH.write_text(text, encoding="utf-8")


def deploy_to_rpc() -> str:
    if not settings.anchor_rpc_url or not settings.anchor_private_key:
        raise RuntimeError("ANCHOR_RPC_URL and ANCHOR_PRIVATE_KEY required")
    key = settings.anchor_private_key
    if not key.startswith("0x"):
        key = "0x" + key
    w3 = Web3(Web3.HTTPProvider(settings.anchor_rpc_url))
    if not w3.is_connected():
        raise RuntimeError("Cannot connect to RPC")
    account = Account.from_key(key)
    bal = w3.eth.get_balance(account.address)
    if bal == 0:
        raise RuntimeError(
            f"Wallet {account.address} has 0 Sepolia ETH. Fund it from a faucet, then retry."
        )
    address = _deploy(w3, key)
    write_contract_to_env(address)
    return address
