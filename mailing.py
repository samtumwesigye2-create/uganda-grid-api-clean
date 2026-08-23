"""
Mass Mailing module for Uganda National Grid (UGAMAP)
--------------------------------------------------------
Drop this file into your repo root alongside main.py, then in main.py add:

    from mailing import router as mailing_router
    app.include_router(mailing_router)

Storage follows the same pattern as entebbe_database.json — a flat JSON
file — so it needs no new database setup. Swap for a real DB later if
your subscriber list grows large.

SMTP config: set these environment variables on Railway/Render:
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM
Works with Gmail (app password), SendGrid SMTP relay, Mailgun SMTP, etc.
No paid API required — any SMTP provider works.
"""

import json
import os
import smtplib
import ssl
import uuid
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, EmailStr

router = APIRouter(prefix="/api/mail", tags=["mailing"])

DB_PATH = Path(__file__).parent / "mailing_database.json"


# ---------- storage helpers ----------

def _load():
    if not DB_PATH.exists():
        data = {"subscribers": [], "campaigns": []}
        _save(data)
        return data
    return json.loads(DB_PATH.read_text())


def _save(data):
    DB_PATH.write_text(json.dumps(data, indent=2, default=str))


# ---------- models ----------

class Subscriber(BaseModel):
    email: EmailStr
    name: Optional[str] = None
    region: Optional[str] = None       # e.g. "Kampala", "Entebbe" — lets you segment
    tags: List[str] = []


class CampaignCreate(BaseModel):
    subject: str
    body_html: str
    segment_region: Optional[str] = None   # send only to subscribers in this region
    segment_tag: Optional[str] = None      # send only to subscribers with this tag


# ---------- subscriber endpoints ----------

@router.post("/subscribers")
def add_subscriber(sub: Subscriber):
    data = _load()
    if any(s["email"] == sub.email for s in data["subscribers"]):
        raise HTTPException(400, "Already subscribed")
    record = sub.dict()
    record["id"] = str(uuid.uuid4())
    record["subscribed_at"] = datetime.now(timezone.utc).isoformat()
    record["active"] = True
    data["subscribers"].append(record)
    _save(data)
    return record


@router.get("/subscribers")
def list_subscribers(region: Optional[str] = None, tag: Optional[str] = None):
    data = _load()
    subs = data["subscribers"]
    if region:
        subs = [s for s in subs if s.get("region") == region]
    if tag:
        subs = [s for s in subs if tag in s.get("tags", [])]
    return subs


@router.delete("/subscribers/{subscriber_id}")
def unsubscribe(subscriber_id: str):
    data = _load()
    before = len(data["subscribers"])
    data["subscribers"] = [s for s in data["subscribers"] if s["id"] != subscriber_id]
    if len(data["subscribers"]) == before:
        raise HTTPException(404, "Subscriber not found")
    _save(data)
    return {"deleted": subscriber_id}


# ---------- sending ----------

def _send_email(to_email: str, subject: str, html_body: str):
    host = os.environ["SMTP_HOST"]
    port = int(os.environ.get("SMTP_PORT", 587))
    user = os.environ["SMTP_USER"]
    password = os.environ["SMTP_PASSWORD"]
    sender = os.environ.get("SMTP_FROM", user)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to_email
    msg.attach(MIMEText(html_body, "html"))

    context = ssl.create_default_context()
    with smtplib.SMTP(host, port) as server:
        server.starttls(context=context)
        server.login(user, password)
        server.sendmail(sender, to_email, msg.as_string())


def _send_campaign_task(campaign_id: str):
    data = _load()
    campaign = next(c for c in data["campaigns"] if c["id"] == campaign_id)

    recipients = data["subscribers"]
    if campaign.get("segment_region"):
        recipients = [s for s in recipients if s.get("region") == campaign["segment_region"]]
    if campaign.get("segment_tag"):
        recipients = [s for s in recipients if campaign["segment_tag"] in s.get("tags", [])]

    sent, failed = 0, []
    for sub in recipients:
        try:
            _send_email(sub["email"], campaign["subject"], campaign["body_html"])
            sent += 1
        except Exception as e:
            failed.append({"email": sub["email"], "error": str(e)})

    campaign["status"] = "sent"
    campaign["sent_count"] = sent
    campaign["failed"] = failed
    campaign["completed_at"] = datetime.now(timezone.utc).isoformat()
    _save(data)


@router.post("/campaigns")
def create_campaign(campaign: CampaignCreate, background_tasks: BackgroundTasks):
    data = _load()
    record = campaign.dict()
    record["id"] = str(uuid.uuid4())
    record["created_at"] = datetime.now(timezone.utc).isoformat()
    record["status"] = "sending"
    data["campaigns"].append(record)
    _save(data)

    background_tasks.add_task(_send_campaign_task, record["id"])
    return record


@router.get("/campaigns")
def list_campaigns():
    return _load()["campaigns"]


@router.get("/campaigns/{campaign_id}")
def get_campaign(campaign_id: str):
    data = _load()
    for c in data["campaigns"]:
        if c["id"] == campaign_id:
            return c
    raise HTTPException(404, "Campaign not found")
