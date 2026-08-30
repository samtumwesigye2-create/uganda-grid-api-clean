import csv
import os
import sys
import psycopg

CSV_FILE = os.environ.get("ENTEBBE_IMPORT_FILE", "entebbe_database_import.csv")
DATABASE_URL = os.environ.get("DATABASE_URL")
BATCH_SIZE = 1000

if not DATABASE_URL:
    raise SystemExit("DATABASE_URL is not set.")

def main():
    with open(CSV_FILE, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    print(f"Loaded {len(rows):,} rows from {CSV_FILE}")

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            # Keep the existing test record and any other records.
            cur.execute("SELECT grid_id FROM uganda_grid_records;")
            existing = {r[0] for r in cur.fetchall() if r[0]}

            new_rows = [r for r in rows if r["grid_id"] not in existing]
            skipped = len(rows) - len(new_rows)

            print(f"Already present / skipped: {skipped:,}")
            print(f"New records to insert: {len(new_rows):,}")

            sql = """
                INSERT INTO uganda_grid_records (
                    grid_id,
                    country,
                    district_code,
                    subcounty_code,
                    parish_code,
                    building_id,
                    latitude,
                    longitude,
                    address
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
            """

            inserted = 0
            for start in range(0, len(new_rows), BATCH_SIZE):
                batch = new_rows[start:start + BATCH_SIZE]
                values = [
                    (
                        r["grid_id"],
                        r["country"],
                        r["district_code"],
                        r["subcounty_code"],
                        r["parish_code"],
                        r["building_id"],
                        float(r["latitude"]),
                        float(r["longitude"]),
                        r["address"],
                    )
                    for r in batch
                ]
                cur.executemany(sql, values)
                inserted += len(values)
                print(f"Inserted {inserted:,}/{len(new_rows):,}")

        conn.commit()

    print("IMPORT COMPLETE")
    print(f"Inserted: {inserted:,}")
    print(f"Skipped existing: {skipped:,}")

if __name__ == "__main__":
    main()
