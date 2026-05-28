import os

from dotenv import load_dotenv
import psycopg2

from logger import logger

load_dotenv()
db_password = os.getenv('db_password')
db_user = os.getenv('db_user')

class Database:
  def __new__(cls, *args, **kwargs):
    if not hasattr(cls, 'instance'):
      cls.instance = super().__new__(cls)
    return cls.instance
  
  def __init__(self, user, password, autocommit=True):
    try:

      self.connection = psycopg2.connect(
          host="localhost",
          database="pirogova_analytics",
          user=user,
          password=password,
          port="5432",
          client_encoding='UTF8'
      )
    except Exception as e:
      logger.log(50,f'Ошибка подключения к базе данных. Текст ошибки: {e}')
      print(e)
    else:
      logger.log(20,f'Подключение к базе прошло успешно!')

    if autocommit:
      self.connection.autocommit = True

    self.cursor = self.connection.cursor()

  def post(self, query, vars):
    try:
      self.cursor.execute(query, vars)
      if not self.connection.autocommit:
        self.connection.commit()
    except Exception as e:
      logger.log(40,f'Ошибка записи данных. Запрос: { self.cursor.query}. Ошибка: {e}')

db = Database(user=db_user,password=db_password)