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
from models import Match, ParseResult

class WebDriver:
    def __init__(self):
        self.options = self._setup_options()
        self.driver = webdriver.Firefox(options=self.options)
        self.wait = WebDriverWait(self.driver, 50)
    
    def _setup_options(self) -> Options:
        options = Options()
        options.add_argument(f"user-agent={UserAgent().random}")
        options.set_preference("security.ssl.enable_ocsp_stapling", False)
        options.set_preference("security.ssl.enable_ocsp_must_staple", False)
        options.set_preference("security.ssl.errorReporting.automatic", False)
        return options
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.driver.quit()

class Parser:
    def __init__(self):
        self.web_driver = WebDriver()
        self.driver = self.web_driver.driver
        self.wait = self.web_driver.wait
    
    def parse_main_page(self, url: str, sport_country: tuple[str, str]) -> ParseResult:
        """Парсинг главной страницы со списком матчей"""
        matches = []
        errors = []
        try:
            self.driver.get(url)
            sleep(1)
            element = self.wait.until(EC.presence_of_element_located((By.ID, "divmain")))
            html_code = element.get_attribute("outerHTML")
            soup = BeautifulSoup(html_code, "html.parser")
            
            for table in soup.find_all("table", class_='l-t'):
                table_result = self._parse_table(table, sport_country)
                matches.extend(table_result)
                
        except Exception as exc:
            error_msg = f"Ошибка при парсинге главной страницы {url}: {exc}"
            print(error_msg)
            errors.append(error_msg)
            
        return ParseResult(matches=matches, errors=errors)
    
    def _parse_table(self, table: BeautifulSoup, sport_country: tuple[str, str]) -> list[list]:
        """Парсинг отдельной таблицы с матчами"""
        result = []
        try:
            match_blocks = table.find_all("tr", class_="g-tr")
            liga = table.find('a', class_='l-th-name').text.split()[2]
            
            for block in match_blocks:
                match_data = self._parse_match_block(block, sport_country, liga)
                if match_data:
                    result.append(match_data)
                    
        except Exception as exc:
            print(f"Ошибка при парсинге таблицы: {exc}")
            
        return result
    
    def _parse_match_block(self, block: BeautifulSoup, sport_country: tuple[str, str], liga: str) -> list:
        """Парсинг блока с информацией о матче"""
        try:
            # Проверяем наличие элементов перед их использованием
            date_div = block.find("div", class_="g-date")
            if not date_div:
                print("Не найден элемент с датой")
                return None
                
            date_time = date_div.get_text(strip=True)
            if not date_time:
                print("Пустое значение даты/времени")
                return None
                
            try:
                date_match, time_match = date_time.split()
            except ValueError:
                print(f"Неверный формат даты/времени: {date_time}")
                return None
            
            # Проверка даты
            if date_match != '29/10': #date.today().strftime('%d/%m'):
                return None
                
            date_match = date.today().isoformat()
            
            # Парсинг команд с проверкой
            teams = []
            team_elements = block.find_all("p")
            if len(team_elements) != 2:
                print("Неверное количество команд")
                return None
                
            for team in team_elements:
                team_name = team.get_text(strip=True)
                if not team_name:
                    print("Пустое название команды")
                    return None
                teams.append(team_name)
            
            # Парсинг коэффициентов с проверкой
            coefficients = []
            coef_elements = block.find_all("td", class_="cf")
            for coef in coef_elements:
                if len(coef["class"]) != 1:
                    continue
                coef_text = coef.get_text(strip=True)
                coef_value = float(coef_text.replace(",", ".")) if coef_text else 0
                coefficients.append(coef_value)
            
            # Проверяем наличие ссылки
            link_element = block.find("a", class_="g-d g-d-s line")
            if not link_element or "href" not in link_element.attrs:
                print("Не найдена ссылка на матч")
                return None
                
            link = link_element["href"]
            
            # Формирование данных матча
            match_data = [list(sport_country) + [liga, time_match, date_match] + teams + coefficients]
            additional_coefficients = self.parse_match_page(link)
            match_data.append(additional_coefficients)
            
            return match_data
            
        except Exception as exc:
            print(f"Ошибка при парсинге блока матча: {exc}")
            return None
    
    def parse_match_page(self, link: str) -> str:
        """Парсинг страницы отдельного матча"""
        try:
            self.driver.get("https://zenit.win" + link)
            
            # Используем ID напрямую
            self.wait.until(EC.presence_of_element_located((By.ID, "table_1031")))
            page = self.driver.page_source
            soup_match = BeautifulSoup(page, "html.parser")
            
            result = self._initialize_result_dict()
            self._parse_will_score_table(soup_match, result)
            self._parse_corners_table(result)
            
            return dumps(result, ensure_ascii=False)
            
        except Exception as exc:
            print(f"Ошибка при парсинге страницы матча {link}: {exc}")
            return dumps({}, ensure_ascii=False)
    
    def _initialize_result_dict(self) -> dict:
        """Инициализация словаря результатов"""
        return {
            "Match will score a goal": {},
            "Corner individual total": {},
            "Corner Individual total 1st half": {},
            "Fouls individual total": {},
            "Fouls Individual total 1st half": {}
        }
    
    def _parse_will_score_table(self, soup: BeautifulSoup, result: dict) -> None:
        """Парсинг таблицы 'забьют гол'"""
        table = soup.find(
            "div", 
            id="table_1031"  # Используем ID напрямую вместо Config.TABLES_CONFIG
        ).find('tbody').find_all('tr')
        for row in table:
            cells = row.find_all('td')
            name = transliterate_text(cells[0].get_text(strip=True))
            y = float(cells[1].get_text(strip=True).replace(',', '.')) if cells[1].get_text(strip=True) else 0
            n = float(cells[2].get_text(strip=True).replace(',', '.')) if cells[2].get_text(strip=True) else 0
            result["Match will score a goal"][name] = [y, n]
    
    def _parse_corners_table(self, result: dict) -> None:
        """Парсинг таблицы угловых"""
        try:
            # Добавляем повторные попытки и дополнительное ожидание
            max_attempts = 3
            for attempt in range(max_attempts):
                try:
                    # Ждем появления кнопки
                    corners_button = self.wait.until(
                        EC.element_to_be_clickable(
                            (By.XPATH, "//div[contains(@class, 'line-base-filter-item') and text()='Угловы']")
                        )
                    )
                    # Добавляем небольшую паузу перед кликом
                    sleep(1)
                    corners_button.click()
                    
                    # Ждем загрузки обеих таблиц
                    self.wait.until(EC.presence_of_element_located((By.ID, "table_266")))
                    self.wait.until(EC.presence_of_element_located((By.ID, "table_272")))
                    
                    # Добавляем паузу после загрузки таблиц
                    sleep(1)
                    
                    # Получаем обновленный HTML после клика
                    soup = BeautifulSoup(self.driver.page_source, "html.parser")
                    self._parse_corner_totals(soup, result)
                    break  # Если успешно, выходим из цикла
                    
                except Exception as e:
                    if attempt == max_attempts - 1:  # Если это была последняя попытка
                        raise e
                    sleep(2)  # Ждем перед следующей попыткой
            
        except Exception as exc:
            print(f"Ошибка при парсинге угловых: {exc}")
    
    def _parse_corner_totals(self, soup: BeautifulSoup, result: dict) -> None:
        """Парсинг тоталов угловых"""
        try:
            # Используем ID напрямую
            corners_table = soup.find(
                "div", 
                id="table_266"  # Используем ID напрямую вместо Config.TABLES_CONFIG
            ).find('tbody').find_all('tr')
            
            # Парсинг основных тоталов угловых
            for row in corners_table:
                cells = row.find_all('td')
                if len(cells) == 4:  
                    name = transliterate_text(cells[0].get_text(strip=True))

                coefficients = [
                    float(cell.get_text(strip=True).replace(',', '.')) 
                    if cell.get_text(strip=True) else 0 
                    for cell in cells[-3:]
                    ]
                result["Corner individual total"][name] = coefficients
            
            # Парсинг тоталов угловых первого тайма
            first_half_table = soup.find(
                "div", 
                id="table_272"  # Используем ID напрямую вместо Config.TABLES_CONFIG
            ).find('tbody').find_all('tr')
            for row in first_half_table:
                cells = row.find_all('td')
                if len(cells) == 4:
                    name = transliterate_text(cells[0].get_text(strip=True))

                coefficients = [
                    float(cell.get_text(strip=True).replace(',', '.')) 
                    if cell.get_text(strip=True) else 0 
                    for cell in cells[-3:]
                    ]
                result["Corner Individual total 1st half"][name] = coefficients
                
        except Exception as exc:
            print(f"Ошибка при парсинге тоталов угловых: {exc}")

    def __del__(self):
        """Закрытие драйвера при удалении объекта"""
        if hasattr(self, 'web_driver'):
            self.web_driver.__exit__(None, None, None)

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
                 W1, X, W2, H1, HV1, H2, HV2, M, B, additional_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
    
    results = ParseResult(matches=[], errors=[])
    
    # Простой последовательный парсинг
    for sport, countries in urls.items():
        for country, url in countries.items():
            try:
                result = parser.parse_main_page(url, (sport, country))
                results.matches.extend(result.matches)
                results.errors.extend(result.errors)
            except Exception as e:
                results.errors.append(str(e))
    
    if results.matches:
        db.save_matches(results.matches)
    
    if results.errors:
        print("Ошибки при парсинге:")
        for error in results.errors:
            print(error)

if __name__ == '__main__':
    main()
