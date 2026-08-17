@app.get("/search")
def search_address(q: str):
    query = q.strip()

    if not query:
        raise HTTPException(
            status_code=400,
            detail="Search query is required"
        )

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id,
                    grid_id,
                    country,
                    district_code,
                    subcounty_code,
                    parish_code,
                    building_id,
                    latitude,
                    longitude,
                    address
                FROM uganda_grid_records
                WHERE
                    grid_id ILIKE %s
                    OR address ILIKE %s
                    OR building_id ILIKE %s
                ORDER BY id
                LIMIT 25;
                """,
                (
                    f"%{query}%",
                    f"%{query}%",
                    f"%{query}%"
                )
            )

            rows = cur.fetchall()

    return [
        {
            "id": row[0],
            "grid_id": row[1],
            "country": row[2],
            "district_code": row[3],
            "subcounty_code": row[4],
            "parish_code": row[5],
            "building_id": row[6],
            "latitude": row[7],
            "longitude": row[8],
            "address": row[9]
        }
        for row in rows
    ]
