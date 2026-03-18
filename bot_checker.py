import asyncio
import re
import os
import sys
from playwright.async_api import async_playwright

os.makedirs('/tmp', exist_ok=True)

sys.stdout.reconfigure(line_buffering=True)

class EmmaBot:
    def __init__(self):
        print("Инициализация бота...", flush=True)
        self.app_url = os.getenv('APP_URL')
        self.username = os.getenv('BOT_USERNAME')
        self.password = os.getenv('BOT_PASSWORD')
        self.browser = None
        self.context = None
        self.state_file = "/tmp/bot_state.json"
        
    async def init(self):
        print("Запуск Playwright...", flush=True)
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-dev-shm-usage']
        )
        self.context = await self.browser.new_context()
        print("Playwright готов", flush=True)

    async def wait_for_app(self):
        for i in range(10):
            try:
                page = await self.context.new_page()
                await page.goto(f"{self.app_url}/login", timeout=2000)
                print("Приложение готово")
                await page.close()
                return True
            except:
                print(f"Ожидание запуска приложения ({i+1}/10)...")
                await asyncio.sleep(2)
        return False
        
    async def login(self):
        if not await self.wait_for_app():
            print("Приложение не запустилось")
            return False
        page = await self.context.new_page()
        print(f"Попытка входа: {self.username}", flush=True)
        
        try:
            await page.goto(f"{self.app_url}/login", timeout=10000)
            await page.wait_for_selector('input[name="username"]', timeout=5000)
            await page.wait_for_selector('input[name="password"]', timeout=5000)
            
            await page.fill('input[name="username"]', self.username)
            await page.fill('input[name="password"]', self.password)
            
            async with page.expect_navigation():
                await page.click('button[type="submit"]')
            
            await page.wait_for_timeout(1000)
            current_url = page.url
            print(f"URL после логина: {current_url}", flush=True)
            
            if 'login' not in current_url:
                await self.context.storage_state(path=self.state_file)
                
                cookies = await self.context.cookies()
                print(f"Сохранено кук: {len(cookies)}", flush=True)
                for cookie in cookies:
                    print(f"    {cookie.get('name')}: {cookie.get('value')[:20]}...", flush=True)
                
                print("Успешный вход!", flush=True)
                await page.close()
                return True
            else:
                print(f"Ошибка: остались на странице логина", flush=True)
                await page.close()
                return False
                
        except Exception as e:
            print(f"Ошибка при входе: {e}", flush=True)
            await page.close()
            return False
    
    async def read_messages(self):
        messages = []
        try:
            with open('/tmp/messages.txt', 'r') as f:
                lines = f.readlines()
            
            open('/tmp/messages.txt', 'w').close()
            
            for line in lines:
                line = line.strip()
                if ': ' in line:
                    username, text = line.split(': ', 1)
                    messages.append({'username': username, 'text': text})
                    print(f"Прочитано сообщение от {username}: {text[:50]}...", flush=True)
        except FileNotFoundError:
            pass
        except Exception as e:
            print(f"Ошибка чтения сообщений: {e}", flush=True)
        
        return messages
    
    async def visit_url(self, url):
        context = await self.browser.new_context(storage_state=self.state_file)
        page = await context.new_page()
        try:
            print(f"Перехожу по ссылке: {url[:100]}...", flush=True)

            cookies = await context.cookies()
            print(f"Куки перед переходом: {len(cookies)} шт.", flush=True)
            
            await page.goto(url, timeout=10000, wait_until='networkidle')

            final_url = page.url
            print(f"Финальный URL: {final_url}", flush=True)
        
            await page.wait_for_timeout(3000)
        except Exception as e:
            print(f"Ошибка при открытии {url[:50]}: {e}", flush=True)
        finally:
            await page.close()
            await context.close()
    
    async def process_messages(self):
        while True:
            try:
                messages = await self.read_messages()
                
                for msg in messages:
                    print(f"Обрабатываю сообщение от {msg['username']}", flush=True)
                    urls = re.findall(r'https?://[^\s]+', msg['text'])
                    
                    for url in urls:
                        await self.visit_url(url)
                        
                await asyncio.sleep(5)
                
            except Exception as e:
                print(f"Ошибка в цикле: {e}", flush=True)
                await asyncio.sleep(5)
    
    async def run(self):
        print("Запуск бота...", flush=True)
        await self.init()
        if await self.login():
            await self.process_messages()
        else:
            print("Не удалось залогиниться", flush=True)

if __name__ == "__main__":
    print("Старт скрипта", flush=True)
    asyncio.run(EmmaBot().run())
