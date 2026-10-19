import argparse
from datetime import timedelta
import os
import sys

from dotenv import load_dotenv
import pandas as pd

from logger import get_logger
from psgsql_connect import bulk_insert, connect
from utils import TIMEOUT, check_response, format_phone, http_session, parse_period, to_rows

load_dotenv()

SOURCE_FIELD = 'UF_CRM_1760353216'

COLUMNS = ['id', 'createdTime', 'stageId', 'phone', 'utmSource', 'utmMedium', 'utmCampaign', 'utmContent',
           'utmTerm', 'SOURCE', 'SOURCE_DESCRIPTION']

UPSERT = """INSERT INTO bitrix_data
                (id, createdTime, stageId, phone, utmSource, utmMedium, utmCampaign, utmContent, utmTerm,
                 source, sourceDescription)
            VALUES %s
            ON CONFLICT (id)
            DO UPDATE SET
                createdTime = EXCLUDED.createdTime,
                stageId = EXCLUDED.stageId,
                phone = EXCLUDED.phone,
                utmSource = EXCLUDED.utmSource,
                utmMedium = EXCLUDED.utmMedium,
                utmCampaign = EXCLUDED.utmCampaign,
                utmContent = EXCLUDED.utmContent,
                utmTerm = EXCLUDED.utmTerm,
                source = EXCLUDED.source,
                sourceDescription = EXCLUDED.sourceDescription"""

logger = get_logger('bitrix')


class Bitrix:
    def __init__(self, host, token, user):
        self.base_url = f'https://{host}.bitrix24.ru/rest/{user}/{token}'
        self.session = http_session()

        sources = self._call('crm.status.entity.items', {'entityId': 'SOURCE'}, 'справочник источников')
        self.source_df = (pd.DataFrame(sources['result'])[['STATUS_ID', 'NAME']]
                          .rename(columns={'NAME': 'SOURCE'}))

        fields = self._call('crm.item.fields', {'entityTypeId': 1, 'useOriginalUfNames': 'Y'},
                            'пользовательское поле')
        df = pd.DataFrame(fields['result']['fields'][SOURCE_FIELD]['items'])
        df.columns = ['ID', 'SOURCE_DESCRIPTION']
        df['ID'] = df['ID'].astype('int64')
        self.source_detail_df = df

    def _call(self, method, data, what):
        response = self.session.post(f'{self.base_url}/{method}', json=data, timeout=TIMEOUT)
        return check_response(response, f'Bitrix ({what})')

    def get_data(self, date_from, date_to):
        """Лиды, созданные с date_from 00:00 по date_to 23:59:59, со всех страниц."""
        data = {
            'entityTypeId': 1,
            'select': ['id', 'createdTime', 'stageId', 'phone', 'utmSource', 'utmMedium', 'utmCampaign',
                       'utmContent', 'utmTerm', 'sourceId', 'ufCrm_1760353216'],
            'useOriginalUfNames': 'N',
            'filter': {
                '>=createdTime': date_from.strftime('%Y-%m-%dT00:00:00+03:00'),
                '<createdTime': (date_to + timedelta(days=1)).strftime('%Y-%m-%dT00:00:00+03:00'),
            },
            'order': {'createdTime': 'DESC'},
            'start': 0,
        }
        items = []
        while True:
            result = self._call('crm.item.list', data, 'лиды')
            items.extend(result['result']['items'])
            if 'next' not in result:
                break
            data['start'] = result['next']
        logger.info(f'Данные Bitrix за {date_from} — {date_to} получены: {len(items)} лидов')
        return items

    def to_df(self, items):
        df = pd.DataFrame(items)
        df['createdTime'] = pd.to_datetime(df['createdTime'], format='%Y-%m-%dT%H:%M:%S+03:00')
        df['phone'] = format_phone(df['phone'])
        df = (df
              .merge(self.source_df, how='left', left_on='sourceId', right_on='STATUS_ID')
              .merge(self.source_detail_df, how='left', left_on='ufCrm_1760353216', right_on='ID'))
        return df[COLUMNS].drop_duplicates('id', keep='last')

    @staticmethod
    def to_db(df):
        conn = connect()
        try:
            with conn, conn.cursor() as cur:
                bulk_insert(cur, UPSERT, to_rows(df))
        finally:
            conn.close()
        logger.info(f'В БД bitrix_data записано {len(df)} строк')


def main():
    parser = argparse.ArgumentParser(description='Выгрузка лидов Bitrix24 в БД')
    parser.add_argument('--date-from', help='YYYY-MM-DD, по умолчанию вчера')
    parser.add_argument('--date-to', help='YYYY-MM-DD включительно, по умолчанию вчера')
    args = parser.parse_args()
    date_from, date_to = parse_period(args.date_from, args.date_to)

    bitrix = Bitrix(os.getenv('bitrix_host'), os.getenv('bitrix_token'), os.getenv('bitrix_user'))
    items = bitrix.get_data(date_from, date_to)
    if items:
        bitrix.to_db(bitrix.to_df(items))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        logger.exception('Критическая ошибка')
        sys.exit(1)
