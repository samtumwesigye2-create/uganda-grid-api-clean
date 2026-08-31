import os

DATABASE_URL=os.environ.get("DATABASE_URL","").strip()


def _connect():
    if not DATABASE_URL: raise RuntimeError("Permanent incident storage unavailable")
    import psycopg2
    return psycopg2.connect(DATABASE_URL)


def init_reputation():
    conn=_connect()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                CREATE TABLE IF NOT EXISTS ugamap_reporter_reputation(
                    user_id UUID PRIMARY KEY,
                    score INTEGER NOT NULL DEFAULT 50,
                    reports_total INTEGER NOT NULL DEFAULT 0,
                    confirmed_reports INTEGER NOT NULL DEFAULT 0,
                    disputed_reports INTEGER NOT NULL DEFAULT 0,
                    admin_resolved_reports INTEGER NOT NULL DEFAULT 0,
                    trust_level VARCHAR(24) NOT NULL DEFAULT 'standard',
                    flagged BOOLEAN NOT NULL DEFAULT FALSE,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """)
    finally: conn.close()


def recalculate(user_id):
    conn=_connect()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""SELECT COUNT(*),COUNT(*) FILTER(WHERE community_status='confirmed'),COUNT(*) FILTER(WHERE community_status='disputed'),COUNT(*) FILTER(WHERE status='resolved') FROM ugamap_incidents WHERE reporter_user_id=%s""",(user_id,))
                total,confirmed,disputed,resolved=cur.fetchone()
                score=max(0,min(100,50 + confirmed*8 + resolved*3 - disputed*12))
                level='trusted' if score>=75 and confirmed>=3 else ('restricted' if score<30 else 'standard')
                flagged=score<30 or (disputed>=3 and disputed>confirmed)
                cur.execute("""INSERT INTO ugamap_reporter_reputation(user_id,score,reports_total,confirmed_reports,disputed_reports,admin_resolved_reports,trust_level,flagged,updated_at) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,NOW()) ON CONFLICT(user_id) DO UPDATE SET score=EXCLUDED.score,reports_total=EXCLUDED.reports_total,confirmed_reports=EXCLUDED.confirmed_reports,disputed_reports=EXCLUDED.disputed_reports,admin_resolved_reports=EXCLUDED.admin_resolved_reports,trust_level=EXCLUDED.trust_level,flagged=EXCLUDED.flagged,updated_at=NOW()""",(user_id,score,total,confirmed,disputed,resolved,level,flagged))
                return {'user_id':str(user_id),'score':score,'reports_total':total,'confirmed_reports':confirmed,'disputed_reports':disputed,'admin_resolved_reports':resolved,'trust_level':level,'flagged':flagged}
    finally: conn.close()


def reputation_for(user_id):
    return recalculate(user_id)


def reputation_for_incident(incident_id):
    conn=_connect()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT reporter_user_id FROM ugamap_incidents WHERE id=%s',(incident_id,)); row=cur.fetchone()
    finally: conn.close()
    return recalculate(row[0]) if row and row[0] else None


def flagged_reporters():
    conn=_connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT user_id FROM ugamap_reporter_reputation WHERE flagged=TRUE ORDER BY score ASC")
            ids=[r[0] for r in cur.fetchall()]
        return [recalculate(x) for x in ids]
    finally: conn.close()

try:
    if DATABASE_URL:init_reputation()
except Exception:pass
