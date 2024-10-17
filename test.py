from json import load

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait 


def parser_matches(soup, sport_country, driver):

    match_blocks = soup.find_all("tr", class_="g-tr")

    # liga = soup.find('a', class_='l-th-name').split()[2]

    result = []
    for block in match_blocks:
        date_time = block.find("div", class_="g-date").get_text(strip=True)
        date, time = date_time.split()
        teams = [team.get_text(strip=True) for team in block.find_all("p")]
        coefficients = [
            float(coef.get_text(strip=True).replace(",", "."))
            for coef in block.find_all("td", class_="cf")
            if coef.get_text(strip=True).replace(",", ".").replace(".", "", 1).isdigit()
        ]
        final_coefficient = block.find("span", class_="g-t-a").get_text(strip=True)
        print(sport_country)

        link = block.find("a", class_="g-d g-d-s line")['href']
        driver.get('https://zenit.win' + link)
        wait = WebDriverWait(driver, 100)
        element_link = wait.until(EC.presence_of_element_located((By.ID, "table_1031")))
        html_code = element_link.get_attribute("outerHTML")
        soup_link = BeautifulSoup(html_code, "html.parser")
        link_res = [i.text if i.text != '' else '0' for i in soup_link.find_all('td', style='width: 15%;')]

        match_data = [date, time] + teams + coefficients + [final_coefficient] + link_res[:10]
        result.append(match_data)
        print(result)
        

    return result




def parser_football():

    with open("urls/zenit_urls.json", "r", encoding="utf-8") as f:
        data = load(f)

    urls = {
        (sport, country): url
        for sport, countries in data.items()
        for country, url in countries.items()
    }

    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)"
    options = Options()
    options.add_argument(f"user-agent={user_agent}")
    driver = webdriver.Firefox(options=options)

    results = []

    for sport_country, url in urls.items():
        driver.get(url)
        wait = WebDriverWait(driver, 100)
        element = wait.until(EC.presence_of_element_located((By.ID, "divmain")))
        html_code = element.get_attribute("outerHTML")
        soup = BeautifulSoup(html_code, "html.parser")
        
        results += parser_matches(soup, sport_country, driver)

        with open("res.txt", "w+", encoding="utf-8") as f:
            print(*results, file=f, sep="\n")
        break

parser_football()
