"""
notifications.py — Sends customer notifications when a shipment's
delivery status is updated by an admin.

Two channels, both best-effort (a failure in one, or both, never
blocks the admin status update itself — it just gets logged):

  - Email via Resend (https://resend.com) — REST API, urllib only,
    no new dependency needed (same pattern as the Africa's Talking
    and Flutterwave calls elsewhere in this codebase)
  - SMS via Africa's Talking REST API (urllib, stdlib only)

Env vars needed:
  RESEND_API_KEY              — from https://resend.com/api-keys
  RESEND_FROM_ADDRESS          — sender address. Use
                                 "onboarding@resend.dev" to start
                                 sending immediately with no setup, or
                                 "notifications@ugandagrid.com" once
                                 that domain is verified in Resend

  AFRICASTALKING_API_KEY     — from your Africa's Talking dashboard
  AFRICASTALKING_USERNAME    — your AT username ("sandbox" while testing,
                                 your real username once live)

  FRONTEND_BASE_URL          — already defined in shipments.py; reused
                                 here to build the tracking link in
                                 the notification text

If any of these are missing, that channel is silently skipped (so you
can turn on email now and add SMS later, or vice versa, without
breaking anything).
"""

import json
import os
import urllib.error
import urllib.parse
import urllib.request

RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
RESEND_FROM_ADDRESS = os.environ.get("RESEND_FROM_ADDRESS", "onboarding@resend.dev")
RESEND_URL = "https://api.resend.com/emails"

AFRICASTALKING_API_KEY = os.environ.get("AFRICASTALKING_API_KEY", "")
AFRICASTALKING_USERNAME = os.environ.get("AFRICASTALKING_USERNAME", "sandbox")
AFRICASTALKING_URL = "https://api.africastalking.com/version1/messaging"

FRONTEND_BASE_URL = os.environ.get(
    "FRONTEND_BASE_URL", "https://uganda-grid-api-clean-production.up.railway.app"
)


def _status_label(status: str) -> str:
    return status.replace("_", " ").title()


def _normalize_ug_phone(phone: str) -> str:
    """Best-effort normalize to +256XXXXXXXXX for Africa's Talking."""
    phone = phone.strip().replace(" ", "").replace("-", "")
    if phone.startswith("+"):
        return phone
    if phone.startswith("0"):
        return "+256" + phone[1:]
    if phone.startswith("256"):
        return "+" + phone
    return phone


def send_email(to_address: str, subject: str, body: str) -> bool:
    if not to_address or not RESEND_API_KEY:
        return False
    try:
        # Resend expects HTML (or text) content. We send plain body as
        # both, wrapping newlines as <br> for the HTML version so it
        # renders reasonably in email clients.
        html_body = body.replace("\n", "<br>")
        payload = json.dumps({
            "from": RESEND_FROM_ADDRESS,
            "to": [to_address],
            "subject": subject,
            "text": body,
            "html": html_body,
        }).encode()

        req = urllib.request.Request(RESEND_URL, data=payload, method="POST")
        req.add_header("Authorization", f"Bearer {RESEND_API_KEY}")
        req.add_header("Content-Type", "application/json")

        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode())
        return bool(result.get("id"))
    except urllib.error.HTTPError as e:
        print(f"[notifications] email send failed to {to_address}: {e.read().decode()}")
        return False
    except Exception as e:
        print(f"[notifications] email send failed to {to_address}: {e}")
        return False


def send_sms(to_phone: str, message: str) -> bool:
    if not to_phone or not AFRICASTALKING_API_KEY:
        return False
    try:
        to_phone = _normalize_ug_phone(to_phone)
        payload = urllib.parse.urlencode({
            "username": AFRICASTALKING_USERNAME,
            "to": to_phone,
            "message": message,
        }).encode()

        req = urllib.request.Request(AFRICASTALKING_URL, data=payload, method="POST")
        req.add_header("apiKey", AFRICASTALKING_API_KEY)
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        req.add_header("Accept", "application/json")

        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode())
        recipients = result.get("SMSMessageData", {}).get("Recipients", [])
        return bool(recipients) and recipients[0].get("status") == "Success"
    except urllib.error.HTTPError as e:
        print(f"[notifications] sms send failed to {to_phone}: {e.read().decode()}")
        return False
    except Exception as e:
        print(f"[notifications] sms send failed to {to_phone}: {e}")
        return False


def notify_shipment_update(shipment: dict, new_status: str, note: str = ""):
    """Fire-and-forget notification to a shipment's recipient (falls back
    to sender if no recipient contact is on file). `shipment` is a dict
    with at least: shipment_number, pickup, delivery, recipient_name,
    recipient_email, recipient_phone, sender_name, sender_email,
    sender_phone.

    Called from shipments.py right after a delivery_status update is
    committed. Never raises — logs and moves on so a bad email/SMS
    config can't break the admin's status update.
    """
    number = shipment.get("shipment_number", "")
    label = _status_label(new_status)
    track_link = f"{FRONTEND_BASE_URL}/track?ship={number}"

    name = shipment.get("recipient_name") or shipment.get("sender_name") or "there"
    email = shipment.get("recipient_email") or shipment.get("sender_email") or ""
    phone = shipment.get("recipient_phone") or shipment.get("sender_phone") or ""

    subject = f"Shipment {number} update: {label}"
    body_lines = [
        f"Hi {name},",
        "",
        f"Your shipment {number} ({shipment.get('pickup', '')} -> {shipment.get('delivery', '')}) is now: {label}.",
    ]
    if note:
        body_lines.append(f"Note: {note}")
    body_lines += ["", f"Track it any time: {track_link}", "", "— Uganda National Grid Ship & Mail"]
    email_body = "\n".join(body_lines)

    sms_body = f"UG Grid: shipment {number} is now {label}."
    if note:
        sms_body += f" ({note})"
    sms_body += f" Track: {track_link}"

    email_sent = send_email(email, subject, email_body)
    sms_sent = send_sms(phone, sms_body)

    return {"email_sent": email_sent, "sms_sent": sms_sent}
