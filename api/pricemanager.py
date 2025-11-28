from sqlalchemy import select
from typing import List, Optional
from models import Product, PriceHistory
from database import db_manager
from schemas import ProductResponse, PriceHistoryResponse
from config import DefaultResponse
from logger_config import setup_logger

logger = setup_logger(__name__)

class PriceManager:
    def __init__(self, parser=None):
        self.parser = parser

    async def add_product(self, link: str, name: str = None) -> DefaultResponse:
        try:
            async with db_manager.get_session() as session:
                existing_product = await session.execute(
                    select(Product).where(Product.link == link)
                )
                if existing_product.scalar_one_or_none():
                    logger.warning(f"Попытка добавить товар с уже существующей ссылкой: {link}")
                    return DefaultResponse(
                        error=True,
                        message="Товар с такой ссылкой уже существует",
                        payload=None
                    )
                
                product_info = {}
                if self.parser:
                    try:
                        full_info = await self.parser.get_product_full_info(link)
                        product_info = {
                            'name': full_info.get('name'),
                            'description': full_info.get('description'),
                            'rating': full_info.get('rating')
                        }
                        logger.info(f"Получена информация о товаре: {product_info}")
                    except Exception as e:
                        logger.warning(f"Ошибка при получении информации о товаре: {str(e)}")
                        product_info = {}
                
                product = Product(
                    link=link,
                    name=name or product_info.get('name'),
                    description=product_info.get('description'), 
                    rating=product_info.get('rating')
                )
                
                session.add(product)
                await session.commit()
                await session.refresh(product)
                
                logger.info(f"СОХРАНЕНО В БД: ID={product.id}, name='{product.name}', desc='{product.description}', rating={product.rating}")
                
                product_response = ProductResponse.model_validate(product)
                
                return DefaultResponse(
                    error=False,
                    message="Товар успешно добавлен",
                    payload=product_response
                )
                    
        except Exception as e:
            logger.error(f"Ошибка при добавлении товара: {str(e)}")
            return DefaultResponse(
                error=True,
                message=f"Ошибка при добавлении товара: {str(e)}",
                payload=None
            )

    async def delete_product(self, product_id: int) -> DefaultResponse:
        try:
            async with db_manager.get_session() as session:
                product = await session.get(Product, product_id)
                if product:
                    result = await session.execute(
                        select(PriceHistory).where(PriceHistory.product_id == product_id)
                    )
                    price_history_records = result.scalars().all()
                    
                    for record in price_history_records:
                        await session.delete(record)
                    
                    await session.delete(product)
                    await session.commit()
                    
                    logger.info(f"Товар успешно удален: ID {product_id}")
                    return DefaultResponse(
                        error=False,
                        message="Товар успешно удален",
                        payload={"product_id": product_id}
                    )
                
                logger.warning(f"Попытка удалить несуществующий товар: ID {product_id}")
                return DefaultResponse(
                    error=True,
                    message="Товар не найден",
                    payload=None
                )
                    
        except Exception as e:
            logger.error(f"Ошибка при удалении товара: {str(e)}")
            return DefaultResponse(
                error=True,
                message=f"Ошибка при удалении товара: {str(e)}",
                payload=None
            )

    async def get_all_products(self) -> DefaultResponse:
        try:
            async with db_manager.get_session() as session:
                result = await session.execute(select(Product))
                products = result.scalars().all()
                
                products_response = [ProductResponse.model_validate(product) for product in products]
                
                logger.info(f"Получено {len(products)} товаров")
                return DefaultResponse(
                    error=False,
                    message="Список товаров успешно получен",
                    payload=products_response
                )
                    
        except Exception as e:
            logger.error(f"Ошибка при получении списка товаров: {str(e)}")
            return DefaultResponse(
                error=True,
                message=f"Ошибка при получении списка товаров: {str(e)}",
                payload=None
            )

    async def add_price_history(self, product_id: int, price: float) -> DefaultResponse:
        try:
            async with db_manager.get_session() as session:
                product = await session.get(Product, product_id)
                if not product:
                    logger.warning(f"Попытка добавить цену для несуществующего товара: ID {product_id}")
                    return DefaultResponse(
                        error=True,
                        message="Товар не найден",
                        payload=None
                    )
                
                price_history = PriceHistory(product_id=product_id, price=price)
                session.add(price_history)
                await session.commit()
                await session.refresh(price_history)
                
                price_history_response = PriceHistoryResponse.model_validate(price_history)
                
                logger.info(f"Цена {price} успешно добавлена для товара ID {product_id}")
                return DefaultResponse(
                    error=False,
                    message="Цена успешно добавлена",
                    payload=price_history_response
                )
                    
        except Exception as e:
            logger.error(f"Ошибка при добавлении истории цены: {str(e)}")
            return DefaultResponse(
                error=True,
                message=f"Ошибка при добавлении истории цены: {str(e)}",
                payload=None
            )

    async def get_current_price(self, product_id: int) -> Optional[float]:
        try:
            async with db_manager.get_session() as session:
                result = await session.execute(
                    select(PriceHistory)
                    .where(PriceHistory.product_id == product_id)
                    .order_by(PriceHistory.created_at.desc())
                    .limit(1)
                )
                latest_price = result.scalar_one_or_none()
                
                return latest_price.price if latest_price else None
                
        except Exception as e:
            logger.error(f"Ошибка при получении текущей цены: {str(e)}")
            return None

    async def get_price_history(self, product_id: int) -> DefaultResponse:
        try:
            async with db_manager.get_session() as session:
                product = await session.get(Product, product_id)
                if not product:
                    logger.warning(f"Попытка получить историю цен для несуществующего товара: ID {product_id}")
                    return DefaultResponse(
                        error=True,
                        message="Товар не найден",
                        payload=None
                    )
                
                result = await session.execute(
                    select(PriceHistory)
                    .where(PriceHistory.product_id == product_id)
                    .order_by(PriceHistory.created_at.desc())
                )
                price_history = result.scalars().all()
                
                price_history_response = [PriceHistoryResponse.model_validate(ph) for ph in price_history]
                
                logger.info(f"Получено {len(price_history)} записей истории цен для товара ID {product_id}")
                return DefaultResponse(
                    error=False,
                    message="История цен успешно получена",
                    payload=price_history_response
                )
                    
        except Exception as e:
            logger.error(f"Ошибка при получении истории цен: {str(e)}")
            return DefaultResponse(
                error=True,
                message=f"Ошибка при получении истории цен: {str(e)}",
                payload=None
            )