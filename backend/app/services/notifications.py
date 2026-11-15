from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import httpx
from sqlalchemy import select
from app.config import settings
from app.config.database import Session
from app.models.application import Application
from app.models.runtime import Notification
from app.models.runtime import NotificationPreference
from app.models.profile import Profile


def reminders():
    # In-app notification and email are independently retryable; external delivery is not guaranteed.
    with Session() as db:
        cursor = ""
        while True:
            rows = list(
                db.scalars(
                    select(Application)
                    .where(
                        Application.status.in_(["SAVED", "DRAFT", "READY_FOR_REVIEW"]),
                        Application.id > cursor,
                    )
                    .order_by(Application.id)
                    .limit(100)
                )
            )
            if not rows:
                break
            cursor = rows[-1].id
            for app in rows:
                key = (
                    "application-reminder:"
                    + app.id
                    + ":"
                    + datetime.now(timezone.utc).date().isoformat()
                )
                notification = db.scalar(
                    select(Notification).where(
                        Notification.owner_id == app.owner_id, Notification.kind_key == key
                    )
                )
                if notification is None:
                    notification = Notification(
                        owner_id=app.owner_id,
                        kind_key=key,
                        payload=dict(
                            event=key,
                            text="Review your saved application",
                            application_id=app.id,
                            email_status="PENDING",
                        ),
                    )
                    db.add(notification)
                    db.commit()
                preference = db.scalar(
                    select(NotificationPreference).where(
                        NotificationPreference.owner_id == app.owner_id,
                        NotificationPreference.kind_key == "preferences",
                    )
                )
                prefs = preference.payload if preference else {}
                if (
                    "email" not in prefs.get("channels", [])
                    or not settings.resend_api_key
                    or not settings.resend_from
                ):
                    continue
                hour = datetime.now(ZoneInfo(prefs.get("timezone", "UTC"))).hour
                start, end = prefs.get("quiet_start", 22), prefs.get("quiet_end", 8)
                if (start < end and start <= hour < end) or (
                    start > end and (hour >= start or hour < end)
                ):
                    continue
                profile = db.scalar(select(Profile).where(Profile.owner_id == app.owner_id))
                email = profile.payload.get("notification_email") if profile else None
                if email and notification.payload.get("email_status") != "PROVIDER_ACCEPTED":
                    try:
                        response = httpx.post(
                            "https://api.resend.com/emails",
                            headers={
                                "Authorization": "Bearer " + settings.resend_api_key,
                                "Idempotency-Key": key,
                            },
                            json={
                                "from": settings.resend_from,
                                "to": [email],
                                "subject": "Review your application",
                                "text": "You have a saved application to review in OpportunityOS.",
                            },
                            timeout=5,
                        )
                        if response.is_success:
                            notification.payload = dict(
                                notification.payload, email_status="PROVIDER_ACCEPTED"
                            )
                            db.commit()
                    except httpx.HTTPError:
                        continue
