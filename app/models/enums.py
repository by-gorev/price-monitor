"""
Перечисления (статусы и типы) для приложения.
"""
import enum


class MatchStatus(str, enum.Enum):
    """Статус сопоставления товара конкурента с нашим товаром."""

    UNMATCHED = "UNMATCHED"  # Не сопоставлен
    AUTO_MATCHED = "AUTO_MATCHED"  # Сопоставлен автоматически
    MANUAL_MATCHED = "MANUAL_MATCHED"  # Сопоставлен вручную
    IGNORED = "IGNORED"  # Не учитывать при сравнении


class MatchType(str, enum.Enum):
    """Способ, которым было создано сопоставление."""

    AUTO = "AUTO"
    MANUAL = "MANUAL"
