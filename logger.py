import logging
from datetime import datetime
import os

def setup_logger():
    # Создаем директорию для логов, если её нет
    if not os.path.exists('logs'):
        os.makedirs('logs')
    
    # Настраиваем формат логирования
    log_format = '%(asctime)s - %(levelname)s - %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'
    
    # Создаем файл лога с текущей датой
    log_file = f'logs/parser_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
    
    # Настраиваем логгер
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        datefmt=date_format,
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()  # Вывод в консоль
        ]
    )
    
    return logging.getLogger(__name__) 