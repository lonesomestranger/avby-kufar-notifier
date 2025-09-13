def get_db_url(db_name: str = "db.sqlite3"):
    return f"sqlite+aiosqlite:///{db_name}"
