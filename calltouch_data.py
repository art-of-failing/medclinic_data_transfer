from datetime import datetime, timedelta
import os

from dotenv import load_dotenv
import pandas as pd
import requests

from logger import logger
from psgsql_connect import db


load_dotenv()
ct_api_token = os.getenv('ct_api_token')
ct_site_id = os.getenv('ct_site_id')


class Calltouch():
    def __init__(self,site_id,token):
        self.site_id = site_id
        self.__token = token

    def get_yesterday_data(self):
        yesterday = (datetime.today() - timedelta(days=1)).strftime('%d/%m/%Y')
        url = f'https://api.calltouch.ru/calls-service/RestAPI/{self.site_id}/calls-diary/calls'
        params = {
            'clientApiId':self.__token,
            'dateFrom': yesterday,
            'dateTo': yesterday
        }

        try:
            response = requests.get(url=url,params=params)
        except Exception as e:
            logger.log(50,f'Ошибка выгрузки данных Calltouch. Текст ошибки: {e}')
        else:
            if response.status_code != 200:
                logger.log(50,f'Ошибка запроса Calltouch {response.status_code}. Ответ: {response.json()}')
            else:
                logger.log(20,f'Данные Calltouch за {yesterday} получены!')
                self.status_code = response.status_code
                self.json = response.json()

                df = self.to_df(response.json())
                self.to_db(df=df,db=db)

    
    def get_custom_date_data(self,date1,date2,page=1):
        print(page)
        url = f'https://api.calltouch.ru/calls-service/RestAPI/{self.site_id}/calls-diary/calls'
        params = {
            'clientApiId':self.__token,
            'dateFrom': date1,
            'dateTo': date2,
            'page': page,
            'limit': 500
        }

        try:
            response = requests.get(url=url,params=params)
        except Exception as e:
            logger.log(50,f'Ошибка выгрузки данных Calltouch. Текст ошибки: {e}')
        else:
            if response.status_code != 200:
                logger.log(50,f'Ошибка запроса Calltouch {response.status_code}. Ответ: {response.json()}')
            else:
                self.status_code = response.status_code
                self.json = response.json()

                df = self.to_df(self.json['records'])
                self.to_db(df=df,db=db)

                if self.json['pageTotal'] > self.json['page']:
                    print(self.json['pageTotal'],self.json['page'])
                    page +=1
                    self.get_custom_date_data(date1,date2,page)

    def to_df(self,data):
        colums = ['callId','date','duration','callerNumber','utmSource','utmMedium','utmCampaign','utmContent','utmTerm','siteName']
        df = pd.DataFrame(data)[colums]
        df['date'] = pd.to_datetime(df['date'],dayfirst=True)
        df['duration'] = df['date'] + pd.to_timedelta(df['duration'], unit='s')
        return df
    
    def to_db(self,df,db):
        count = 0
        for i,row in df.iterrows():
            query =  """INSERT  INTO calltouch_data VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (siteName, callId)
                        DO UPDATE SET
                            date = EXCLUDED.date,
                            callernumber = EXCLUDED.callerNumber,
                            utmsource = EXCLUDED.utmSource,
                            utmmedium = EXCLUDED.utmMedium,
                            utmcampaign = EXCLUDED.utmCampaign,
                            utmcontent = EXCLUDED.utmContent,
                            utmterm = EXCLUDED.utmTerm;"""
            try:
                db.post(query=query,vars=(row['callId'],
                                                row['date'],
                                                row['callerNumber'],
                                                row['utmSource'],
                                                row['utmMedium'],
                                                row['utmCampaign'],
                                                row['utmContent'],
                                                row['utmTerm'],
                                                row['siteName']))
            except:
                ...
            else:
                count += 1
        logger.log(20,f'В БД calltouch_data записано {count} из {len(df)} строк!')

ct_pirogova = Calltouch(site_id=ct_site_id,token=ct_api_token)
ct_pirogova.get_yesterday_data()
#ct_pirogova.get_custom_date_data('20/04/2026','25/05/2026')


