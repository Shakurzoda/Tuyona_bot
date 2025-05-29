import logging
import asyncio
import os

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
    InlineKeyboardMarkup, InlineKeyboardButton, Message
)
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")  # Пример: -1001234567890 или @tuyona_channel

logging.basicConfig(level=logging.INFO)

bot = Bot(token=TOKEN)
dp = Dispatcher()

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
    keyboard=[[KeyboardButton(text="🔙 Назад")]],
    resize_keyboard=True
)

confirm_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить заявку", callback_data="confirm")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_phone")]
    ]
)

@dp.message(Command("start"))
async def start_handler(message: Message):
    user_id = message.from_user.id
    user_data[user_id] = {}
    user_step[user_id] = "category"

    name = message.from_user.first_name or "гость"
    await message.answer(
        f"Здравствуйте, {name}! Я бот Sino от компании Tuyona. "
        f"Я готов помочь вам с отправкой заявки. Давайте начнем."
    )
    await message.answer(
        "Выберите категорию, в которой вы хотели бы стать нашим партнёром:",
        reply_markup=category_keyboard
    )

@dp.message(F.text == "🔙 Назад")
async def go_back(message: Message):
    user_id = message.from_user.id
    step = user_step.get(user_id)

    if step == "company":
        user_step[user_id] = "category"
        await message.answer("Выберите категорию:", reply_markup=category_keyboard)
    elif step == "media":
        user_step[user_id] = "company"
        await message.answer("Введите название вашей компании, группы или имя:", reply_markup=back_keyboard)
    elif step == "price":
        user_step[user_id] = "media"
        await message.answer(
            "Снова отправьте ссылку или до 5 медиафайлов.\nДопустимо: 1 видео и до 4 фото, или только фото, или только видео.",
            reply_markup=back_keyboard
        )
    elif step == "phone":
        user_step[user_id] = "price"
        await message.answer("Укажите цену за вашу услугу:", reply_markup=back_keyboard)
    else:
        await message.answer("Вы уже в начале. Введите /start, чтобы начать заново.")

@dp.callback_query(F.data == "back_to_phone")
async def back_to_phone(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    user_step[user_id] = "phone"
    await callback.message.answer("Укажите ваш номер телефона:", reply_markup=back_keyboard)
    await callback.answer()

@dp.message(F.text.in_({
    "Рестораны", "Оформление", "Певец", "Салон красоты", "Оператор/Фотограф", "Музыканты"
}))
async def category_handler(message: Message):
    user_id = message.from_user.id
    user_data[user_id]["category"] = message.text
    user_step[user_id] = "company"
    await message.answer("Введите название вашей компании, группы или имя:", reply_markup=back_keyboard)

@dp.message()
async def handle_steps(message: Message):
    user_id = message.from_user.id
    if user_id not in user_data:
        await message.answer("Начните с команды /start.")
        return

    step = user_step.get(user_id)
    data = user_data[user_id]

    if step == "company":
        data["company"] = message.text
        data["media"] = []
        data["video_uploaded"] = False
        user_step[user_id] = "media"
        await message.answer(
            "Отправьте ссылку или до 5 файлов: фото и/или видео.\n"
            "Можно 1 видео и до 4 фото, или 5 фото, или только 1 видео.",
            reply_markup=back_keyboard
        )
        return

    if step == "media" and message.text and ("instagram.com" in message.text or "youtu" in message.text):
        data["link"] = message.text
        user_step[user_id] = "price"
        await message.answer("Ссылка сохранена ✅\nТеперь укажите цену:", reply_markup=back_keyboard)
        return

    if step == "media":
        if "media" not in data:
            data["media"] = []
            data["video_uploaded"] = False

        media_count = len(data["media"])

        if message.video:
            if data["video_uploaded"]:
                await message.answer("Вы уже отправили видео. Можно только одно.")
                return
            if media_count >= 5:
                await message.answer("Вы уже отправили 5 файлов.")
                return
            data["media"].append(message.video.file_id)
            data["video_uploaded"] = True
            await message.answer(f"Видео загружено. Файлов: {len(data['media'])}/5")
        elif message.photo:
            if media_count >= 5:
                await message.answer("Вы уже отправили 5 файлов.")
                return
            data["media"].append(message.photo[-1].file_id)
            await message.answer(f"Фото загружено. Файлов: {len(data['media'])}/5")
        else:
            await message.answer("Отправьте ссылку или файл.")
            return

        if len(data["media"]) == 5:
            user_step[user_id] = "price"
            await message.answer("Вы загрузили 5 файлов. ✅\nУкажите цену:", reply_markup=back_keyboard)
        return

    if step == "price":
        if any(char.isdigit() for char in message.text):
            data["price"] = message.text
            user_step[user_id] = "phone"
            await message.answer("Цена сохранена ✅\nУкажите номер телефона:", reply_markup=back_keyboard)
        else:
            await message.answer("Укажите цену в формате: 5000₽, от 10 000 руб и т.д.")
        return

    if step == "phone":
        data["phone"] = message.text
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
        await message.answer(summary, reply_markup=confirm_keyboard)
        return

    await message.answer("Следуйте шагам или введите /start.")

@dp.callback_query(F.data == "confirm")
async def confirm_submission(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    data = user_data.get(user_id)
    if not data:
        await callback.message.answer("Что-то пошло не так. Введите /start.")
        return

    text = (
        f"🎉 Новая заявка от партнёра!\n\n"
        f"📌 Категория: {data.get('category')}\n"
        f"🏷 Название: {data.get('company')}\n"
        f"🔗 Ссылка: {data.get('link', '—')}\n"
        f"💰 Цена: {data.get('price')}\n"
        f"📞 Телефон: {data.get('phone')}"
    )

    # Отправка заявки в канал
    try:
        await bot.send_message(CHANNEL_ID, text)

        # Отправка медиа при наличии
        if data.get("media"):
            media_group = []
            for file_id in data["media"]:
                if file_id.startswith("BAACAg"):  # исключить стикеры и пр.
                    continue
                media_group.append(types.InputMediaPhoto(media=file_id))
            if media_group:
                await bot.send_media_group(CHANNEL_ID, media_group[:10])  # максимум 10

        await callback.message.answer("Ваша заявка отправлена ✅", reply_markup=ReplyKeyboardRemove())
        await callback.message.answer("Хотите отправить ещё одну заявку? Введите /start")

    except Exception as e:
        await callback.message.answer(f"Ошибка при отправке заявки: {e}")

    user_step[user_id] = "done"
    await callback.answer()

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())