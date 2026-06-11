"""
Подключение к базе данных PostgreSQL через SQLAlchemy.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import DATABASE_URL

# Движок SQLAlchemy
engine = create_engine(DATABASE_URL, echo=False)

# Фабрика сессий для работы с БД
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Базовый класс для всех моделей."""

    pass


def get_db():
    """
    Зависимость FastAPI: открывает сессию БД и закрывает после запроса.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
