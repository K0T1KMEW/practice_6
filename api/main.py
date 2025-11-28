from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from typing import List
from contextlib import asynccontextmanager

from schemas import ProductCreate, ProductResponse, PriceHistoryResponse
from pricemanager import PriceManager
from config import DefaultResponse
from logger_config import setup_logger
from database import db_manager
from parser import XComParser as PriceParser

logger = setup_logger(__name__)

price_parser = None
price_manager = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    await db_manager.initialize_database()
    
    global price_parser, price_manager
    price_parser = PriceParser()
    price_manager = PriceManager(parser=price_parser)
    
    yield
    
    if price_parser:
        await price_parser.close()
    await db_manager.close()

app = FastAPI(
    title="Price Monitoring API",
    description="API для мониторинга цен товаров",
    lifespan=lifespan
)

templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    products_result = await price_manager.get_all_products()
    products = products_result.payload if not products_result.error else []
    return templates.TemplateResponse("index.html", {"request": request, "products": products})

@app.get("/products/{product_id}/prices-page", response_class=HTMLResponse)
async def price_history_page(request: Request, product_id: int):
    try:
        products_result = await price_manager.get_all_products()
        if products_result.error:
            return DefaultResponse(error=True, message="Товар не найден", payload=None)
        
        product = next((p for p in products_result.payload if p.id == product_id), None)
        if not product:
            return DefaultResponse(error=True, message="Товар не найден", payload=None)
        
        price_history_result = await price_manager.get_price_history(product_id)
        price_history = price_history_result.payload if not price_history_result.error else []
        
        return templates.TemplateResponse(
            "price_history.html", 
            {
                "request": request, 
                "product": product,
                "price_history": price_history
            }
        )
        
    except Exception as e:
        logger.error(f"Ошибка при загрузке страницы истории цен: {str(e)}")
        return DefaultResponse(error=True, message="Внутренняя ошибка сервера", payload=None)

@app.post("/products", response_model=DefaultResponse[ProductResponse])
async def add_product(product_data: ProductCreate) -> DefaultResponse[ProductResponse]:
    try:
        logger.info(f"Добавление товара: {product_data.link}")
        
        result = await price_manager.add_product(
            link=product_data.link,
            name=product_data.name
        )
        
        if result.error:
            logger.warning(f"Ошибка добавления товара: {result.message}")
            return DefaultResponse(error=True, message=result.message, payload=None)
        
        logger.info(f"Товар успешно добавлен: ID {result.payload.id}")
        return result
        
    except Exception as e:
        logger.error(f"Ошибка API при добавлении товара: {str(e)}")
        return DefaultResponse(
            error=True,
            message=f"Внутренняя ошибка сервера: {str(e)}",
            payload=None
        )

@app.delete("/products/{product_id}", response_model=DefaultResponse)
async def delete_product(product_id: int) -> DefaultResponse:
    try:
        logger.info(f"Удаление товара: ID {product_id}")
        
        result = await price_manager.delete_product(product_id)
        
        if result.error:
            logger.warning(f"Ошибка удаления товара: {result.message}")
            return DefaultResponse(error=True, message=result.message, payload=None)
        
        logger.info(f"Товар успешно удален: ID {product_id}")
        return result
        
    except Exception as e:
        logger.error(f"Ошибка API при удалении товара: {str(e)}")
        return DefaultResponse(
            error=True,
            message=f"Внутренняя ошибка сервера: {str(e)}",
            payload=None
        )

@app.get("/products", response_model=DefaultResponse[List[ProductResponse]])
async def get_products() -> DefaultResponse[List[ProductResponse]]:
    try:
        logger.info("Запрос списка товаров")
        
        result = await price_manager.get_all_products()
        
        if result.error:
            logger.warning(f"Ошибка получения списка товаров: {result.message}")
            return DefaultResponse(
                error=True,
                message=result.message,
                payload=None
            )
        
        logger.info(f"Успешно возвращено {len(result.payload)} товаров")
        return result
        
    except Exception as e:
        logger.error(f"Ошибка API при получении списка товаров: {str(e)}")
        return DefaultResponse(
            error=True,
            message=f"Внутренняя ошибка сервера: {str(e)}",
            payload=None
        )

@app.get("/products/{product_id}/prices", response_model=DefaultResponse[List[PriceHistoryResponse]])
async def get_price_history(product_id: int) -> DefaultResponse[List[PriceHistoryResponse]]:
    try:
        logger.info(f"Запрос истории цен для товара: ID {product_id}")
        
        result = await price_manager.get_price_history(product_id)
        
        if result.error:
            logger.warning(f"Ошибка получения истории цен: {result.message}")
            return DefaultResponse(
                error=True,
                message=result.message,
                payload=None
            )
        
        logger.info(f"Успешно возвращено {len(result.payload)} записей цен")
        return result
        
    except Exception as e:
        logger.error(f"Ошибка API при получении истории цен: {str(e)}")
        return DefaultResponse(
            error=True,
            message=f"Внутренняя ошибка сервера: {str(e)}",
            payload=None
        )

# @app.get("/health", response_model=DefaultResponse)
# async def health_check() -> DefaultResponse:
#     return DefaultResponse(
#         error=False,
#         message="Service is healthy",
#         payload={"status": "healthy", "service": "price_monitoring_api"}
#     )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)