from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from json import load
import sqlite3
from time import sleep
from fake_useragent import UserAgent

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait


def parse_page(url, sport_country):

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
        wait = WebDriverWait(driver, 100)
        element = wait.until(EC.presence_of_element_located((By.ID, "divmain")))
        html_code = element.get_attribute("outerHTML")
        soup = BeautifulSoup(html_code, "html.parser")

        for table in soup.find_all("table", class_='l-t'):
            match_blocks = table.find_all("tr", class_="g-tr")  # Все таблицы
            liga = table.find('a', class_='l-th-name').text.split()[2]

            for block in match_blocks:  # проходим по всем таблицам
                # достаем дату и время
                date_time = block.find("div", class_="g-date").get_text(strip=True)
                date_match, time_match = date_time.split()
                if date_match != date.today().strftime('%d/%m'):
                    continue  # если дата не соответствует текущей, то пропускаем

                teams = [team.get_text(strip=True) for team in block.find_all("p")]
                coefficients = [
                    float(coef.get_text(strip=True).replace(",", ".")) if coef.get_text(strip=True) != "" else 0
                    for coef in block.find_all("td", class_="cf")
                    if len(coef["class"]) == 1  # проверяем, что класс только один - "cf"
                    ]


                # достаем ссылку на страницу
                link = block.find("a", class_="g-d g-d-s line")["href"]

                driver.get("https://zenit.win" + link)
                wait = WebDriverWait(driver, 100)
                element_link = wait.until(
                    EC.presence_of_element_located((By.ID, "table_1031"))
                )
                html_code = element_link.get_attribute("outerHTML")
                soup_link = BeautifulSoup(html_code, "html.parser")
                link_res = [
                    float(i.text.replace(',', '.')) if i.text != "" else 0
                    for i in soup_link.find_all("td", style="width: 15%;")
                ]

                match_data = (list(sport_country) + [liga, time_match] + teams + coefficients + [final_coefficient] + link_res[:10])
                result.append(match_data)

        return result
    finally:
        driver.quit()
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
            executor.submit(parse_page, url, sport_country): url
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
        today = date.today().strftime('%Y%m%d')
        cursor.execute(f'''CREATE TABLE IF NOT EXISTS "{today}" (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            sport TEXT,
                            country TEXT,
                            liga TEXT,
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
                            B NUMERIC(6,3) DEFAULT NULL,
                            extra INTEGER DEFAULT NULL,
                            both_teams_Y NUMERIC(6,3) DEFAULT NULL,
                            both_teams_N NUMERIC(6,3) DEFAULT NULL,
                            both_teams_1_Y NUMERIC(6,3) DEFAULT NULL,
                            both_teams_1_N NUMERIC(6,3) DEFAULT NULL,
                            both_teams_2_Y NUMERIC(6,3) DEFAULT NULL,
                            both_teams_2_N NUMERIC(6,3) DEFAULT NULL,
                            both_teams_12_Y NUMERIC(6,3) DEFAULT NULL,
                            both_teams_12_N NUMERIC(6,3) DEFAULT NULL,
                            first_half_gool_Y NUMERIC(6,3) DEFAULT NULL,
                            first_half_gool_N NUMERIC(6,3) DEFAULT NULL)''')


        cursor.executemany(f'''INSERT INTO "{today}"
        (sport, country, liga, time_start, team1, team2, W1, X, W2, H1, HV1, H2, HV2, M, total, B, extra, both_teams_Y, both_teams_N, both_teams_1_Y, both_teams_1_N, both_teams_2_Y, both_teams_2_N, both_teams_12_Y, both_teams_12_N, first_half_gool_Y, first_half_gool_N)
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', data)
        db.commit()  # записываем данные в базу


if __name__ == '__main__':
    db_record(parser_football())    
