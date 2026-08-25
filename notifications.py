"""
notifications.py — Sends customer notifications when a shipment's
delivery status is updated by an admin.

Two channels, both best-effort (a failure in one, or both, never
blocks the admin status update itself — it just gets logged):

  - Email via Gmail SMTP (smtplib, stdlib only)
  - SMS via Africa's Talking REST API (urllib, stdlib only — same
    pattern as the Flutterwave calls in shipments.py, no new
    dependency needed)

Env vars needed:
  GMAIL_ADDRESS              — the Gmail address to send from
  GMAIL_APP_PASSWORD         — a Gmail "app password" (NOT your normal
                                 Gmail password — generate one at
                                 https://myaccount.google.com/apppasswords,
                                 requires 2-Step Verification to be on)

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
import smtplib
import urllib.error
import urllib.parse
import urllib.request
from email.mime.text import MIMEText

GMAIL_ADDRESS = os.environ.get("GMAIL_ADDRESS", "")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")

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
    if not to_address or not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        return False
    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = GMAIL_ADDRESS
        msg["To"] = to_address

        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as server:
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_ADDRESS, [to_address], msg.as_string())
        return True
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
