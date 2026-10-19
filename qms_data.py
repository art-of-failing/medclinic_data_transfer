import glob
import os
import sys
import xml.etree.ElementTree as ET
import zipfile

from dotenv import load_dotenv
import pandas as pd

from logger import get_logger
from psgsql_connect import bulk_insert, connect
from utils import format_phone, to_rows

load_dotenv()
QMS_DIR = os.getenv('qms_dir', '/home/contractor/qms_files')
PROCESSED_FILE = os.path.join(QMS_DIR, 'processed_files.txt')
FILE_PATTERNS = ['call*.xls', 'call*.ods']
ODS_TABLE = '{urn:oasis:names:tc:opendocument:xmlns:table:1.0}'

COLUMNS = ['Дата начала звонка', 'Тип', 'Телефон', 'Рег №', 'Тема звонка', 'Отделение', 'Врач',
           'Источник сведений', 'Результат звонка', 'ФИО оператора']

logger = get_logger('qms')


def read_processed():
    if not os.path.exists(PROCESSED_FILE):
        return set()
    with open(PROCESSED_FILE, 'r', encoding='UTF-8') as f:
        # basename — чтобы старые записи с полными путями тоже распознавались
        return {os.path.basename(line.strip()) for line in f if line.strip()}


def mark_processed(files):
    with open(PROCESSED_FILE, 'a', encoding='UTF-8') as f:
        for file in files:
            f.write(os.path.basename(file) + '\n')


def read_ods(file):
    """Таблица из .ods. QMS пишет архив без файла mimetype, поэтому pandas/odfpy его не открывают —
    разбираем content.xml напрямую."""
    with zipfile.ZipFile(file) as z:
        root = ET.fromstring(z.read('content.xml'))

    rows = []
    for row in root.iter(ODS_TABLE + 'table-row'):
        values = []
        for cell in row:
            if cell.tag not in (ODS_TABLE + 'table-cell', ODS_TABLE + 'covered-table-cell'):
                continue
            text = '\n'.join(''.join(p.itertext()) for p in cell).strip() or None
            # Пустые хвостовые ячейки бывают «повторены» тысячи раз — ограничиваем
            repeat = min(int(cell.get(ODS_TABLE + 'number-columns-repeated', 1)), 100)
            values.extend([text] * repeat)
        if any(v is not None for v in values):
            rows.append(values)

    header_idx = next(i for i, r in enumerate(rows) if r[0] == '№')
    header = [h.strip() if h else h for h in rows[header_idx]]
    data = [(r + [None] * len(header))[:len(header)] for r in rows[header_idx + 1:]]
    return pd.DataFrame(data, columns=header)


def read_file(file):
    if file.lower().endswith('.ods'):
        df = read_ods(file)
    else:
        df = pd.concat(pd.read_html(file, skiprows=3, header=0))
    df = df[pd.to_numeric(df['№'], errors='coerce').notna()]
    df['Дата начала звонка'] = pd.to_datetime(df['Дата звонка'] + ' ' + df['Время начала'],
                                              format='%d.%m.%Y %H:%M:%S')
    df['Телефон'] = format_phone(df['Телефон'])
    return df[COLUMNS]


def main():
    processed = read_processed()
    # Имена файлов вида callГГГГММДД_..., поэтому сортировка по имени = по дате выгрузки
    files = sorted((f for pattern in FILE_PATTERNS for f in glob.glob(os.path.join(QMS_DIR, pattern))
                    if os.path.basename(f) not in processed), key=os.path.basename)
    if not files:
        logger.info('Новых файлов нет')
        return

    frames, read_files = [], []
    for order, file in enumerate(files):
        try:
            df = read_file(file)
        except Exception:
            logger.exception(f'Ошибка чтения файла {file}, файл пропущен')
            continue
        df['_order'] = order
        frames.append(df)
        read_files.append(file)
        logger.info(f'Данные из файла {file} получены: {len(df)} строк')

    if not frames:
        raise RuntimeError('Не удалось прочитать ни одного файла')

    # Файлы пересекаются по датам: за каждый день берём данные только из самой свежей выгрузки
    df = pd.concat(frames, ignore_index=True)
    df['_day'] = df['Дата начала звонка'].dt.date
    df = df[df['_order'] == df.groupby('_day')['_order'].transform('max')]
    days = sorted(df['_day'].unique())

    conn = connect()
    try:
        with conn, conn.cursor() as cur:  # одна транзакция: при ошибке удаление откатится
            cur.execute('DELETE FROM qms_data WHERE date::date = ANY(%s)', (days,))
            deleted = cur.rowcount
            bulk_insert(cur, 'INSERT INTO qms_data VALUES %s', to_rows(df[COLUMNS]),
                        template='(DEFAULT,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)')
    finally:
        conn.close()

    logger.info(f'qms_data: удалено {deleted}, записано {len(df)} строк за {days[0]} — {days[-1]}')
    mark_processed(read_files)


if __name__ == '__main__':
    try:
        main()
    except Exception:
        logger.exception('Критическая ошибка')
        sys.exit(1)
