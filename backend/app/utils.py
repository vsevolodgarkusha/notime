from datetime import datetime, timezone
import logging
try:
    from zoneinfo import ZoneInfo
except ImportError:
    # Fallback for older python (though we are on modern)
    from backports.zoneinfo import ZoneInfo

def format_user_time(dt: datetime, timezone_str: str) -> str:
    """
    Convert UTC datetime to user's timezone string.
    Format: dd.mm.yyyy HH:MM
    """
    if dt is None:
        return ""

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    if not timezone_str:
        logging.warning("No timezone provided, using UTC")
        return dt.strftime("%d.%m.%Y %H:%M")

    try:
        user_tz = ZoneInfo(timezone_str)
        local_time = dt.astimezone(user_tz)
        return local_time.strftime("%d.%m.%Y %H:%M")
    except Exception as e:
        logging.error(f"Timezone conversion error for {timezone_str}: {e}")
        return dt.strftime("%d.%m.%Y %H:%M")
