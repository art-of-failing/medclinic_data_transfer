import os

from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import execute_values

load_dotenv()


def connect():
    """Подключение к БД. Используется как контекстный менеджер транзакции: with conn: ..."""
    return psycopg2.connect(
        host=os.getenv('db_host', 'localhost'),
        database='analytics',
        user=os.getenv('db_user'),
        password=os.getenv('db_password'),
        port='5432',
        client_encoding='UTF8',
    )


def bulk_insert(cursor, query, rows, template=None):
    """Пакетная вставка: query должен содержать 'VALUES %s'."""
    execute_values(cursor, query, rows, template=template, page_size=1000)
