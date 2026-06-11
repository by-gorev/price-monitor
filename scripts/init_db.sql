-- Создание отдельной базы данных для competitor-monitor
-- Запуск от имени суперпользователя PostgreSQL:
--   psql -U postgres -f scripts/init_db.sql

-- Пользователь приложения
CREATE USER competitor_user WITH PASSWORD 'competitor_password';

-- База данных (отдельная от других проектов)
CREATE DATABASE competitor_monitor OWNER competitor_user;

-- Права
GRANT ALL PRIVILEGES ON DATABASE competitor_monitor TO competitor_user;
