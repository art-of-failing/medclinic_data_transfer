from datetime import date, datetime, timedelta

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

TIMEOUT = 30


def http_session():
    """Сессия с повторами при сетевых ошибках и ответах 429/5xx."""
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=2, status_forcelist=[429, 500, 502, 503, 504],
                  allowed_methods=None)
    session.mount('https://', HTTPAdapter(max_retries=retry))
    return session


def check_response(response, what):
    if response.status_code != 200:
        raise RuntimeError(f'Ошибка запроса {what}. Код ответа: {response.status_code}. '
                           f'Тело ответа: {response.text[:500]}')
    return response.json()


def format_phone(phones):
    """Приводит телефоны к виду 7XXXXXXXXXX. Меньше 10 цифр -> NA, больше 11 -> цифры как есть."""
    digits = phones.astype('string').str.replace(r'\D', '', regex=True).fillna('')
    length = digits.str.len()
    starts_7_8 = digits.str[:1].isin(['7', '8'])

    result = pd.Series(pd.NA, index=phones.index, dtype='string')
    trim = (length == 11) & starts_7_8
    keep = ((length == 11) & ~starts_7_8) | (length == 10)
    result[trim] = '7' + digits[trim].str[1:]
    result[keep] = '7' + digits[keep]
    result[length > 11] = digits[length > 11]
    return result


def to_rows(df):
    """DataFrame -> список кортежей с питоновскими типами и None вместо пропусков."""
    df = df.astype(object).where(df.notna(), None)
    return list(df.itertuples(index=False, name=None))


def parse_period(args_from, args_to):
    """Период из аргументов YYYY-MM-DD (включительно), по умолчанию — вчера."""
    yesterday = date.today() - timedelta(days=1)
    date_from = datetime.strptime(args_from, '%Y-%m-%d').date() if args_from else yesterday
    date_to = datetime.strptime(args_to, '%Y-%m-%d').date() if args_to else yesterday
    return date_from, date_to
