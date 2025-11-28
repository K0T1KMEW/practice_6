import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from parser import XComParser as PriceParser
from database import db_manager
from pricemanager import PriceManager
from logger_config import setup_logger

logger = setup_logger(__name__)

class MonitoringService:
    def __init__(self):
        self.parser = None
        self.price_manager = None
        self.scheduler = AsyncIOScheduler()
    
    async def initialize(self):
        success = await db_manager.initialize_database()
        if not success:
            logger.error("Не удалось инициализировать базу данных")
            return False
        
        self.parser = PriceParser()
        self.price_manager = PriceManager(parser=self.parser)
        
        await self.parser.init_session()
        
        logger.info("Сервис мониторинга инициализирован")
        return True
    
    async def process_product(self, product):
        try:
            logger.info(f"Начинаем парсинг товара: {product.name}")
            logger.info(f"Ссылка: {product.link}")
            
            price = await self.parser.parse_price(product.link)
            
            logger.info(f"Результат парсинга: {price}")
            
            if price is not None:
                result = await self.price_manager.add_price_history(product.id, price)
                if result.error:
                    logger.error(f"Ошибка сохранения цены для товара {product.name}: {result.message}")
                else:
                    logger.info(f"Цена {price}₽ сохранена для товара {product.name}")
            else:
                logger.warning(f"Не удалось получить цену для товара {product.name}")
                
        except Exception as e:
            logger.error(f"Ошибка обработки товара {product.name}: {str(e)}")
            logger.exception(e)
    
    async def monitor_prices(self):
        try:
            logger.info("Запуск задачи мониторинга цен")
            
            products_response = await self.price_manager.get_all_products()
            
            if products_response.error:
                logger.error("Ошибка получения списка товаров")
                return
            
            products = products_response.payload
            logger.info(f"Найдено {len(products)} товаров для мониторинга")
            
            for product in products:
                await self.process_product(product)
                
            logger.info("Задача мониторинга цен завершена")
            
        except Exception as e:
            logger.error(f"Критическая ошибка в задаче мониторинга: {str(e)}")
    
    def start(self):
        asyncio.create_task(self.monitor_prices())
    
        self.scheduler.add_job(
            self.monitor_prices,
            'interval',
            minutes=60,
            id='price_monitoring'
        )
        self.scheduler.start()
        logger.info("Сервис мониторинга цен запущен (интервал: 60 минут)")
    
    async def stop(self):
        self.scheduler.shutdown()
        if self.parser:
            await self.parser.close()
        logger.info("Сервис мониторинга цен остановлен")

async def main():
    service = MonitoringService()
    
    if not await service.initialize():
        return
    
    service.start()
    
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        await service.stop()

if __name__ == "__main__":
    asyncio.run(main())