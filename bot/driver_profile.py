"""
Driver Profile Management

Handles driver profiles, preferences, and statistics.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class DriverProfileManager:
    """
    Manages driver profiles and personalization.

    Features:
    - Auto-create profiles on first interaction
    - Track statistics (requests, messages, activity)
    - Manage preferences
    - Provide personalized context for RAG
    """

    def __init__(self, storage):
        """
        Args:
            storage: Storage instance (must support PostgreSQL)
        """
        self.storage = storage

    def get_or_create_profile(self, user_id: int, user_data: dict) -> dict:
        """
        Get existing profile or create new one.

        Args:
            user_id: Telegram user ID
            user_data: User data from Telegram (full_name, username)

        Returns:
            Driver profile dict
        """
        if not self.storage.use_postgres:
            # Return minimal profile for SQLite
            return {
                "user_id": user_id,
                "full_name": user_data.get("full_name", "Unknown"),
                "username": user_data.get("username"),
                "status": "active",
            }

        return self.storage.get_or_create_driver_profile(
            user_id=user_id,
            user_data=user_data,
        )

    def update_activity(self, user_id: int) -> None:
        """
        Update driver's last activity timestamp and stats.

        Args:
            user_id: Telegram user ID
        """
        if not self.storage.use_postgres:
            return

        today = date.today()

        try:
            # Increment total messages for today
            self.storage.add_driver_stat(
                user_id=user_id,
                stat_date=today,
                stat_type="messages",
                stat_value=1,  # Will be incremented if exists
            )
        except Exception as e:
            logger.debug(f"Failed to update activity stats: {e}")

    def track_request(self, user_id: int, request_type: str) -> None:
        """
        Track driver request statistics.

        Args:
            user_id: Telegram user ID
            request_type: Type of request (day_off_request, car_assignment_request)
        """
        if not self.storage.use_postgres:
            return

        today = date.today()

        try:
            # Increment request count for today
            self.storage.add_driver_stat(
                user_id=user_id,
                stat_date=today,
                stat_type=f"requests_{request_type}",
                stat_value=1,
            )

            # Increment total requests
            self.storage.add_driver_stat(
                user_id=user_id,
                stat_date=today,
                stat_type="requests_total",
                stat_value=1,
            )
        except Exception as e:
            logger.debug(f"Failed to track request: {e}")

    def set_preference(self, user_id: int, key: str, value: str) -> None:
        """
        Set driver preference.

        Common preferences:
        - shift_preference: 'morning', 'day', 'night'
        - notification_preference: 'all', 'important_only', 'off'
        - language_preference: 'ru', 'en'

        Args:
            user_id: Telegram user ID
            key: Preference key
            value: Preference value
        """
        if not self.storage.use_postgres:
            logger.warning("Preferences require PostgreSQL")
            return

        try:
            self.storage.update_driver_preference(
                user_id=user_id,
                preference_key=key,
                preference_value=value,
            )
            logger.info(f"Set preference for user {user_id}: {key}={value}")
        except Exception as e:
            logger.error(f"Failed to set preference: {e}")

    def get_preferences(self, user_id: int) -> dict[str, str]:
        """
        Get all preferences for a driver.

        Args:
            user_id: Telegram user ID

        Returns:
            Dict of preferences {key: value}
        """
        if not self.storage.use_postgres:
            return {}

        try:
            return self.storage.get_driver_preferences(user_id)
        except Exception as e:
            logger.error(f"Failed to get preferences: {e}")
            return {}

    def get_stats_summary(
        self,
        user_id: int,
        days: int = 30,
    ) -> dict:
        """
        Get driver statistics summary.

        Args:
            user_id: Telegram user ID
            days: Number of days to analyze

        Returns:
            Stats summary dict
        """
        if not self.storage.use_postgres:
            return {}

        end_date = date.today()
        start_date = end_date - timedelta(days=days)

        try:
            stats = self.storage.get_driver_stats(
                user_id=user_id,
                start_date=start_date,
                end_date=end_date,
            )

            # Aggregate stats
            summary = {
                "total_messages": 0,
                "total_requests": 0,
                "day_off_requests": 0,
                "car_assignment_requests": 0,
                "active_days": 0,
            }

            seen_dates = set()

            for stat in stats:
                stat_type = stat.get("stat_type", "")
                stat_value = float(stat.get("stat_value", 0))
                stat_date = stat.get("stat_date")

                if stat_date and stat_date not in seen_dates:
                    seen_dates.add(stat_date)

                if stat_type == "messages":
                    summary["total_messages"] += int(stat_value)
                elif stat_type == "requests_total":
                    summary["total_requests"] += int(stat_value)
                elif stat_type == "requests_day_off_request":
                    summary["day_off_requests"] += int(stat_value)
                elif stat_type == "requests_car_assignment_request":
                    summary["car_assignment_requests"] += int(stat_value)

            summary["active_days"] = len(seen_dates)

            return summary

        except Exception as e:
            logger.error(f"Failed to get stats summary: {e}")
            return {}

    def format_profile_context(self, profile: dict, preferences: dict | None = None) -> str:
        """
        Format driver profile for RAG context.

        Args:
            profile: Driver profile dict
            preferences: Optional preferences dict

        Returns:
            Formatted profile context string
        """
        preferences = preferences or {}

        lines = [
            f"Водитель: {profile.get('full_name', 'Unknown')}",
        ]

        if profile.get('username'):
            lines.append(f"Username: @{profile['username']}")

        if profile.get('status'):
            status_map = {
                'active': 'Активен',
                'inactive': 'Неактивен',
                'on_leave': 'В отпуске',
            }
            lines.append(f"Статус: {status_map.get(profile['status'], profile['status'])}")

        if preferences.get('shift_preference'):
            shift_map = {
                'morning': 'Утренняя',
                'day': 'Дневная',
                'night': 'Ночная',
            }
            shift = shift_map.get(preferences['shift_preference'], preferences['shift_preference'])
            lines.append(f"Предпочитаемая смена: {shift}")

        return "\n".join(lines)


# Admin helper functions

def format_driver_info(profile: dict, stats: dict, preferences: dict) -> str:
    """
    Format driver information for admin view.

    Args:
        profile: Driver profile
        stats: Stats summary
        preferences: Driver preferences

    Returns:
        Formatted info string
    """
    lines = [
        "👤 Профиль водителя",
        "",
        f"ID: {profile.get('user_id')}",
        f"Имя: {profile.get('full_name', 'Unknown')}",
    ]

    if profile.get('username'):
        lines.append(f"Username: @{profile['username']}")

    lines.append(f"Статус: {profile.get('status', 'active')}")

    if profile.get('created_at'):
        lines.append(f"Зарегистрирован: {profile['created_at']}")

    # Stats
    if stats:
        lines.extend([
            "",
            "📊 Статистика (последние 30 дней):",
            f"Всего сообщений: {stats.get('total_messages', 0)}",
            f"Всего заявок: {stats.get('total_requests', 0)}",
            f"- Выходные: {stats.get('day_off_requests', 0)}",
            f"- Постановка на авто: {stats.get('car_assignment_requests', 0)}",
            f"Активных дней: {stats.get('active_days', 0)}",
        ])

    # Preferences
    if preferences:
        lines.extend([
            "",
            "⚙️ Настройки:",
        ])
        for key, value in preferences.items():
            lines.append(f"- {key}: {value}")

    return "\n".join(lines)
