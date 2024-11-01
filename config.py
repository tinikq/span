from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class Config:
    DB_NAME: str = 'data_bet.db'
    BASE_URL: str = 'https://zenit.win'
    URLS_FILE: str = "urls/zenit_urls.json"
    WAIT_TIMEOUT: int = 50
