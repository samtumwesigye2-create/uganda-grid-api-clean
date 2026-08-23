"""
Flutterwave payment integration (card + Mobile Money) for UGAMAP.

Requires env vars:
    FLW_SECRET_KEY  - from your Flutterwave dashboard, Settings > API

Flow:
  1. initiate_payment() -> hosted checkout link
  2. customer pays on Flutterwave's page (card or MTN/Airtel Mobile Money)
  3. Flutterwave redirects back to redirect_url with status + transaction_id
  4. verify_payment(transaction_id) -> confirm status/amount server-side
"""
import os
import requests

FLW_BASE = "https://api.flutterwave.com/v3"


def _headers():
    return {
        "Authorization": f"Bearer {os.environ['FLW_SECRET_KEY']}",
        "Content-Type": "application/json",
    }


def initiate_payment(tx_ref: str, amount: float, currency: str, customer_email: str,
                      customer_name: str, redirect_url: str) -> str:
    payload = {
        "tx_ref": tx_ref,
        "amount": amount,
        "currency": currency,
        "redirect_url": redirect_url,
        "payment_options": "card,mobilemoneyuganda",
        "customer": {"email": customer_email, "name": customer_name},
        "customizations": {"title": "UGAMAP Shipment Payment"},
    }
    resp = requests.post(f"{FLW_BASE}/payments", json=payload, headers=_headers(), timeout=15)
    resp.raise_for_status()
    return resp.json()["data"]["link"]


def verify_payment(transaction_id: str) -> dict:
    resp = requests.get(f"{FLW_BASE}/transactions/{transaction_id}/verify",
                         headers=_headers(), timeout=15)
    resp.raise_for_status()
    return resp.json()["data"]
