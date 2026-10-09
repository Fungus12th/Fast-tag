import sys
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

options = Options()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')

try:
    driver = webdriver.Chrome(options=options)
    driver.get("http://localhost:5000")
    logs = driver.get_log('browser')
    for log in logs:
        print(log)
    driver.quit()
except Exception as e:
    print(f"Selenium failed: {e}")
