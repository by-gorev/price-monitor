"""
Настройки приложения.
Значения берутся из переменных окружения или файла .env.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

# Загружаем переменные из .env в корне проекта
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# URL подключения к отдельной базе competitor_monitor
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://competitor_user:competitor_password@localhost:5432/competitor_monitor",
)

# Порт веб-сервера
APP_PORT = int(os.getenv("APP_PORT", "8082"))

# Задержка между HTTP-запросами при парсинге (секунды)
REQUEST_DELAY_SECONDS = 2
