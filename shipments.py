    @router.get("/ship/receipt/{shipment_number}", response_class=HTMLResponse)
    def receipt(shipment_number: str):
        conn = get_conn()
        row = conn.execute("SELECT * FROM shipments WHERE shipment_number = ?", (shipment_number,)).fetchone()
        conn.close()
        if not row:
            raise HTTPException(status_code=404, detail="Shipment not found")
        if row["status"] != "paid":
            return HTMLResponse(
                "<body style='font-family:-apple-system,sans-serif;max-width:420px;"
                "margin:60px auto;text-align:center;'><h2>Payment required</h2>"
                "<p>This shipment doesn't have a receipt yet because it hasn't "
                "been paid for.</p></body>",
                status_code=402,
            )

        tier = all_tier_labels().get(row["speed_tier"], {"label": row["speed_tier"]})
        date_str = time.strftime("%Y-%m-%d %H:%M", time.localtime(row["created_at"]))
        is_intl = row["shipment_type"] == "international"
        delivery_status = row["delivery_status"] or "created"
        delivery_label = delivery_status.replace("_", " ").title()
        track_link = f"{FRONTEND_BASE_URL}/track?ship={row['shipment_number']}"

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Receipt — {row['shipment_number']}</title>
            <style>
                body {{ font-family: -apple-system, sans-serif; max-width:480px; margin:30px auto; padding:20px; color:#111; }}
                h1 {{ font-size:20px; border-bottom:2px solid #111; padding-bottom:10px; }}
                table {{ width:100%; border-collapse:collapse; margin-top:16px; }}
                td {{ padding:6px 0; border-bottom:1px solid #eee; }}
                td:first-child {{ color:#666; width:45%; }}
                .total {{ font-size:18px; font-weight:bold; margin-top:16px; }}
                .status {{ display:inline-block; padding:4px 10px; border-radius:6px; font-size:13px; margin-right:6px; }}
                .paid {{ background:#d4f4dd; color:#1a7a37; }}
                .delivery {{ background:#dbe6ff; color:#2a3a7a; }}
                button {{ margin-top:20px; padding:10px 16px; border:none; border-radius:6px; background:#e2593a; color:#fff; font-size:15px; margin-right:8px; cursor:pointer; }}
                a.trackBtn {{ display:inline-block; margin-top:20px; padding:10px 16px; border-radius:6px; background:#3b5bfd; color:#fff; font-size:15px; text-decoration:none; }}
            </style>
        </head>
        <body>
            <h1>Uganda National Grid — Shipping Receipt</h1>
            <p>Receipt #: <strong>{row['shipment_number']}</strong><br>Date: {date_str}</p>
            <span class="status paid">PAID ({(row['payment_method'] or '').upper() or 'CONFIRMED'})</span>
            <span class="status delivery">{delivery_label}</span>

            <table>
                <tr><td>Type</td><td>{'International' if is_intl else 'Domestic'}</td></tr>
                <tr><td>Pickup</td><td>{row['pickup']}</td></tr>
                <tr><td>Delivery</td><td>{row['delivery']}</td></tr>
                <tr><td>Weight</td><td>{row['weight_kg']} kg</td></tr>
                {'' if is_intl else f"<tr><td>Distance</td><td>{row['distance_km']} km</td></tr>"}
                <tr><td>Speed</td><td>{tier.get('label', row['speed_tier'])}</td></tr>
                <tr><td>Sender</td><td>{row['sender_name'] or '—'} {('· ' + row['sender_phone']) if row['sender_phone'] else ''}</td></tr>
                <tr><td>Recipient</td><td>{row['recipient_name'] or '—'} {('· ' + row['recipient_phone']) if row['recipient_phone'] else ''}</td></tr>
            </table>

            <p class="total">Total paid: UGX {row['rate_ugx']:,.0f}</p>

            <a class="trackBtn" href="{track_link}">Track this shipment</a>
        </body>
        </html>
        """

    return router
