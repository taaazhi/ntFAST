"""One-off cleanup of stale login_history rows.

Run once after deploying the session-cleanup change:
    python -m scripts.cleanup_stale_sessions

Closes any session where logout_time IS NULL and login_time is older than
SESSION_INACTIVITY_DAYS (default 7). Also closes obvious testing artefacts
where user_agent starts with 'curl/' or 'python-requests/'.

The same logic runs lazily on each /active-sessions request, but this script
gives an immediate clean state for the security page without waiting for the
first user to trigger lazy cleanup.
"""
from datetime import datetime, timedelta

from app.core.database import SessionLocal
from app.models.login_history import LoginHistory
from app.services.login_history_service import SESSION_INACTIVITY_DAYS


def main() -> None:
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        cutoff = now - timedelta(days=SESSION_INACTIVITY_DAYS)

        # 1) Old sessions past inactivity threshold
        stale_by_age = (
            db.query(LoginHistory)
            .filter(LoginHistory.logout_time.is_(None), LoginHistory.login_time < cutoff)
            .all()
        )

        # 2) Testing/automation sessions (curl, python-requests, httpx) — usually never log out properly.
        #    Safe to close: real browsers identify as Mozilla/Chrome/Firefox/Safari/Edge.
        TESTING_PREFIXES = ("curl/", "python-requests/", "httpx/", "PostmanRuntime/", "Wget/")
        all_active = (
            db.query(LoginHistory)
            .filter(LoginHistory.logout_time.is_(None))
            .all()
        )
        stale_by_ua = [
            r for r in all_active
            if r.user_agent and any(r.user_agent.startswith(p) for p in TESTING_PREFIXES)
        ]

        # Combine sets (avoid double-closing)
        seen_ids = set()
        to_close = []
        for r in (*stale_by_age, *stale_by_ua):
            if r.id in seen_ids:
                continue
            seen_ids.add(r.id)
            to_close.append(r)

        for r in to_close:
            r.logout_time = now
            if r.login_time:
                r.session_duration = int((now - r.login_time).total_seconds())

        db.commit()

        print(f"Closed {len(to_close)} stale sessions "
              f"({len(stale_by_age)} aged-out, "
              f"{len(stale_by_ua)} testing-agent)")
    finally:
        db.close()


if __name__ == "__main__":
    main()
