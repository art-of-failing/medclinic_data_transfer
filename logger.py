from datetime import datetime
import logging
import os

from dotenv import load_dotenv

load_dotenv()

LOG_DIR = os.getenv('log_dir', '/home/contractor/scripts/log')


def get_logger(name):
    """Логгер, пишущий в файл log_dir/ГГГГ-ММ-ДД.log (общий для всех скриптов)."""
    root = logging.getLogger()
    if not root.handlers:
        os.makedirs(LOG_DIR, exist_ok=True)
        file_name = os.path.join(LOG_DIR, datetime.today().strftime('%Y-%m-%d') + '.log')
        handler = logging.FileHandler(file_name, encoding='UTF-8')
        handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        root.addHandler(handler)
        root.setLevel(logging.INFO)
    return logging.getLogger(name)
