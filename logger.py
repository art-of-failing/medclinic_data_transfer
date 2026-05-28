from datetime import datetime
import logging
import os
import sys

class Logger:
  #Не даем создать новый объект
  def __new__(cls, *args, **kwargs):
    if not hasattr(cls, 'instance'):
      cls.instance = super().__new__(cls)
    return cls.instance

  def __init__(self,path):
    if hasattr(self, 'logger'):
      return

    self.path = path

    os.makedirs(self.path, exist_ok=True)

    #Создаем логгер
    self.logger = logging.getLogger('logger')
    self.logger.setLevel(logging.INFO)

    self.logger.handlers.clear()

    #Создаем обработчик для фалла
    self.file_name = os.path.join(self.path, datetime.strftime(datetime.today(),'%Y-%m-%d')+'.log')
    self.file_handler = logging.FileHandler(self.file_name,encoding='UTF-8')
    self.file_handler.setLevel(logging.INFO)

    # Форматирование
    self.formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    self.file_handler.setFormatter(self.formatter)

    # Добавляем обработчик к логгеру
    self.logger.addHandler(self.file_handler)


  def log(self,level,text):
    if level == 10:
      self.logger.debug(text)
    elif level == 20:
      self.logger.info(text)
    elif level == 30:
      self.logger.warning(text)
    elif level == 40:
      self.logger.error(text)
    elif level == 50:
      self.logger.critical(text)
      sys.exit('Критическая ошибка')


logger = Logger(r'C:\Users\HR\Documents\Python\Pirogova\venv\log')