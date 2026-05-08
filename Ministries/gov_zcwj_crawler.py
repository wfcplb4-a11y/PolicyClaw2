import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
import re
import time

SELENIUM_AVAILABLE = False
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from webdriver_manager.chrome import ChromeDriverManager
    from selenium.webdriver.chrome.service import Service
    SELENIUM_AVAILABLE = True
except ImportError:
    print("Selenium not installed, will try alternative method")

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Referer': 'https://sousuo.www.gov.cn/zcwjk/policyDocumentLibrary',
    'Origin': 'https://sousuo.www.gov.cn'
}

TARGET_URL = "https://sousuo.www.gov.cn/zcwjk/policyDocumentLibrary?q=&t=zhengcelibrary&orpro="

API_URL = "https://sousuo.www.gov.cn/search-gov/data"
API_COOKIES = "_qimei_uuid42=19b0c0b313910000a4cf89a20e72d2bc27b92965c2; _qimei_i_3=7be76886c45e58d8c7c4af61528177e3f3efa4a7100d558ae7dc7e5e2f90226b356663943c89e2bd8084; _qimei_h38=aea3debfa4cf89a20e72d2bc02000000819b0c; wdcid=0c788098375b7e28; __auc=053a196d19bd558a9d02fc6b252; _qimei_i_1=7fcd64d3c00b538f94c5a8615fd725e8febfa6f1475c01d6b6dd7b582493206c6163379d3980b0dc85b7f3e4; _qimei_fingerprint=933d898aca3f979f69c8525dc88033dd; arialoadData=false; ariauseGraymode=false"

CATEGORY_MAP = {
    'gongwen': '国务院文件',
    'bumenfile': '国务院部门文件',
    'otherfile': '其他文件',
    'gongbao': '国务院公报'
}

def get_api_session():
    session = requests.Session()
    
    main_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    }
    
    session.get(TARGET_URL, headers=main_headers, timeout=30)
    
    for cookie in API_COOKIES.split('; '):
        if '=' in cookie:
            name, value = cookie.split('=', 1)
            session.cookies.set(name.strip(), value.strip())
    
    return session


def scrape_with_selenium():
    options = Options()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-extensions')
    options.add_argument('--disable-logging')
    options.add_argument('--disable-software-rasterizer')
    options.add_argument('--disable-gpu-sandbox')
    options.add_argument('--ignore-certificate-errors')
    options.add_argument('--disable-setuid-sandbox')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--disable-web-security')
    options.add_argument('--allow-running-insecure-content')
    
    max_retries = 2
    for attempt in range(max_retries):
        try:
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)
            
            driver.set_page_load_timeout(45)
            driver.set_script_timeout(45)
            driver.get(TARGET_URL)
            
            time.sleep(8)
            
            last_height = driver.execute_script("return document.body.scrollHeight")
            scroll_count = 0
            max_scrolls = 15
            
            while scroll_count < max_scrolls:
                for _ in range(3):
                    driver.execute_script("window.scrollBy(0, 500);")
                    time.sleep(0.3)
                
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(1)
                
                try:
                    new_height = driver.execute_script("return document.body.scrollHeight")
                except:
                    new_height = last_height
                
                if new_height == last_height:
                    scroll_count += 1
                else:
                    scroll_count = 0
                    last_height = new_height
                
                if scroll_count >= 3:
                    break
            
            time.sleep(2)
            
            page_source = driver.page_source
            driver.quit()
            
            return page_source
        except Exception as e:
            print(f"Selenium attempt {attempt + 1} failed: {e}")
            try:
                driver.quit()
            except:
                pass
            
            if attempt < max_retries - 1:
                time.sleep(3)
    
    return None


def scrape_with_api():
    try:
        session = get_api_session()
        params = {
            't': 'zhengcelibrary',
            'q': '',
            'p': '1',
            'n': '200',
            'type': 'gwyzcwjk'
        }
        response = session.get(API_URL, headers=headers, params=params, timeout=30)
        data = response.json()
        searchVO = data.get('searchVO', {})
        catMap = searchVO.get('catMap', {})
        
        all_items = []
        
        for catKey, catData in catMap.items():
            catName = CATEGORY_MAP.get(catKey, catKey)
            listVO = catData.get('listVO', [])
            
            for item in listVO:
                title_raw = item.get('title', '')
                title = re.sub(r'</?em>', '', title_raw)
                title = re.sub(r'<br\s*/?>', ' ', title)
                
                date_str = item.get('pubtimeStr', '')
                pub_at = None
                if date_str:
                    try:
                        pub_at = datetime.strptime(date_str, '%Y.%m.%d').date()
                    except ValueError:
                        pass
                
                pcode = item.get('pcode', '')
                url = item.get('sourcelink', item.get('url', ''))
                
                if not url:
                    continue
                
                all_items.append({
                    'title': title,
                    'url': url,
                    'pub_at': pub_at,
                    'category': catName,
                    'pcode': pcode
                })
        
        return all_items
    except Exception as e:
        print(f"API fetch error: {e}")
        import traceback
        traceback.print_exc()
        return []


def scrape_data():
    policies = []
    all_items = []
    
    try:
        tz_utc8 = timezone(timedelta(hours=8))
        today = datetime.now(tz_utc8).date()
        yesterday = today - timedelta(days=1)
        
        print(f"Running date (Beijing): {today}")
        print(f"Target date: {yesterday}")
        
        print("Using API to fetch data...")
        all_items = scrape_with_api()
        
        print(f"Found {len(all_items)} items from API")
        
        filtered_count = 0
        
        for item in all_items:
            try:
                title = item.get('title', '')
                href = item.get('url', '')
                pub_at = item.get('pub_at')
                category = item.get('category', '')
                
                if not title or not href:
                    continue
                
                if not href.startswith('http'):
                    href = f"https://sousuo.www.gov.cn{href}"
                
                if pub_at != yesterday:
                    filtered_count += 1
                    continue
                
                content = ""
                try:
                    detail_resp = requests.get(href, headers=headers, timeout=15)
                    detail_resp.raise_for_status()
                    detail_soup = BeautifulSoup(detail_resp.content, 'html.parser')
                    
                    content_table = detail_soup.find('table', class_='border-table noneBorder pages_content')
                    if content_table:
                        content = content_table.get_text(separator='\n', strip=True)
                    else:
                        content_elem = detail_soup.select_one('#UCAP-CONTENT') or detail_soup.select_one('.article-content')
                        if content_elem:
                            content = content_elem.get_text(separator='\n', strip=True)
                        else:
                            max_text = ""
                            for tag in detail_soup.find_all(['div', 'td', 'p']):
                                text = tag.get_text(strip=True)
                                if len(text) > len(max_text):
                                    max_text = text
                            content = max_text
                except Exception as e:
                    print(f"Detail page fetch failed: {href} - {e}")
                
                policy_data = {
                    'title': title,
                    'url': href,
                    'pub_at': pub_at,
                    'content': content,
                    'selected': False,
                    'category': category,
                    'source': '国务院文件'
                }
                
                policies.append(policy_data)
                
            except Exception as e:
                print(f"Single item processing failed - {e}")
                continue
        
        print(f"\nState Council Document Crawler: Successfully crawled {len(policies)} items from yesterday")
        print(f"Filtered out {filtered_count} non-target-date items")
        
        if all_items:
            print(f"\nAll items found on page (total: {len(all_items)}):")
            sorted_items = sorted(all_items, key=lambda x: x['pub_at'] or datetime.min.date(), reverse=True)
            for i, item in enumerate(sorted_items, 1):
                date_str = item['pub_at'].strftime('%Y-%m-%d') if item['pub_at'] else 'Unknown date'
                title_clean = re.sub(r'\s+', ' ', item['title'])
                print(f"{i}. {title_clean[:70]} [{date_str}]")
        
    except Exception as e:
        print(f"State Council Document Crawler: Failed - {e}")
        import traceback
        traceback.print_exc()
    
    return policies, all_items


def save_to_supabase(data_list):
    try:
        from db_utils import save_to_policy
        return save_to_policy(data_list, "国务院文件")
    except Exception as e:
        print(f"Error saving to database: {e}")
        return data_list, None


def run():
    try:
        print("Starting Crawler: State Council Documents")
        print("----------------------------------------")
        data, _ = scrape_data()
        if data:
            result, api_push_result = save_to_supabase(data)
            print(f"Crawled: {len(data)} items")
            print(f"Written to database: {len(result)} items")
            print("State Council Document Crawler: Success")
            return result, api_push_result
        else:
            print("No target date articles found")
            print("State Council Document Crawler: Completed")
            return [], None
    except Exception as e:
        print(f"State Council Document Crawler: Failed - {e}")
        return [], None


if __name__ == "__main__":
    run()
