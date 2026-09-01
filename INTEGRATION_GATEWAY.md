# UGA Integration Gateway

The gateway exchanges signed, idempotent JSON events with external systems without granting database access.

Configure Railway variable `INTEGRATION_CONNECTORS_JSON`:

```json
{
  "partner-system": {
    "name": "Partner System",
    "webhook_url": "https://partner.example/webhooks/uga",
    "secret": "replace-with-a-long-random-secret",
    "enabled": true,
    "subscriptions": ["shipment.created", "inventory.updated"],
    "field_map": {"shipment_number": "external_reference"},
    "headers": {"X-Partner-ID": "uga"}
  }
}
```

Staff permissions are `integration:read` and `integration:write`. The master administrator retains full access.

Routes:

- `GET /integration/status`
- `GET /integration/connectors`
- `POST /integration/events`
- `POST /integration/webhooks/{connector_id}`
- `GET /integration/events`
- `POST /integration/events/{event_id}/retry`

Outbound requests include `X-UGA-Signature`, `X-UGA-Event-ID`, and `X-UGA-Idempotency-Key`. Inbound systems sign the exact request body using HMAC-SHA256 and send `X-UGA-Signature: sha256=<hex digest>`.
