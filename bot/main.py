import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database import db_manager
from pricemanager import PriceManager
from parser import XComParser as PriceParser
from logger_config import setup_logger
from config import settings

logger = setup_logger(__name__)

class ProductStates(StatesGroup):
    waiting_for_link = State()
    waiting_for_product_id = State()
    waiting_for_delete_confirmation = State()

class PriceMonitorBot:
    def __init__(self, token: str):
        self.bot = Bot(token=token)
        self.dp = Dispatcher()
        self.parser = PriceParser()
        self.price_manager = PriceManager(parser=self.parser)
        
        self.register_handlers()
    
    def register_handlers(self):
        self.dp.message(Command("start"))(self.cmd_start)
        self.dp.message(Command("help"))(self.cmd_help)
        self.dp.message(Command("list"))(self.cmd_list_products)
        self.dp.message(Command("add"))(self.cmd_add_product)
        self.dp.message(Command("delete"))(self.cmd_delete_product)
        self.dp.message(Command("history"))(self.cmd_price_history)
        self.dp.message(Command("health"))(self.cmd_health)
        
        self.dp.message(ProductStates.waiting_for_link)(self.process_product_link)
        self.dp.message(ProductStates.waiting_for_product_id)(self.process_product_id)
        
        self.dp.callback_query(F.data.startswith("delete_"))(self.process_delete_confirmation)
        self.dp.callback_query(F.data.startswith("confirm_delete_"))(self.process_delete)
        self.dp.callback_query(F.data.startswith("cancel_delete"))(self.cancel_delete)
        self.dp.callback_query(F.data.startswith("history_"))(self.show_price_history)
    
    async def cmd_start(self, message: Message):
        welcome_text = """
<b>Бот мониторинга цен</b>

Доступные команды:
/list - Показать все товары
/add - Добавить новый товар
/delete - Удалить товар
/history - История цен товара
/help - Справка

Для начала работы добавьте товар командой /add
        """
        await message.answer(welcome_text, parse_mode="HTML")
    
    async def cmd_help(self, message: Message):
        help_text = """
<b>Справка по командам</b>

/list - Показать список всех отслеживаемых товаров
/add - Добавить новый товар для отслеживания
/delete - Удалить товар из отслеживания
/history - Показать историю цен для конкретного товара

<b>Как добавить товар:</b>
1. Нажмите /add
2. Отправьте ссылку на товар с сайта xcom-shop.ru

<b>Мониторинг:</b>
Цены автоматически обновляются каждые 60 минут
        """
        await message.answer(help_text, parse_mode="HTML")
    
    async def cmd_list_products(self, message: Message):
        try:
            result = await self.price_manager.get_all_products()
            
            if result.error:
                await message.answer(f"Ошибка: {result.message}")
                return
            
            products = result.payload
            if not products:
                await message.answer("Нет товаров для отслеживания\n\nДобавьте товар командой /add")
                return
            
            text = "<b>Отслеживаемые товары:</b>\n\n"
            
            for product in products:
                current_price = await self.price_manager.get_current_price(product.id)
                price_text = f"{current_price}₽" if current_price else "Нет данных"
                
                text += f"<b>ID:</b> {product.id}\n"
                text += f"<b>Название:</b> {product.name or 'Без названия'}\n"
                text += f"<b>Текущая цена:</b> {price_text}\n"
                text += f"<b>Ссылка:</b> {product.link}\n"
                
                builder = InlineKeyboardBuilder()
                builder.add(
                    types.InlineKeyboardButton(
                        text="История цен",
                        callback_data=f"history_{product.id}"
                    ),
                    types.InlineKeyboardButton(
                        text="Удалить",
                        callback_data=f"delete_{product.id}"
                    )
                )
                
                await message.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())
                text = ""
                
        except Exception as e:
            logger.error(f"Ошибка в cmd_list_products: {str(e)}")
            await message.answer("Произошла ошибка при получении списка товаров")
    
    async def cmd_add_product(self, message: Message, state: FSMContext):
        await message.answer(
            "<b>Добавление товара</b>\n\n"
            "Отправьте ссылку на товар с сайта xcom-shop.ru\n",
            parse_mode="HTML"
        )
        await state.set_state(ProductStates.waiting_for_link)
    
    async def process_product_link(self, message: Message, state: FSMContext):
        link = message.text.strip()
        
        if not link.startswith('https://www.xcom-shop.ru/'):
            await message.answer(
                "<b>Неверная ссылка</b>\n",
                parse_mode="HTML"
            )
            return
        
        await message.answer("Добавляем товар...")
        
        try:
            result = await self.price_manager.add_product(link=link)
            
            if result.error:
                await message.answer(f"Ошибка: {result.message}")
            else:
                product = result.payload
                await message.answer(
                    f"<b>Товар успешно добавлен!</b>\n\n"
                    f"<b>ID:</b> {product.id}\n"
                    f"<b>Название:</b> {product.name or 'Без названия'}\n"
                    f"<b>Ссылка:</b> {product.link}\n\n"
                    f"Цена будет обновлена при следующем запуске мониторинга",
                    parse_mode="HTML"
                )
            
            await state.clear()
            
        except Exception as e:
            logger.error(f"Ошибка при добавлении товара: {str(e)}")
            await message.answer("Произошла ошибка при добавлении товара")
            await state.clear()
    
    async def cmd_delete_product(self, message: Message, state: FSMContext):
        await message.answer(
            "<b>Удаление товара</b>\n\n"
            "Отправьте ID товара для удаления\n"
            "Чтобы посмотреть список товаров, используйте /list",
            parse_mode="HTML"
        )
        await state.set_state(ProductStates.waiting_for_product_id)
    
    async def process_product_id(self, message: Message, state: FSMContext):
        try:
            product_id = int(message.text.strip())
            
            products_result = await self.price_manager.get_all_products()
            if not products_result.error:
                product = next((p for p in products_result.payload if p.id == product_id), None)
                if product:
                    builder = InlineKeyboardBuilder()
                    builder.add(
                        types.InlineKeyboardButton(
                            text="Да, удалить",
                            callback_data=f"confirm_delete_{product_id}"
                        ),
                        types.InlineKeyboardButton(
                            text="Отмена",
                            callback_data="cancel_delete"
                        )
                    )
                    
                    await message.answer(
                        f"<b>Подтвердите удаление</b>\n\n"
                        f"Вы действительно хотите удалить товар?\n\n"
                        f"<b>ID:</b> {product.id}\n"
                        f"<b>Название:</b> {product.name or 'Без названия'}\n"
                        f"<b>Ссылка:</b> {product.link}",
                        parse_mode="HTML",
                        reply_markup=builder.as_markup()
                    )
                else:
                    await message.answer("Товар с таким ID не найден")
            else:
                await message.answer("Ошибка при получении списка товаров")
            
            await state.clear()
            
        except ValueError:
            await message.answer("Пожалуйста, отправьте корректный числовой ID")
        except Exception as e:
            logger.error(f"Ошибка в process_product_id: {str(e)}")
            await message.answer("Произошла ошибка")
            await state.clear()
    
    async def process_delete_confirmation(self, callback: CallbackQuery):
        product_id = int(callback.data.replace("delete_", ""))
        
        products_result = await self.price_manager.get_all_products()
        if not products_result.error:
            product = next((p for p in products_result.payload if p.id == product_id), None)
            if product:
                builder = InlineKeyboardBuilder()
                builder.add(
                    types.InlineKeyboardButton(
                        text="Да, удалить",
                        callback_data=f"confirm_delete_{product_id}"
                    ),
                    types.InlineKeyboardButton(
                        text="Отмена",
                        callback_data="cancel_delete"
                    )
                )
                
                await callback.message.edit_text(
                    f"<b>Подтвердите удаление</b>\n\n"
                    f"Вы действительно хотите удалить товар?\n\n"
                    f"<b>ID:</b> {product.id}\n"
                    f"<b>Название:</b> {product.name or 'Без названия'}\n"
                    f"<b>Ссылка:</b> {product.link}",
                    parse_mode="HTML",
                    reply_markup=builder.as_markup()
                )
        
        await callback.answer()
    
    async def process_delete(self, callback: CallbackQuery):
        product_id = int(callback.data.replace("confirm_delete_", ""))
        
        try:
            result = await self.price_manager.delete_product(product_id)
            
            if result.error:
                await callback.message.edit_text(f"Ошибка: {result.message}")
            else:
                await callback.message.edit_text("Товар успешно удален")
            
        except Exception as e:
            logger.error(f"Ошибка при удалении товара: {str(e)}")
            await callback.message.edit_text("Произошла ошибка при удалении товара")
        
        await callback.answer()
    
    async def cancel_delete(self, callback: CallbackQuery):
        await callback.message.edit_text("Удаление отменено")
        await callback.answer()
    
    async def cmd_price_history(self, message: Message):
        await message.answer(
            "<b>История цен</b>\n\n"
            "Отправьте ID товара для просмотра истории цен\n"
            "Чтобы посмотреть список товаров, используйте /list",
            parse_mode="HTML"
        )
    
    async def show_price_history(self, callback: CallbackQuery):
        product_id = int(callback.data.replace("history_", ""))
        
        try:
            products_result = await self.price_manager.get_all_products()
            if products_result.error:
                await callback.message.answer("Ошибка при получении информации о товаре")
                return
            
            product = next((p for p in products_result.payload if p.id == product_id), None)
            if not product:
                await callback.message.answer("Товар не найден")
                return
            
            history_result = await self.price_manager.get_price_history(product_id)
            if history_result.error:
                await callback.message.answer(f"Ошибка: {history_result.message}")
                return
            
            price_history = history_result.payload
            if not price_history:
                await callback.message.answer(
                    f"<b>История цен</b>\n\n"
                    f"<b>Товар:</b> {product.name or 'Без названия'}\n"
                    f"<b>ID:</b> {product.id}\n\n"
                    f"Нет данных о ценах",
                    parse_mode="HTML"
                )
                return
            
            text = f"<b>История цен</b>\n\n"
            text += f"<b>Товар:</b> {product.name or 'Без названия'}\n"
            text += f"<b>ID:</b> {product.id}\n\n"
            text += "<b>Последние 10 записей:</b>\n"
            
            for i, price_record in enumerate(price_history[:10]):
                text += f"{i+1}. {price_record.price}₽ - {price_record.created_at.strftime('%d.%m.%Y %H:%M')}\n"
            
            if len(price_history) > 10:
                text += f"\n... и еще {len(price_history) - 10} записей"
            
            await callback.message.answer(text, parse_mode="HTML")
            
        except Exception as e:
            logger.error(f"Ошибка в show_price_history: {str(e)}")
            await callback.message.answer("Произошла ошибка при получении истории цен")
        
        await callback.answer()
    
    async def cmd_health(self, message: Message):
        try:
            result = await self.price_manager.get_all_products()
            status = "Бот работает нормально" if not result.error else "Есть проблемы с базой данных"
            
            await message.answer(
                f"🏥 <b>Статус бота</b>\n\n"
                f"{status}\n"
                f"База данных: {'Доступна' if not result.error else 'Недоступна'}",
                parse_mode="HTML"
            )
            
        except Exception as e:
            await message.answer("Бот не работает нормально")
    
    async def start(self):
        try:
            await db_manager.initialize_database()
            logger.info("Бот запускается...")
            
            await self.dp.start_polling(self.bot)
            
        except Exception as e:
            logger.error(f"Ошибка при запуске бота: {str(e)}")
        finally:
            if self.parser:
                self.parser.close()

async def main():
    BOT_TOKEN = settings.TELEGRAM_BOT_TOKEN
    
    logger.info("Запуск бота мониторинга цен...")
    bot = PriceMonitorBot(BOT_TOKEN)
    await bot.start()

if __name__ == "__main__":
    asyncio.run(main())