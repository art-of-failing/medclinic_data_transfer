import argparse
import os
import sys

from dotenv import load_dotenv
import pandas as pd

from logger import get_logger
from psgsql_connect import bulk_insert, connect
from utils import TIMEOUT, check_response, http_session, parse_period, to_rows

load_dotenv()

COLUMNS = ['callId', 'date', 'callerNumber', 'utmSource', 'utmMedium', 'utmCampaign', 'utmContent',
           'utmTerm', 'siteName']

UPSERT = """INSERT INTO calltouch_data
                (callId, date, callerNumber, utmSource, utmMedium, utmCampaign, utmContent, utmTerm, siteName)
            VALUES %s
            ON CONFLICT (siteName, callId)
            DO UPDATE SET
                date = EXCLUDED.date,
                callernumber = EXCLUDED.callerNumber,
                utmsource = EXCLUDED.utmSource,
                utmmedium = EXCLUDED.utmMedium,
                utmcampaign = EXCLUDED.utmCampaign,
                utmcontent = EXCLUDED.utmContent,
                utmterm = EXCLUDED.utmTerm"""

logger = get_logger('calltouch')


class Calltouch:
    def __init__(self, site_id, token):
        self.site_id = site_id
        self.__token = token
        self.session = http_session()

    def get_data(self, date_from, date_to):
        """Все звонки за период (даты включительно), со всех страниц."""
        url = f'https://api.calltouch.ru/calls-service/RestAPI/{self.site_id}/calls-diary/calls'
        params = {
            'clientApiId': self.__token,
            'dateFrom': date_from.strftime('%d/%m/%Y'),
            'dateTo': date_to.strftime('%d/%m/%Y'),
            'limit': 500,
        }
        records, page = [], 1
        while True:
            response = self.session.get(url, params={**params, 'page': page}, timeout=TIMEOUT)
            data = check_response(response, 'Calltouch')
            records.extend(data['records'])
            if page >= data['pageTotal']:
                break
            page += 1
        logger.info(f'Данные Calltouch за {date_from} — {date_to} получены: {len(records)} звонков')
        return records

    @staticmethod
    def to_df(records):
        df = pd.DataFrame(records, columns=COLUMNS)
        df['date'] = pd.to_datetime(df['date'], dayfirst=True)
        # Повтор ключа в одном INSERT ... ON CONFLICT вызывает ошибку
        return df.drop_duplicates(['siteName', 'callId'], keep='last')

    @staticmethod
    def to_db(df):
        if df.empty:
            return
        conn = connect()
        try:
            with conn, conn.cursor() as cur:
                bulk_insert(cur, UPSERT, to_rows(df))
        finally:
            conn.close()
        logger.info(f'В БД calltouch_data записано {len(df)} строк')


def main():
    parser = argparse.ArgumentParser(description='Выгрузка звонков Calltouch в БД')
    parser.add_argument('--date-from', help='YYYY-MM-DD, по умолчанию вчера')
    parser.add_argument('--date-to', help='YYYY-MM-DD включительно, по умолчанию вчера')
    args = parser.parse_args()
    date_from, date_to = parse_period(args.date_from, args.date_to)

    ct = Calltouch(site_id=os.getenv('ct_site_id'), token=os.getenv('ct_api_token'))
    ct.to_db(ct.to_df(ct.get_data(date_from, date_to)))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        logger.exception('Критическая ошибка')
        sys.exit(1)
