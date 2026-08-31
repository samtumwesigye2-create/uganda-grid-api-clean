import os

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()


def _connect():
    if not DATABASE_URL:
        raise RuntimeError("Permanent incident storage unavailable")
    import psycopg2
    return psycopg2.connect(DATABASE_URL)


def init_account_links():
    conn = _connect()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                ALTER TABLE ugamap_incidents
                  ADD COLUMN IF NOT EXISTS reporter_user_id UUID;

                CREATE INDEX IF NOT EXISTS idx_ugamap_incidents_reporter
                  ON ugamap_incidents(reporter_user_id, created_at DESC);

                CREATE TABLE IF NOT EXISTS ugamap_incident_votes(
                    incident_id UUID NOT NULL,
                    user_id UUID NOT NULL,
                    vote VARCHAR(16) NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    PRIMARY KEY(incident_id, user_id)
                );

                CREATE INDEX IF NOT EXISTS idx_ugamap_incident_votes_user
                  ON ugamap_incident_votes(user_id, updated_at DESC);
                """)
        return True
    finally:
        conn.close()


def attach_reporter(incident_id: str, user_id: str):
    conn = _connect()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE ugamap_incidents SET reporter_user_id=%s WHERE id=%s AND reporter_user_id IS NULL",
                    (user_id, incident_id),
                )
                cur.execute(
                    "INSERT INTO ugamap_incident_audit(incident_id,action,value) VALUES(%s,'reporter_account',%s)",
                    (incident_id, user_id),
                )
    finally:
        conn.close()


def vote_once(incident_id: str, user_id: str, vote: str):
    value = (vote or "").strip().lower()
    if value not in {"confirm", "not_there"}:
        raise ValueError("Vote must be confirm or not_there")
    conn = _connect()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT reporter_user_id FROM ugamap_incidents WHERE id=%s FOR UPDATE", (incident_id,))
                row = cur.fetchone()
                if not row:
                    return None
                if row[0] and str(row[0]) == str(user_id):
                    raise PermissionError("You cannot confirm your own report")

                cur.execute(
                    """INSERT INTO ugamap_incident_votes(incident_id,user_id,vote)
                       VALUES(%s,%s,%s)
                       ON CONFLICT(incident_id,user_id)
                       DO UPDATE SET vote=EXCLUDED.vote,updated_at=NOW()""",
                    (incident_id, user_id, value),
                )
                cur.execute(
                    """SELECT
                         COUNT(*) FILTER (WHERE vote='confirm'),
                         COUNT(*) FILTER (WHERE vote='not_there')
                       FROM ugamap_incident_votes WHERE incident_id=%s""",
                    (incident_id,),
                )
                yes, no = cur.fetchone()
                community = "confirmed" if yes >= 2 and yes > no else ("disputed" if no >= 2 and no >= yes else "unverified")
                cur.execute(
                    "UPDATE ugamap_incidents SET confirm_yes=%s,confirm_no=%s,community_status=%s WHERE id=%s",
                    (yes, no, community, incident_id),
                )
                cur.execute(
                    "INSERT INTO ugamap_incident_audit(incident_id,action,value) VALUES(%s,'account_vote',%s)",
                    (incident_id, value),
                )
                return {"id": incident_id, "confirm_yes": yes, "confirm_no": no, "community_status": community, "your_vote": value}
    finally:
        conn.close()


def list_user_reports(user_id: str):
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id,category,lat,lon,note,status,EXTRACT(EPOCH FROM created_at),
                          confirm_yes,confirm_no,community_status,media_type,(media_data IS NOT NULL)
                   FROM ugamap_incidents
                   WHERE reporter_user_id=%s
                   ORDER BY created_at DESC""",
                (user_id,),
            )
            out=[]
            for r in cur.fetchall():
                item={"id":str(r[0]),"category":r[1],"lat":r[2],"lon":r[3],"note":r[4] or "","status":r[5],"created_at":float(r[6]),"confirm_yes":r[7] or 0,"confirm_no":r[8] or 0,"community_status":r[9] or "unverified","media_type":r[10]}
                if r[11]: item["media_url"]="/report-media/"+item["id"]
                out.append(item)
            return out
    finally:
        conn.close()


try:
    if DATABASE_URL:
        init_account_links()
except Exception:
    pass
