import logging
import asyncio
import os
import re
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
    InlineKeyboardMarkup, InlineKeyboardButton, Message
)
from aiogram.exceptions import TelegramBadRequest
from dotenv import load_dotenv

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

# Проверка переменных окружения
if not TOKEN:
    logger.error("BOT_TOKEN не задан в .env файле")
    raise ValueError("BOT_TOKEN обязателен")
if not CHANNEL_ID:
    logger.error("CHANNEL_ID не задан в .env файле")
    raise ValueError("CHANNEL_ID обязателен")
if not (CHANNEL_ID.startswith("-100") and CHANNEL_ID[1:].isdigit()) and not CHANNEL_ID.startswith("@"):
    logger.error("CHANNEL_ID должен быть числовым ID (например, -1001234567890) или именем (например, @channel)")
    raise ValueError("Неверный формат CHANNEL_ID")

# Инициализация бота и диспетчера
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Хранилище данных и состояний
user_data = {}
user_step = {}

# Клавиатуры
category_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Рестораны"), KeyboardButton(text="Оформление")],
        [KeyboardButton(text="Певец"), KeyboardButton(text="Салон красоты")],
        [KeyboardButton(text="Оператор/Фотограф"), KeyboardButton(text="Музыканты")],
        [KeyboardButton(text="🔙 Назад")]
    ],
    resize_keyboard=True
)

back_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🔙 Назад"), KeyboardButton(text="🔄 Заполнить заново")]
    ],
    resize_keyboard=True
)

price_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="5000 TJS"), KeyboardButton(text="10000 TJS")],
        [KeyboardButton(text="от 15000 TJS"), KeyboardButton(text="Договорная")],
        [KeyboardButton(text="🔙 Назад"), KeyboardButton(text="🔄 Заполнить заново")]
    ],
    resize_keyboard=True
)

confirm_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить заявку", callback_data="confirm")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_phone")]
    ]
)

def get_media_keyboard():
    """Создает инлайн-клавиатуру для добавления медиа или продолжения."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📎 Добавить еще", callback_data="add_media")],
            [InlineKeyboardButton(text="➡️ Продолжить", callback_data="proceed_to_price")]
        ]
    )

def sanitize_text(text: str) -> str:
    """Экранирование зарезервированных символов для MarkdownV2."""
    if not text:
        return text
    reserved_chars = r'[_*[\]()~`>#+=|{}.!-]'
    return re.sub(reserved_chars, r'\\\g<0>', text)

@dp.message(Command("start"))
async def start_handler(message: Message):
    user_id = message.from_user.id
    # Очистка данных пользователя для сброса состояния
    user_data.pop(user_id, None)
    user_step.pop(user_id, None)
    user_data[user_id] = {}
    user_step[user_id] = "category"

    name = message.from_user.first_name or "гость"
    try:
        await message.answer(
            f"Здравствуйте, {name}! Я бот Sino от компании Tuyona. Я помогу вам отправить заявку. Выберите категорию партнёрства:",
            reply_markup=category_keyboard
        )
    except Exception as e:
        logger.error(f"Ошибка при отправке стартового сообщения: {e}")
        await message.answer("Произошла ошибка. Попробуйте снова или свяжитесь с поддержкой.")

@dp.message(F.text == "🔙 Назад")
async def go_back(message: Message):
    user_id = message.from_user.id
    step = user_step.get(user_id, "category")

    try:
        if step == "company":
            user_step[user_id] = "category"
            await message.answer("Выберите категорию:", reply_markup=category_keyboard)
        elif step == "media":
            user_step[user_id] = "company"
            await message.answer("Введите название вашей компании, группы или имя:", reply_markup=back_keyboard)
        elif step == "price":
            user_step[user_id] = "media"
            await message.answer(
                "Отправьте ссылку или до 5 медиафайлов (1 видео и до 4 фото, или только 5 фото, или 1 видео):",
                reply_markup=back_keyboard
            )
        elif step == "phone":
            user_step[user_id] = "price"
            await message.answer("Выберите или укажите цену за вашу услугу:", reply_markup=price_keyboard)
            await message.answer("Валюта: таджикские сомони (TJS)")
        else:
            await message.answer("Вы в начале. Введите /start, чтобы начать заново.")
    except Exception as e:
        logger.error(f"Ошибка в обработке команды 'Назад': {e}")
        await message.answer("Произошла ошибка. Попробуйте снова или свяжитесь с поддержкой.")

@dp.message(F.text == "🔄 Заполнить заново")
async def reset_handler(message: Message):
    user_id = message.from_user.id
    user_data.pop(user_id, None)
    user_step.pop(user_id, None)
    user_data[user_id] = {}
    user_step[user_id] = "category"
    try:
        await message.answer("Данные сброшены. Выберите категорию:", reply_markup=category_keyboard)
    except Exception as e:
        logger.error(f"Ошибка при сбросе данных: {e}")
        await message.answer("Произошла ошибка. Попробуйте снова или свяжитесь с поддержкой.")

@dp.callback_query(F.data == "back_to_phone")
async def back_to_phone(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    user_step[user_id] = "phone"
    try:
        await callback.message.answer("Укажите ваш номер телефона:", reply_markup=back_keyboard)
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка при возврате к вводу телефона: {e}")
        await callback.message.answer("Произошла ошибка. Попробуйте снова или свяжитесь с поддержкой.")

@dp.callback_query(F.data == "add_media")
async def add_media(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    user_step[user_id] = "media"
    try:
        await callback.message.answer(
            "Отправьте ссылку или до 5 медиафайлов (1 видео и до 4 фото, или только 5 фото, или 1 видео):",
            reply_markup=back_keyboard
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка при возврате к загрузке медиа: {e}")
        await callback.message.answer("Произошла ошибка. Попробуйте снова или свяжитесь с поддержкой.")

@dp.callback_query(F.data == "proceed_to_price")
async def proceed_to_price(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    user_step[user_id] = "price"
    try:
        await callback.message.answer("Выберите или укажите цену за вашу услугу:", reply_markup=price_keyboard)
        await callback.message.answer("Валюта: таджикские сомони (TJS)")
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка при переходе к вводу цены: {e}")
        await callback.message.answer("Произошла ошибка. Попробуйте снова или свяжитесь с поддержкой.")

@dp.message(F.text.in_({
    "Рестораны", "Оформление", "Певец", "Салон красоты", "Оператор/Фотограф", "Музыканты"
}))
async def category_handler(message: Message):
    user_id = message.from_user.id
    user_data[user_id]["category"] = message.text
    user_step[user_id] = "company"
    try:
        await message.answer("Введите название вашей компании, группы или имя:", reply_markup=back_keyboard)
    except Exception as e:
        logger.error(f"Ошибка при выборе категории: {e}")
        await message.answer("Произошла ошибка. Попробуйте снова или свяжитесь с поддержкой.")

@dp.message()
async def handle_steps(message: Message):
    user_id = message.from_user.id
    if user_id not in user_data:
        try:
            await message.answer("Начните с команды /start.")
            return
        except Exception as e:
            logger.error(f"Ошибка при проверке user_data: {e}")
            await message.answer("Произошла ошибка. Попробуйте снова или свяжитесь с поддержкой.")
            return

    step = user_step.get(user_id)
    data = user_data[user_id]

    try:
        if step == "company":
            if len(message.text) > 100:
                await message.answer("Название слишком длинное (макс. 100 символов). Попробуйте снова:")
                return
            data["company"] = sanitize_text(message.text)
            data["media"] = []
            data["video_uploaded"] = False
            user_step[user_id] = "media"
            await message.answer(
                "Отправьте ссылку или до 5 медиафайлов (1 видео и до 4 фото, или только 5 фото, или 1 видео):",
                reply_markup=back_keyboard
            )
            return

        if step == "media":
            if message.text and ("instagram.com" in message.text or "youtu" in message.text):
                data["link"] = message.text
                user_step[user_id] = "price"
                await message.answer("Ссылка сохранена ✅")
                await message.answer("Выберите или укажите цену за вашу услугу:", reply_markup=price_keyboard)
                await message.answer("Валюта: таджикские сомони (TJS)")
                return

            if "media" not in data:
                data["media"] = []
                data["video_uploaded"] = False

            media_count = len(data["media"])

            if message.video:
                if data["video_uploaded"]:
                    await message.answer("Можно загрузить только одно видео.")
                    return
                if media_count >= 5:
                    await message.answer("Достигнут лимит в 5 файлов.")
                    return
                data["media"].append(("video", message.video.file_id))
                data["video_uploaded"] = True
                await message.answer(f"Видео загружено. Файлов: {media_count + 1}/5")
            elif message.photo:
                if media_count >= 5:
                    await message.answer("Достигнут лимит в 5 файлов.")
                    return
                data["media"].append(("photo", message.photo[-1].file_id))
                await message.answer(f"Фото загружено. Файлов: {media_count + 1}/5")
            else:
                await message.answer("Отправьте ссылку, фото или видео (другие типы файлов не поддерживаются).")
                return

            if len(data["media"]) < 5:
                await message.answer(f"Загружено файлов: {len(data['media'])}/5", reply_markup=get_media_keyboard())
            else:
                user_step[user_id] = "price"
                await message.answer("Загружено 5 файлов ✅")
                await message.answer("Выберите или укажите цену за вашу услугу:", reply_markup=price_keyboard)
                await message.answer("Валюта: таджикские сомони (TJS)")
            return

        if step == "price":
            if re.match(r"^(от\s)?\d+(\s?(TJS|сомони))?$", message.text.strip()) or message.text.strip() == "Договорная":
                data["price"] = sanitize_text(message.text)
                user_step[user_id] = "phone"
                await message.answer("Цена сохранена ✅")
                await message.answer("Укажите ваш номер телефона (например, +992123456789 или 123456789):", reply_markup=back_keyboard)
            else:
                await message.answer("Выберите цену из предложенных или укажите в формате: 5000, 5000 TJS, от 10000 сомони или Договорная.")
            return

        if step == "phone":
            phone = message.text.strip()
            if re.match(r"^(\+992)?\d{9}$", phone):
                data["phone"] = sanitize_text(phone)
                user_step[user_id] = "confirm"

                summary = (
                    f"📝 Проверьте заявку:\n\n"
                    f"📌 Категория: {data.get('category')}\n"
                    f"🏷 Название: {data.get('company')}\n"
                    f"🔗 Ссылка: {data.get('link', '—')}\n"
                    f"📎 Файлов: {len(data.get('media', []))}\n"
                    f"💰 Цена: {data.get('price')}\n"
                    f"📞 Телефон: {data.get('phone')}\n\n"
                    f"Все верно?"
                )
                await message.answer(summary, reply_markup=confirm_keyboard, parse_mode="MarkdownV2")
            else:
                await message.answer("Укажите корректный номер телефона (например, +992123456789 или 123456789).")
            return

        await message.answer("Следуйте шагам или введите /start.")
    except Exception as e:
        logger.error(f"Ошибка в обработке шага {step}: {e}")
        await message.answer("Произошла ошибка. Попробуйте снова или свяжитесь с поддержкой.")

@dp.callback_query(F.data == "confirm")
async def confirm_submission(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    data = user_data.get(user_id)
    if not data:
        try:
            await callback.message.answer("Что-то пошло не так. Введите /start.")
            await callback.answer()
        except Exception as e:
            logger.error(f"Ошибка при обработке подтверждения: {e}")
        return

    text = (
        f"🎉 Новая заявка от партнёра\!\n\n"
        f"📌 Категория: {data.get('category')}\n"
        f"🏷 Название: {data.get('company')}\n"
        f"🔗 Ссылка: {data.get('link', '—')}\n"
        f"💰 Цена: {data.get('price')}\n"
        f"📞 Телефон: {data.get('phone')}"
    )

    try:
        # Отправка текста в канал
        await bot.send_message(CHANNEL_ID, text, parse_mode="MarkdownV2")

        # Отправка медиа, если есть
        if data.get("media"):
            media_group = []
            for media_type, file_id in data["media"]:
                if media_type == "photo":
                    media_group.append(types.InputMediaPhoto(media=file_id))
                elif media_type == "video":
                    media_group.append(types.InputMediaVideo(media=file_id))
            if media_group:
                await bot.send_media_group(CHANNEL_ID, media_group[:10])

        await callback.message.answer("Ваша заявка отправлена ✅", reply_markup=ReplyKeyboardRemove())
        await callback.message.answer("Хотите отправить ещё одну заявку? Введите /start")

        # Очистка данных пользователя
        user_data.pop(user_id, None)
        user_step.pop(user_id, None)

    except TelegramBadRequest as e:
        logger.error(f"Ошибка отправки в канал: {e}")
        await callback.message.answer("Ошибка при отправке заявки: неверный формат данных.")
    except Exception as e:
        logger.error(f"Неожиданная ошибка при отправке: {e}")
        await callback.message.answer("Произошла ошибка. Попробуйте позже или свяжитесь с поддержкой.")

    try:
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка при подтверждении callback: {e}")

async def main():
    try:
        await dp.start_polling(bot)
    except asyncio.exceptions.CancelledError:
        logger.info("Поллинг бота остановлен")
    except Exception as e:
        logger.error(f"Ошибка работы бота: {e}")
        try:
            await bot.send_message(CHANNEL_ID, "Бот столкнулся с ошибкой и остановлен. Проверьте логи.")
        except Exception as send_e:
            logger.error(f"Не удалось отправить сообщение об ошибке в канал: {send_e}")
        raise

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")