from datetime import datetime, timedelta
import os
import requests

from dotenv import load_dotenv
import pandas as pd
import re

from logger import logger
from psgsql_connect import db

load_dotenv()
bitrix_host = os.getenv('bitrix_host')
bitrix_token = os.getenv('bitrix_token')
bitrix_user = os.getenv('bitrix_user')


class Bitrix():
    def __init__(self,host,token,user):
        self.host = host
        self.__token = token
        self.user = user

        try:

            url = f'https://{self.host}.bitrix24.ru/rest/{self.user}/{self.__token}/crm.status.entity.items'
            data = {
                'entityId': 'SOURCE'
            }

            response = requests.post(url=url,json=data)
        except Exception as e:
            logger.log(50,f'Ошибка получения данных справочника. Текст ошибки: {e}')
        else:
            if response.status_code != 200:
                logger.log(50,f'Ошибка получения данных справочника. Код ответа: {response.status_code}. Тело ответа: {response.json()}')
            else:
                self.source_df = pd.DataFrame(response.json()['result'])[['STATUS_ID','NAME']]
                self.source_df.columns = ['STATUS_ID','SOURCE']
        
        try:
            url = f'https://{self.host}.bitrix24.ru/rest/{self.user}/{self.__token}/crm.item.fields'
            data = {
                'entityTypeId': 1,
                'useOriginalUfNames' : 'Y'
            }

            response = requests.post(url=url,json=data)
        except Exception as e:
            logger.log(50,f'Ошибка получения данных пользовательского поля. Текст ошибки: {e}')
        else:
            if response.status_code != 200:
                logger.log(50,f'Ошибка получения данных пользовательского поля. Код ответа: {response.status_code}. Тело ответа: {response.json()}')
            else:
                df = pd.DataFrame(response.json()['result']['fields']['UF_CRM_1760353216']['items'])
                df['ID'] = df['ID'].astype('int64')
                df.columns = ['ID','SOURCE_DESCRIPTION']
                self.source_detail_df = df
                
            

    def get_data(self,date1,date2,start=0):
        url = f'https://{self.host}.bitrix24.ru/rest/{self.user}/{self.__token}/crm.item.list'
        data = {
            'entityTypeId': 1,
            'select': [
                'id',
                'createdTime',
                'stageId',
                'phone',
                'utmSource',
                'utmMedium',
                'utmCampaign',
                'utmContent',
                'utmTerm',
                'sourceId',
                'ufCrm_1760353216'
            ],
            'useOriginalUfNames': 'N',
            'filter': {
                '>=createdTime': date1,
                '<createdTime': date2,
            },
            'order': {
                'createdTime': 'DESC'
            },
            'start':start
        }

        try:
            response = requests.post(url=url,json=data)
        except Exception as e:
            logger.log(50,f'Ошибка выгрузки данных Bitrix. Текст ошибки: {e}')
        else:
            if response.status_code != 200:
                logger.log(50,f'Ошибка запроса Bitrix {response.status_code}. Ответ: {response.json()}')
            else:
                logger.log(20,f'Данные Bitrix получены!')

                df = self.to_df(response.json()['result']['items'])
                self.to_db(db=db,data=df)

                if 'next' in response.json():
                    self.get_data(date1,date2,start=response.json()['next'])

    
    def to_df(self,data):
        colums = [
                'id',
                'createdTime',
                'stageId',
                'phone',
                'utmSource',
                'utmMedium',
                'utmCampaign',
                'utmContent',
                'utmTerm',
                'SOURCE',
                'SOURCE_DESCRIPTION'
            ]
        df = pd.DataFrame(data)
        df['createdTime'] = pd.to_datetime(df['createdTime'],format='%Y-%m-%dT%H:%M:%S+03:00')
        df['phone'] = df['phone'].apply(self.__format_phone_number)

        df = (df
              .merge(self.source_df,how='left',left_on='sourceId',right_on='STATUS_ID')
              .merge(self.source_detail_df,how='left',left_on='ufCrm_1760353216',right_on='ID'))
        return df[colums]
    
    def to_db(self,data,db):
        count = 0
        for i,row in data.iterrows():
            query =  """INSERT  INTO bitrix_data VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (id)
                        DO UPDATE SET
                            id = EXCLUDED.id,
                            createdTime = EXCLUDED.createdTime,
                            stageId = EXCLUDED.stageId,
                            phone = EXCLUDED.phone,
                            utmSource = EXCLUDED.utmSource,
                            utmMedium = EXCLUDED.utmMedium,
                            utmCampaign = EXCLUDED.utmCampaign,
                            utmContent = EXCLUDED.utmContent,
                            utmTerm = EXCLUDED.utmTerm,
                            source = EXCLUDED.source,
                            sourceDescription = EXCLUDED.sourceDescription;"""
            try:
                db.post(query=query,vars=(row['id'],
                                                row['createdTime'],
                                                row['stageId'],
                                                row['phone'],
                                                row['utmSource'],
                                                row['utmMedium'],
                                                row['utmCampaign'],
                                                row['utmContent'],
                                                row['utmTerm'],
                                                row['SOURCE'],
                                                row['SOURCE_DESCRIPTION']))
            except:
                ...
            else:
                count += 1
        logger.log(20,f'В БД bitix_data записано {count} из {len(data)} строк!')
    
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

today = datetime.today().strftime('%Y-%m-%dT00:00:00+03:00')
yesterday = (datetime.today() - timedelta(days=1)).strftime('%Y-%m-%dT00:00:00+03:00')

bitix = Bitrix(bitrix_host,bitrix_token,bitrix_user)
bitix.get_data(yesterday,today)
