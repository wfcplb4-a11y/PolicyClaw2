import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
import re
import time

SELENIUM_AVAILABLE = False
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager
    SELENIUM_AVAILABLE = True
except ImportError:
    print("Selenium not installed, will use requests")

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
}

TARGET_URL = "https://www.mof.gov.cn/gkml/bulinggonggao/tongzhitonggao/"


def scrape_with_requests():
    try:
        response = requests.get(TARGET_URL, headers=headers, timeout=30)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"Requests error: {e}")
        return None


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
    
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        
        driver.set_page_load_timeout(45)
        driver.get(TARGET_URL)
        
        time.sleep(10)
        
        page_source = driver.page_source
        driver.quit()
        
        return page_source
    except Exception as e:
        print(f"Selenium error: {e}")
        try:
            driver.quit()
        except:
            pass
        return None


def scrape_data():
    policies = []
    all_items = []
    
    try:
        tz_utc8 = timezone(timedelta(hours=8))
        today = datetime.now(tz_utc8).date()
        yesterday = today - timedelta(days=1)
        
        print(f"运行日期（北京时间）：{today}")
        print(f"目标抓取日期：{yesterday}")
        
        # Try requests first
        print("Using requests...")
        page_source = scrape_with_requests()
        
        # If requests fails, try Selenium
        if not page_source and SELENIUM_AVAILABLE:
            print("Requests failed, using Selenium...")
            page_source = scrape_with_selenium()
        
        if not page_source:
            print("无法获取页面内容")
            return policies, all_items
        
        soup = BeautifulSoup(page_source, 'html.parser')
        
        # Find ul with class="xwbd_lianbolistfrcon"
        ul = soup.find('ul', class_='xwbd_lianbolistfrcon')
        if not ul:
            print("文章列表未找到")
            return policies, all_items
        
        lis = ul.find_all('li')
        print(f"找到 {len(lis)} 条数据")
        
        filtered_count = 0
        
        for li in lis:
            try:
                a = li.find('a')
                if not a:
                    continue
                
                title = a.get_text(strip=True)
                href = a.get('href', '')
                
                if not title or not href:
                    continue
                
                if not href.startswith('http'):
                    href = f"https://www.mof.gov.cn{href}"
                
                # Find date in spans
                date_spans = li.find_all('span')
                date_str = ''
                for span in date_spans:
                    text = span.get_text(strip=True)
                    if re.match(r'\d{4}-\d{2}-\d{2}', text):
                        date_str = text
                        break
                
                pub_at = None
                if date_str:
                    try:
                        pub_at = datetime.strptime(date_str, '%Y-%m-%d').date()
                    except ValueError:
                        pass
                
                all_items.append({'title': title, 'pub_at': pub_at})
                
                if pub_at != yesterday:
                    filtered_count += 1
                    continue
                
                # Fetch detail page content
                content = ""
                try:
                    detail_resp = requests.get(href, headers=headers, timeout=15)
                    if detail_resp.status_code == 200:
                        detail_soup = BeautifulSoup(detail_resp.content, 'html.parser')
                        
                        # Try the specific XPath: //div[@class="mainboxerji"]
                        content_div = detail_soup.find('div', class_='mainboxerji')
                        if content_div:
                            content = content_div.get_text(separator='\n', strip=True)
                        else:
                            # Fallback
                            content_div = detail_soup.find('div', class_='TRS_Editor') or detail_soup.find('div', class_='content')
                            if content_div:
                                content = content_div.get_text(separator='\n', strip=True)
                            else:
                                max_text = ""
                                for tag in detail_soup.find_all(['div', 'td', 'p']):
                                    text = tag.get_text(strip=True)
                                    if len(text) > len(max_text):
                                        max_text = text
                                content = max_text
                except Exception as e:
                    print(f"抓取详情页失败：{e}")
                
                policy_data = {
                    'title': title,
                    'url': href,
                    'pub_at': pub_at,
                    'content': content,
                    'selected': False,
                    'category': '',
                    'source': '财政部通知'
                }
                
                policies.append(policy_data)
                
            except Exception as e:
                print(f"单条数据处理失败 - {e}")
                continue
        
        print(f"\n✅ 财政部通知爬虫：成功抓取 {len(policies)} 条前一天数据")
        print(f"⏭️  过滤掉 {filtered_count} 条非目标日期的数据")
        
        if all_items:
            print(f"\n📊 页面最新5条是：")
            sorted_items = sorted(all_items, key=lambda x: x['pub_at'] or datetime.min.date(), reverse=True)
            for i, item in enumerate(sorted_items[:5], 1):
                date_str = item['pub_at'].strftime('%Y-%m-%d') if item['pub_at'] else '未知日期'
                title = item['title'][:50]
                print(f"✅ {title}... {date_str}")
        
    except Exception as e:
        print(f"❌ 财政部通知爬虫：抓取失败 - {e}")
        print("----------------------------------------")
    
    return policies, all_items


def save_to_supabase(data_list):
    try:
        from db_utils import save_to_policy
        return save_to_policy(data_list, "财政部通知")
    except Exception as e:
        print(f"Error saving to database: {e}")
        return data_list, None


def run():
    try:
        data, _ = scrape_data()
        if data:
            result, api_push_result = save_to_supabase(data)
            print(f"\n💾 写入数据库: {len(result)} 条")
            print("----------------------------------------")
            print("✅ 爬虫 财政部通知 执行成功")
            return result, api_push_result
        else:
            print(f"\n💾 写入数据库: 0 条")
            print("----------------------------------------")
            print("⚠️  未找到目标日期的文章")
            return [], None
    except Exception as e:
        print(f"❌ 爬虫 财政部通知 运行失败 - {e}")
        print("----------------------------------------")
        return [], None


if __name__ == "__main__":
    run()
