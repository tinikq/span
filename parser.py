from datetime import date, datetime

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support.wait import WebDriverWait

import re
import sqlite3


def parse_matches(data: str, sport_country: str) -> list[tuple]:
    pattern = re.compile(r"(\d{2}/\d{2})\s+(\d{2}:\d{2})\n([А-Яа-я\s]+)\n([А-Яа-я\s]+)(?:\nМатч.*)?\n([\d,. \-+]+)")
    matches = []
    year = datetime.now().strftime('%Y-')

    for match in pattern.findall(data):
        date = year + match[0][::-1].replace('/', '-', 1)[::-1]
        time = match[1]
        team1 = match[2].strip()
        team2 = match[3].strip()
        odds = [x.replace(',', '.') for x in match[4].split()]
        if len(odds) == 10:
            odds.insert(1, 0)
        elif len(odds) == 8:
            odds = [0, 0, 0] + odds
        matches.append((date, time, team1, team2, *odds, *sport_country))

    return matches


def parser_SE():
    url = 'https://www.sport-express.ru/stavki-na-sport/'

    user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)'
    options = Options()
    # options.add_argument('--headless')
    options.add_argument(f'user-agent={user_agent}')
    driver = webdriver.Firefox(options=options)
    driver.get(url)  # открываем страницу
    wait = WebDriverWait(driver, 100)  # ожидание загрузки страницы
    # elements = wait.until(EC.presence_of_all_elements_located((By.CLASS_NAME, "g-tr")))


def parser_zenit():
    urls = {
        ('Футбол', 'Россия'): 'https://zenit.win/line/football/r_11_russia',
        ('Футбол', 'Англия'): 'https://zenit.win/line/football/r_37_england',
        ('Футбол', 'Германия'): 'https://zenit.win/line/football/r_41_germany',
        ('Футбол', 'Испания'): 'https://zenit.win/line/football/r_40_spain',
        ('Футбол', 'Италия'): 'https://zenit.win/line/football/r_43_italy',
        ('Футбол', 'Франция'): 'https://zenit.win/line/football/r_45_france',
        ('Баскетбол', 'Россия'): 'https://zenit.win/line/basketball/r_10_russia',
        ('Баскетбол', 'США'): 'https://zenit.win/line/basketball/r_9_usa',
        ('Хоккей', 'Россия'): 'https://zenit.win/line/ice-hockey/r_32_russia',
        ('Хоккей', 'Германия'): 'https://zenit.win/line/ice-hockey/r_355_germany',
        ('Хоккей', 'США'): 'https://zenit.win/line/ice-hockey/r_12_usa'}

    # настройка драйвера, добавляем фейковый юзер агент
    user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)'
    options = Options()
    # options.add_argument('--headless')
    options.add_argument(f'user-agent={user_agent}')
    driver = webdriver.Firefox(options=options)

    try:
        for sport_country, url in urls.items():
            try:
                driver.get(url)
                wait = WebDriverWait(driver, 100)
                elements = wait.until(EC.presence_of_all_elements_located((By.CLASS_NAME, "g-tr")))

                elements = [element.text for element in elements]
                elements = parse_matches('\n'.join(elements), sport_country)
                yield elements
            except:
                continue
    finally:
        driver.close()  # гарантированное закрытие драйвера


def db_record():
    with sqlite3.connect('data_bet.db') as db:
        cursor = db.cursor()
        today = date.today().strftime('%Y%m%d')
        cursor.execute(f'''CREATE TABLE IF NOT EXISTS "{today}" (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            date DATE,
                            time_start TIME,
                            team1 TEXT,
                            team2 TEXT,
                            W1 NUMERIC(6,3) DEFAULT NULL,
                            X NUMERIC(6,3) DEFAULT NULL,
                            W2 NUMERIC(6,3) DEFAULT NULL,
                            H1 NUMERIC(6,3) DEFAULT NULL,
                            HV1 NUMERIC(6,3) DEFAULT NULL,
                            H2 NUMERIC(6,3) DEFAULT NULL,
                            HV2 NUMERIC(6,3) DEFAULT NULL,
                            M NUMERIC(6,3) DEFAULT NULL,
                            total INTEGER DEFAULT NULL,
                            B NUMERIC(6,3) DEFAULT NULL,
                            extra INTEGER DEFAULT NULL,
                            sport TEXT,
                            country TEXT)''')

        for data in parser_zenit():
            cursor.executemany(f'''INSERT INTO "{today}"
            (date, time_start, team1, team2, W1, X, W2, H1, HV1, H2, HV2, M, total, B, extra, sport, country)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', data)
            db.commit()  # записываем данные в базу



def main():
    db_record()


if __name__ == '__main__':
    main()
