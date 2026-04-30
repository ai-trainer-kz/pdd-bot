import os
import logging
import json
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor

from openai import OpenAI

BOT_TOKEN = os.getenv("BOT_TOKEN")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

DATA_FILE = "users.json"

def load_users():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_users():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

users = load_users()
FREE_LIMIT = 5

def is_premium(user_id):
    user = users.get(user_id)
    if not user or not user.get("premium"):
        return False

    expires = user.get("expires")
    if not expires:
        return False

    expires_date = datetime.strptime(expires, "%Y-%m-%d")

    if datetime.now() > expires_date:
        user["premium"] = False
        save_users()
        return False

    return True

# ===== КНОПКИ =====
main_kb = ReplyKeyboardMarkup(resize_keyboard=True)
main_kb.add("🚗 Тест ПДД", "📚 Обучение")
main_kb.add("💰 Купить")

answers_kb = ReplyKeyboardMarkup(resize_keyboard=True)
answers_kb.add("A", "B", "C", "D")
answers_kb.add("🛑 Стоп")

pay_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="✅ Я оплатил", callback_data="paid")]
])

# ===== START =====
@dp.message_handler(commands=["start"])
async def start(msg: types.Message):
    uid = str(msg.from_user.id)

    users[uid] = users.get(uid, {
        "free_used": 0,
        "premium": False,
        "expires": None
    })
    save_users()

    await msg.answer(
        "🚗 Привет! Я AI-тренер по ПДД KZ\n\nВыбери режим 👇",
        reply_markup=main_kb
    )

# ===== КУПИТЬ =====
@dp.message_handler(lambda msg: msg.text == "💰 Купить")
async def buy(msg: types.Message):
    await msg.answer(
        "Полный доступ:\n7 дней — 5000 тг\n30 дней — 10000 тг\n\nПосле оплаты нажми кнопку ниже 👇",
        reply_markup=pay_kb
    )

@dp.callback_query_handler(lambda c: c.data == "paid")
async def paid(callback: types.CallbackQuery):
    await callback.message.answer("Отправь чек администратору")
    await callback.answer()

# ===== ТЕСТ =====
@dp.message_handler(lambda msg: msg.text == "🚗 Тест ПДД")
async def test(msg: types.Message):
    await send_question(msg)

# ===== СТОП =====
@dp.message_handler(lambda msg: msg.text == "🛑 Стоп")
async def stop(msg: types.Message):
    await msg.answer("Тест остановлен", reply_markup=main_kb)

# ===== ВОПРОС =====
async def send_question(msg):
    uid = str(msg.from_user.id)
    user = users[uid]

    if not is_premium(uid) and user["free_used"] >= FREE_LIMIT:
        await msg.answer("Лимит закончился. Купи доступ")
        return

    prompt = """
Ты — экзаменатор ПДД Казахстана.

Задай 1 вопрос как на экзамене.
Формат:
Вопрос
A)
B)
C)
D)

НЕ пиши ответ
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    q = response.choices[0].message.content

    user["last_question"] = q

    if not is_premium(uid):
        user["free_used"] += 1

    save_users()

    await msg.answer(q, reply_markup=answers_kb)

# ===== ОТВЕТ =====
@dp.message_handler(lambda msg: msg.text in ["A", "B", "C", "D"])
async def answer(msg: types.Message):
    uid = str(msg.from_user.id)
    user = users.get(uid)

    if "last_question" not in user:
        return

    prompt = f"""
Вопрос:
{user['last_question']}

Ответ пользователя: {msg.text}

Скажи:
1. Правильно или нет
2. Короткое объяснение
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    res = response.choices[0].message.content

    await msg.answer(res)

    await send_question(msg)

# ===== ЗАПУСК =====
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
