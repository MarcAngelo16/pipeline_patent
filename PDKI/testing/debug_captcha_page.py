#!/usr/bin/env python3
import os, time
import undetected_chromedriver as uc

os.environ['DISPLAY'] = ':99'
options = uc.ChromeOptions()
options.add_argument('--user-data-dir=/root/chrome-profile')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument('--window-size=1920,1080')

driver = uc.Chrome(options=options, version_main=145)
driver.get('https://pdki-indonesia.dgip.go.id/link/5049443230313830393536377c706174656e74')
time.sleep(5)

print('URL:  ', driver.current_url)
print('TITLE:', driver.title)
print('SOURCE LENGTH:', len(driver.page_source))
print('=' * 60)
print(driver.page_source)
print('=' * 60)

screenshot_path = os.path.join(os.path.dirname(__file__), 'captcha_page.png')
driver.save_screenshot(screenshot_path)
print('Screenshot saved:', screenshot_path)
driver.quit()
