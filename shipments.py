"""
Flutterwave payment integration for UGAMAP Shipment/Parcel module
-------------------------------------------------------------------
Drop into repo root alongside shipments.py and rates.py.

Provides:
    initiate_payment(tx_ref, amount, currency, customer_email,
                      customer_name, redirect_url) -> str (payment link)
    verify_payment(transaction_id) -> dict with keys:
                      status, tx_ref, amount, currency

Env var required (Railway/Render -> Variables):
    FLW_SECRET_KEY   - your Flutterwave secret key (starts with FLWSECK-)

Docs: https://developer.flutterwave.com/docs/flutterwave-standard
"""

import os
import requests

FLW_BASE_URL = "https://api.flutterwave.com/v3"


def _secret_key() -> str:
    key = os.environ.get("FLW_SECRET_KEY")
    if not key:
        raise RuntimeError(
            "FLW_SECRET_KEY environment variable is not set. "
            "Add it in your hosting provider's Variables/Env settings."
        )
    return key


def initiate_payment(
    tx_ref: str,
    amount: float,
    currency: str,
    customer_email: str,
    customer_name: str,
    redirect_url: str,
) -> str:
    """
    Creates a Flutterwave Standard payment and returns the hosted
    checkout link the customer should be redirected to.

    Raises RuntimeError with a readable message on any failure so the
    caller's `except Exception as e: raise HTTPException(502, f"...{e}")`
    shows something useful instead of a raw stack trace.
    """
    url = f"{FLW_BASE_URL}/payments"
    headers = {
        "Authorization": f"Bearer {_secret_key()}",
        "Content-Type": "application/json",
    }
    payload = {
        "tx_ref": tx_ref,
        "amount": str(amount),
        "currency": currency,
        "redirect_url": redirect_url,
        "customer": {
            "email": customer_email,
            "name": customer_name,
        },
        "customizations": {
            "title": "UGAMAP Shipment Payment",
            "description": f"Payment for shipment {tx_ref}",
        },
    }

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=15)
    except requests.RequestException as e:
        raise RuntimeError(f"could not reach Flutterwave: {e}")

    try:
        data = resp.json()
    except ValueError:
        raise RuntimeError(f"unexpected response from Flutterwave (status {resp.status_code})")

    if resp.status_code != 200 or data.get("status") != "success":
        message = data.get("message", "unknown error")
        raise RuntimeError(f"Flutterwave rejected the request: {message}")

    link = data.get("data", {}).get("link")
    if not link:
        raise RuntimeError("Flutterwave response did not include a payment link")

    return link


def verify_payment(transaction_id: str) -> dict:
    """
    Verifies a completed transaction by its Flutterwave transaction_id
    (passed back on the redirect as `transaction_id`).

    Returns a dict: {"status": "successful"/"failed"/..., "tx_ref": str,
    "amount": float, "currency": str} so the caller in shipments.py can
    cross-check tx_ref and amount before marking a shipment as paid.
    """
    url = f"{FLW_BASE_URL}/transactions/{transaction_id}/verify"
    headers = {
        "Authorization": f"Bearer {_secret_key()}",
    }

    try:
        resp = requests.get(url, headers=headers, timeout=15)
    except requests.RequestException as e:
        raise RuntimeError(f"could not reach Flutterwave: {e}")

    try:
        data = resp.json()
    except ValueError:
        raise RuntimeError(f"unexpected response from Flutterwave (status {resp.status_code})")

    if resp.status_code != 200 or data.get("status") != "success":
        message = data.get("message", "unknown error")
        raise RuntimeError(f"Flutterwave verify failed: {message}")

    tx = data.get("data", {})
    return {
        "status": tx.get("status"),
        "tx_ref": tx.get("tx_ref"),
        "amount": tx.get("amount"),
        "currency": tx.get("currency"),
    }
