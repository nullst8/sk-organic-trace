#!/usr/bin/env python3

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from eth_account import Account
from web3 import Web3

from app.chain import deploy_to_rpc, explorer_address_url, explorer_tx_url
from app.settings import settings


def main() -> None:
    if not settings.anchor_rpc_url or not settings.anchor_private_key:
        print("Missing ANCHOR_RPC_URL or ANCHOR_PRIVATE_KEY in backend/.env")
        sys.exit(1)

    key = settings.anchor_private_key
    if not key.startswith("0x"):
        key = "0x" + key
    account = Account.from_key(key)
    w3 = Web3(Web3.HTTPProvider(settings.anchor_rpc_url))
    if not w3.is_connected():
        print("Cannot connect to", settings.anchor_rpc_url)
        sys.exit(1)

    bal = w3.eth.get_balance(account.address)
    eth = float(w3.from_wei(bal, "ether"))
    print("Network chain_id:", w3.eth.chain_id)
    print("Funding address:", account.address)
    print("Explorer:", explorer_address_url(account.address, w3.eth.chain_id))
    print(f"Balance: {eth} ETH")

    if bal == 0:
        print(
            "\nFund this address with Sepolia ETH, then re-run:\n"
            "  https://www.alchemy.com/faucets/ethereum-sepolia\n"
            "  https://cloud.google.com/application/web3/faucet/ethereum/sepolia\n"
            "  https://faucet.quicknode.com/ethereum/sepolia\n"
        )
        sys.exit(2)

    if settings.anchor_contract_address:
        print("Contract already set:", settings.anchor_contract_address)
        print("Explorer:", explorer_address_url(settings.anchor_contract_address, w3.eth.chain_id))
        print("Restart uvicorn to load settings if you just funded/deployed.")
        return

    print("Deploying ProvenanceAnchor…")
    address = deploy_to_rpc()
    print("Deployed:", address)
    print("Wrote ANCHOR_CONTRACT_ADDRESS to backend/.env")
    print("Explorer:", explorer_address_url(address, w3.eth.chain_id))
    print("Restart uvicorn, then POST /api/anchors to publish a Merkle root.")


if __name__ == "__main__":
    main()
