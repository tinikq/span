from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from json import load, dumps
import sqlite3
from time import sleep
from fake_useragent import UserAgent
from transliterate import translit

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from transliterate import translit


def transliterate_text(text: str) -> str:
    return translit(text, 'ru', reversed=True).replace("'", "")

def main_parse(url: str, sport_country: tuple[str, str]) -> list[list]:

    # настраиваев driver
    user_agent = UserAgent().random
    options = Options()
    # options.add_argument("--headless")  # не отображать браузер
    options.add_argument(f"user-agent={user_agent}")

    #настройки для игнорироваия ошибок ssl (есть смысл или нет не известно)
    options.set_preference("security.ssl.enable_ocsp_stapling", False)
    options.set_preference("security.ssl.enable_ocsp_must_staple", False)
    options.set_preference("security.ssl.errorReporting.automatic", False)

    driver = webdriver.Firefox(options=options)
    result = []

    try:
        # достаем необходимую страницу и сразу преабразуем ее в html код
        driver.get(url)
        sleep(1)
        wait = WebDriverWait(driver, 50)
        element = wait.until(EC.presence_of_element_located((By.ID, "divmain")))
        html_code = element.get_attribute("outerHTML")
        soup = BeautifulSoup(html_code, "html.parser")

        for table in soup.find_all("table", class_='l-t'): # проходим по всем таблицам
            match_blocks = table.find_all("tr", class_="g-tr")  # Все матчи в таблице
            liga = table.find('a', class_='l-th-name').text.split()[2] # дос��аем название лиги

            for block in match_blocks:  # проходим по всем матчам
                # достаем дату и время
                date_time = block.find("div", class_="g-date").get_text(strip=True)
                date_match, time_match = date_time.split()
                # если дата не соответствует текущей, то пропускаем
                if date_match != date.today().strftime('%d/%m'):
                    continue
                # переводим дату в isoformat
                date_match = date.today().isoformat()

                teams = [team.get_text(strip=True) for team in block.find_all("p")] # достаем названия команд
                # достаем коэффициенты
                coefficients = [
                    float(coef.get_text(strip=True).replace(",", ".")) if coef.get_text(strip=True) != "" else 0 # если коэффициент пустой то переводим 0
                    for coef in block.find_all("td", class_="cf")
                    if len(coef["class"]) == 1  # проверяем, что класс только один - "cf" что бы не было лишних коэффициентов
                    ]
                # достаем ссылку на страницу
                link = block.find("a", class_="g-d g-d-s line")["href"]


                

                match_data = [list(sport_country) + [liga, time_match, date_match] + teams + coefficients] 
                match_data.append(coefficients_parse(link, driver, wait))
                result.append(match_data)
    except Exception as exc:
        print(f"Ошибка при парсинге на главной страницы {url}: {exc}")

    return result

def coefficients_parse(link: str, driver: webdriver.Firefox, wait: WebDriverWait):
    '''
    Тут происходит парсинг коэффициентов по ссылке на сам матч, таких как:
    "забьют гол", "угловые индивидуальный тотал", "удары от ворот индивидуальный тотал", "фолы индивидуальный тотал"
    а так же результатом возврощается серилизованный json словарь
    '''
    driver.get("https://zenit.win" + link)

    # достаем таблицу "wait = WebDriverWait(driver, 50)
    wait.until(EC.presence_of_element_located((By.ID, "table_1031")))
    page = driver.page_source
    # форматируемм ее
    
    soup_match = BeautifulSoup(page, "html.parser")
    table_will_score_a_goal = soup_match.find("div", id="table_1031").find('tbody').find_all('tr')

    # создаем словарь для результата
    result = {"Match will score a goal": {},
              "Corner individual total": {},
              "Corner Individual total 1st half": {},
              "Fouls individual total": {},
              "Fouls Individual total 1st half": {}
              }
    
    # парсим таблицу "забьют гол"
    for keys in table_will_score_a_goal:
        cells = keys.find_all('td')
        name = transliterate_text(cells[0].get_text(strip=True)) # достаем название ставки и переводим в латиницу
        if cells[1].get_text(strip=True) == "":
            y = 0
        else:
            y = float(cells[1].get_text(strip=True).replace(',', '.'))  
        if cells[2].get_text(strip=True) == "":
            n = 0
        else:
            n = float(cells[2].get_text(strip=True).replace(',', '.'))
        result["Match will score a goal"][name] = [y, n]

    # парсим таблицу "угловые индивидуальный тотал" в случае если он есть
    try:
        corners_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//div[contains(@class, 'line-base-filter-item') and text()='Угловые']")))
        corners_button.click()

        # ждем пока загрузятся таблицы
        wait.until(EC.presence_of_element_located((By.ID, "table_266")))
        wait.until(EC.presence_of_element_located((By.ID, "table_272")))

        page = driver.page_source
        soup = BeautifulSoup(page, "html.parser")
        rows = soup.find("div", id="table_266").find('tbody').find_all('tr')

        # парсим таблицу "угловые индивидуальный тотал"
        for keys in rows:
            cells = keys.find_all('td')
            if len(cells) == 4:
                name = transliterate_text(cells[0].get_text(strip=True))
            tr_coef = [float(i.get_text(strip=True).replace(',', '.')) if i.get_text(strip=True) else 0 for i in cells[-3:]]
            result["Fouls individual total"][name] = tr_coef
        
        rows = soup.find("div", id="table_272").find('tbody').find_all('tr')
    except Exception as e:
        print(f'Ошибка при парсинге "Угловые" на странице {link}')

    result_json = dumps(result, ensure_ascii=False)
    return result_json
  

def parser_football():
    
    with open("urls/zenit_urls.json", "r", encoding="utf-8") as f:
        data = load(f)

    urls = {
        (sport, country): url
        for sport, countries in data.items()
        for country, url in countries.items()
    }

    results = []

    with ThreadPoolExecutor(max_workers=3) as executor:  # 6 потоков
        future_to_url = {
            executor.submit(main_parse, url, sport_country): url
            for sport_country, url in urls.items()
        }

        for future in as_completed(future_to_url):
            url = future_to_url[future]
            try:
                data = future.result()
                results.extend(data)
                
            except Exception as exc:
                print(f"Ошибка при парсинге {url}: {exc}")

        return results

def db_record(data: list[list]) -> None:
       with sqlite3.connect('data_bet.db') as db:
        cursor = db.cursor()
        today = date.today().strftime('mathes')
        cursor.execute(f'''CREATE TABLE IF NOT EXISTS "{today}" (
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
                            B NUMERIC(6,3) DEFAULT NULL
                            ''')


        cursor.executemany(f'''INSERT INTO "{today}"
        (sport, country, liga, time_start, team1, team2, W1, X, W2, H1, HV1, H2, HV2, M, total, B, extra, both_teams_Y, both_teams_N, both_teams_1_Y, both_teams_1_N, both_teams_2_Y, both_teams_2_N, both_teams_12_Y, both_teams_12_N, first_half_gool_Y, first_half_gool_N)
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', data)
        db.commit()  # записываем данные в базу


if __name__ == '__main__':
    db_record(parser_football())    


