"""Idempotent migration: adds users.notification_settings JSON column.

SQLAlchemy's Base.metadata.create_all does NOT alter existing tables — it only
creates missing ones. So when we add a new column to the User model (like
`notification_settings`), existing databases need an explicit ALTER TABLE.

Run once after deploying the User.notification_settings change:
    python -m scripts.add_notification_settings_column

Safe to run multiple times: uses `ADD COLUMN IF NOT EXISTS` (Postgres 9.6+).
"""
from sqlalchemy import text

from app.core.database import engine


def main() -> None:
    with engine.begin() as conn:
        # ADD COLUMN IF NOT EXISTS is Postgres-native (no syntax errors on second run)
        conn.execute(text("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS notification_settings JSON
        """))
        # Check if it was added or already existed
        result = conn.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'users' AND column_name = 'notification_settings'
        """)).first()
        if result:
            print("users.notification_settings: present")
        else:
            print("users.notification_settings: NOT FOUND (migration may have failed)")


if __name__ == "__main__":
    main()
