import sqlite3

from ugatu import ugatu_master_driver as master


def test_master_driver_not_created_without_env(monkeypatch, tmp_path):
    monkeypatch.delenv("UGATU_MASTER_KEY", raising=False)
    monkeypatch.setattr(master, "DB_PATH", str(tmp_path / "data_hub.db"))
    assert master.master_key_configured() is False
    assert master.ensure_master_driver() is False
    assert not (tmp_path / "data_hub.db").exists()


def test_master_driver_created_from_env(monkeypatch, tmp_path):
    db = tmp_path / "data_hub.db"
    monkeypatch.setenv("UGATU_MASTER_KEY", "test-master-secret")
    monkeypatch.setattr(master, "DB_PATH", str(db))
    assert master.ensure_master_driver() is True
    conn = sqlite3.connect(db)
    row = conn.execute("SELECT id,name,passcode,is_active FROM drivers WHERE id=?", (master.MASTER_DRIVER_ID,)).fetchone()
    conn.close()
    assert row == (master.MASTER_DRIVER_ID, "UGATU Master", "test-master-secret", 1)


def test_master_key_conflict_is_rejected(monkeypatch, tmp_path):
    db = tmp_path / "data_hub.db"
    monkeypatch.setenv("UGATU_MASTER_KEY", "duplicate-secret")
    monkeypatch.setattr(master, "DB_PATH", str(db))
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE drivers (id TEXT PRIMARY KEY,name TEXT NOT NULL,phone TEXT,passcode TEXT UNIQUE NOT NULL,vehicle_id TEXT,status TEXT NOT NULL DEFAULT 'off_duty',current_lat REAL,current_lon REAL,last_ping_at REAL,is_active INTEGER NOT NULL DEFAULT 1,created_at REAL NOT NULL)")
    conn.execute("INSERT INTO drivers VALUES (?,?,?,?,?,?,?,?,?,?,?)", ("OTHER","Other Driver","","duplicate-secret",None,"available",None,None,None,1,1.0))
    conn.commit(); conn.close()
    try:
        master.ensure_master_driver()
        assert False, "Expected conflict to raise"
    except RuntimeError as exc:
        assert "conflicts" in str(exc)
