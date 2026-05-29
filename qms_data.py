import glob
import os
import re

import pandas as pd

from logger import logger
from psgsql_connect import db


class File_Reader():
    def __init__(self,folder_path):
        self.folder_path = folder_path
        self.file_list = glob.glob(os.path.join(folder_path, 'call*.xls'))
        try:
            df_list = pd.read_html(self.file_list[0],skiprows=3,header=0)
            df = pd.concat(df_list)
            df['Дата начала звонка'] = pd.to_datetime(df['Дата звонка'] + ' ' + df['Время начала'],format='%d.%m.%Y %H:%M:%S')
            df['Дата конца звонка'] = pd.to_datetime(df['Дата звонка'] + ' ' + df['Время окончания'],format='%d.%m.%Y %H:%M:%S')
            df = df[pd.to_numeric(df['№'],errors='coerce').notna()]
            df = df[['Дата начала звонка','Дата конца звонка', 'Тип', 'Телефон', 'Рег №', 'Тема звонка', 'Отделение', 'Врач', 'Источник сведений', 'Результат звонка', 'ФИО оператора']]
            df['Телефон'] = df['Телефон'].apply(self.__format_phone_number)
            self.df = df
        except Exception as e:
            logger.log(50,f'Ошибка получения данных из файла. Текст ошибки: {e}')
        else:
            logger.log(20,f'Данные из файла {self.file_list[0]} получены!')
            
            new_path = os.path.join(r'/home/contractor/qms_files/archive/', os.path.basename(self.file_list[0]))
            os.rename(self.file_list[0],new_path)

    def __format_phone_number(self,phone):
        if pd.isna(phone) or not str(phone).strip():
            return pd.NA
        
        digits = re.sub(r'\D', '', str(phone))

        if len(digits) < 10:
            return pd.NA
        
        if (digits.startswith('7') or digits.startswith('8')) and len(digits) == 11:
            digits = digits[1:]
        elif len(digits) > 11:
            return digits
        
        return '7' + digits
    
    def to_db(self,data):
        count = 0
        for i,row in data.iterrows():
            query =  """INSERT  INTO qms_data VALUES (DEFAULT,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"""
            try:
                db.post(query=query,vars=(row['Дата начала звонка'],
                                                row['Тип'],
                                                row['Телефон'],
                                                row['Рег №'],
                                                row['Тема звонка'],
                                                row['Отделение'],
                                                row['Врач'],
                                                row['Источник сведений'],
                                                row['Результат звонка'],
                                                row['ФИО оператора']
                                                ))
            except:
                ...
            else:
                count += 1
        logger.log(20,f'В БД qms_data записано {count} из {len(data)} строк!')


file = File_Reader(r'/home/contractor/qms_files/')
file.to_db(file.df)


