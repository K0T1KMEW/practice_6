import aiohttp
from bs4 import BeautifulSoup
import re
import asyncio
from logger_config import setup_logger

logger = setup_logger(__name__)

class XComParser:
    def __init__(self):
        self.session = None
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0',
            'Referer': 'https://www.xcom-shop.ru/',
        }

    async def init_session(self):
        if not self.session:
            self.session = aiohttp.ClientSession(headers=self.headers)
            logger.info("Сессия aiohttp инициализирована")

    async def get_product_full_info(self, link: str) -> dict:
        result = {
            'name': None,
            'description': None,
            'rating': None,
            'price': None,
            'reviews_count': None
        }
        
        await self.init_session()
        
        for attempt in range(3):
            try:
                logger.info(f"Попытка {attempt + 1} получения информации: {link}")
                
                async with self.session.get(link, timeout=20) as response:
                    response.raise_for_status()
                    html = await response.text()
                
                soup = BeautifulSoup(html, 'html.parser')
                
                try:
                    title_element = soup.find('h1', {'id': 'card_main_title'})
                    if title_element:
                        title = title_element.get_text(strip=True)
                        title = re.sub(r'<!--.*?-->', '', title)
                        title = re.sub(r'\s+', ' ', title).strip()
                        result['name'] = title
                        logger.info(f"Название получено: {result['name']}")
                except Exception as e:
                    logger.error(f"Ошибка получения названия: {e}")
            
                try:
                    price_element = soup.find('div', class_='card-content-total-price__current')
                    if price_element:
                        price_text = price_element.get_text(strip=True)
                        price_clean = re.sub(r'[^\d]', '', price_text)
                        if price_clean:
                            result['price'] = float(price_clean)
                            logger.info(f"Цена получена: {result['price']}")
                except Exception as e:
                    logger.error(f"Ошибка парсинга цены: {e}")
                
                try:
                    rating_element = soup.find('span', class_='card-head-reviews-rating__value')
                    if rating_element:
                        rating_text = rating_element.get_text(strip=True)
                        if rating_text:
                            result['rating'] = float(rating_text)
                            logger.info(f"Рейтинг получен: {result['rating']}")
                except Exception as e:
                    logger.error(f"Ошибка получения рейтинга: {e}")
                
                try:
                    reviews_element = soup.find('div', class_='card-head-reviews-info__value')
                    if reviews_element:
                        reviews_text = reviews_element.get_text(strip=True)
                        reviews_count = re.search(r'\d+', reviews_text)
                        if reviews_count:
                            result['reviews_count'] = int(reviews_count.group())
                            logger.info(f"Количество отзывов: {result['reviews_count']}")
                except Exception as e:
                    logger.error(f"Ошибка получения отзывов: {e}")
                
                logger.info(f"Финальный результат парсинга: {result}")
                
                if any(result.values()):
                    return result
                else:
                    logger.warning(f"Не удалось получить данные на попытке {attempt + 1}")
                    
            except Exception as e:
                logger.warning(f"Попытка {attempt + 1} не удалась: {e}")
                if attempt < 2:
                    await asyncio.sleep(3)
                    continue
        
        logger.warning(f"Не удалось получить данные после 3 попыток, возвращаем пустой результат")
        return result

    async def parse_price(self, link: str) -> float:
        try:
            info = await self.get_product_full_info(link)
            return info.get('price')
        except Exception as e:
            logger.error(f"Ошибка получения цены товара: {e}")
            return None

    async def close(self):
        if self.session:
            await self.session.close()
            logger.info("Сессия aiohttp закрыта")