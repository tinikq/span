from datetime import date
from json import dumps, load
import json
import sqlite3
from time import sleep
from typing import List, Dict, Any

from fake_useragent import UserAgent
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from transliterate import translit

from config import Config
from logger import setup_logger
from models import Match, ParseResult

class WebDriver:
    def __init__(self):
        options = Options()
        options.add_argument(f"user-agent={UserAgent().random}")
        options.set_preference("security.ssl.enable_ocsp_stapling", False)
        options.set_preference("security.ssl.enable_ocsp_must_staple", False)
        options.set_preference("security.ssl.errorReporting.automatic", False)
        
        # Добавляем новые настройки
        options.set_preference("marionette.enabled", True)
        options.set_preference("dom.webdriver.enabled", False)
        options.set_preference("network.http.connection-timeout", 60)
        
        self.driver = webdriver.Firefox(options=options)
        self.wait = WebDriverWait(self.driver, 50)
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.driver.quit()
        
logger = setup_logger()

class Parser:
    def __init__(self):
        # Используем только один WebDriver через класс WebDriver
        self.web_driver = WebDriver()
        self.driver = self.web_driver.driver
        self.wait = self.web_driver.wait
    
    def parse_main_page(self, url: str, sport_country: tuple[str, str]) -> list:
        matches = []
        try:
            logger.info(f"Начинаем парсинг страницы {url}")
            self.driver.get(url)
            
            element = self.wait.until(EC.presence_of_element_located((By.ID, "divmain")))
            soup = BeautifulSoup(element.get_attribute("outerHTML"), "html.parser")
            
            for table in soup.find_all("table", class_='l-t'):
                liga = table.find('a', class_='l-th-name').text.split()[2:]
                liga = ' '.join(liga)
                logger.info(f"Парсинг лиги: {liga}")
                
                for block in table.find_all("tr", class_="g-tr"):
                    match_data = self.parse_match(block, sport_country, liga)
                    if match_data:
                        matches.append(match_data)
        except Exception as exc:
            logger.error(f"Ошибка при парсинге главной страницы: {exc}")
            
        return matches
    
    def parse_match(self, block: BeautifulSoup, sport_country: tuple[str, str], liga: str) -> list:
        try:
            # Получаем дату и время
            date_time = block.find("div", class_="g-date").get_text(strip=True)
            date_match, time_match = date_time.split()
            
            if date_match != '01/11': #date.today().strftime('%d/%m'):
                return None
            
            # Получаем команды
            teams = [team.get_text(strip=True) for team in block.find_all("p")]

            
            # Получаем коэффициенты
            coefficients = [float(coef.get_text(strip=True).replace(",", ".")) if coef.get_text(strip=True) else 0
                          for coef in block.find_all("td", class_="cf")
                          if len(coef["class"]) == 1]
            
            # Получаем ссылку на матч
            link = block.find("a", class_="g-d g-d-s line")["href"]
            
            # Формируем данные матча
            match_data = [list(sport_country) + [liga, time_match, date_match] + teams + coefficients]
            additional_data = self.parse_match_page(link)
            match_data.append(additional_data)
            return match_data
            
        except Exception as exc:
            logger.error(f"Ошибка при парсинге матча: {exc}")
            return None
    
    def parse_match_page(self, link: str) -> str:
        try:
            self.driver.get("https://zenit.win" + link)
            result = {
                "Match will score a goal": {},
                "Corner individual total": {},
                "Corner Individual total 1st half": {},
                "Fouls individual total": {},
                "Fouls Individual total 1st half": {}
            }
            
            # Парсим таблицу "забьют гол"
            self.wait.until(EC.presence_of_element_located((By.ID, "table_1031")))
            soup = BeautifulSoup(self.driver.page_source, "html.parser")
            
            table = soup.find("div", id="table_1031").find('tbody').find_all('tr')
            for row in table:
                cells = row.find_all('td')
                name = translit(cells[0].get_text(strip=True), 'ru', reversed=True).replace("'", "")
                y = float(cells[1].get_text(strip=True).replace(',', '.')) if cells[1].get_text(strip=True) else 0
                n = float(cells[2].get_text(strip=True).replace(',', '.')) if cells[2].get_text(strip=True) else 0
                result["Match will score a goal"][name] = [y, n]
            # Пробуем парсить угловые и фолы
            for stat_type in ['Угловые', 'Фолы']:
                try:
                    button = self.wait.until(
                        EC.element_to_be_clickable(
                            (By.XPATH, f"//div[contains(@class, 'line-base-filter-item') and contains(text(), '{stat_type}')]")
                        )
                    )
                    sleep(1)
                    button.click()
                    sleep(2)
                    self.wait.until(EC.presence_of_element_located((By.ID, "table_266")))
                    self.wait.until(EC.presence_of_element_located((By.ID, "table_272")))

                    soup = BeautifulSoup(self.driver.page_source, "html.parser")
                    prefix = "Corner" if stat_type == 'Угловые' else "Fouls"
                    
                    # Парсим основные тоталы
                    for row in soup.find("div", id="table_266").find('tbody').find_all('tr'):
                        cells = row.find_all('td')
                        if len(cells) == 4:
                            name = transliterate_text(cells[0].get_text(strip=True))
                            result[f"{prefix} individual total"][name] = []
                        coefficients = [float(cell.get_text(strip=True).replace(',', '.')) if cell.get_text(strip=True) else 0 
                                        for cell in cells[-3:]]
                        result[f"{prefix} individual total"][name].append(coefficients)

                    # Парсим тоталы первого тайма
                    for row in soup.find("div", id="table_272").find('tbody').find_all('tr'):
                        cells = row.find_all('td')
                        if len(cells) == 4:
                            name = transliterate_text(cells[0].get_text(strip=True))
                            result[f"{prefix} Individual total 1st half"][name] = []
                        coefficients = [float(cell.get_text(strip=True).replace(',', '.')) if cell.get_text(strip=True) else 0 
                                        for cell in cells[-3:]]
                        result[f"{prefix} Individual total 1st half"][name].append(coefficients)
                
                except Exception as e:
                    logger.info(f"{stat_type} не найдены: {e}")
            
            return dumps(result, ensure_ascii=False)
            
        except Exception as exc:
            logger.error(f"Ошибка при парсинге угловых или фолы: {exc}")
            return dumps({}, ensure_ascii=False)
    
    def __del__(self):
        """Закрытие драйвера при удалении объекта"""
        if hasattr(self, 'web_driver'):
            self.web_driver.__exit__(None, None, None)  # Используем метод __exit__ класса WebDriver

def transliterate_text(text: str) -> str:
    return translit(text, 'ru', reversed=True).replace("'", "")

def main_parse(url: str, sport_country: tuple[str, str]) -> list[list]:
    parser = Parser()
    return parser.parse_main_page(url, sport_country)

class Database:
    def __init__(self):
        self.db_name = Config.DB_NAME
        
    def save_matches(self, matches: List[Match]) -> None:
        with sqlite3.connect(self.db_name) as db:
            cursor = db.cursor()
            self._create_table(cursor)
            self._insert_matches(cursor, matches)
            db.commit()
    
    def _create_table(self, cursor: sqlite3.Cursor) -> None:
        table_name = date.today().strftime('matches')
        cursor.execute(f'''CREATE TABLE IF NOT EXISTS "{table_name}" (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sport TEXT,
            country TEXT,
            liga TEXT,
            time_start TIME,
            date_start DATE,
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
            T NUMERIC(6,3) DEFAULT NULL,
            B NUMERIC(6,3) DEFAULT NULL,
            additional_data JSON
        )''')
    
    def _insert_matches(self, cursor: sqlite3.Cursor, matches: List[list]) -> None:
        """Вставка матчей в базу данных"""
        table_name = date.today().strftime('matches')
        for match_data in matches:
            # match_data[0] содержит основные данные
            # match_data[1] содержит additional_coefficients
            main_data = match_data[0]  # [sport, country, liga, time, date, team1, team2, *coefficients]
            additional_data = match_data[1]  # JSON строка с дополнительными коэффициентами

            cursor.execute(f'''
                INSERT INTO "{table_name}" 
                (sport, country, liga, time_start, date_start, team1, team2, 
                 W1, X, W2, H1, HV1, H2, HV2, M, T, B, additional_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                main_data[0],  # sport
                main_data[1],  # country
                main_data[2],  # liga
                main_data[3],  # time_start
                main_data[4],  # date_start
                main_data[5],  # team1
                main_data[6],  # team2
                *main_data[7:],  # все коэффициенты
                additional_data  # JSON строка с дополнительными данными
            ))

def main():
    parser = Parser()
    db = Database()
    
    with open(Config.URLS_FILE, "r", encoding="utf-8") as f:
        urls = load(f)
    
    all_matches = []  # Список для хранения всех матчей
    errors = []  # Список для хранения ошибок
    
    # Простой последовательный парсинг
    for sport, countries in urls.items():
        for country, url in countries.items():
            try:
                matches = parser.parse_main_page(url, (sport, country))
                if matches:  # Если есть матчи, добавляем их в общий список
                    all_matches.extend(matches)
            except Exception as e:
                errors.append(str(e))
    
    if all_matches:
        db.save_matches(all_matches)
    
    if errors:
        print("Ошибки при парсинге:")
        for error in errors:
            print(error)

if __name__ == '__main__':
    main()
