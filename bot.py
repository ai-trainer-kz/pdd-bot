import os
import logging
import json
from datetime import datetime

from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

DATA_FILE = "users.json"

# ====== DATA ======
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

# ====== PREMIUM ======
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

# ====== KEYBOARDS ======
lang_kb = ReplyKeyboardMarkup(resize_keyboard=True)
lang_kb.add("🇷🇺 Русский", "🇰🇿 Қазақша")

def get_main_kb(lang):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    if lang == "kz":
        kb.add("🚗 Тест ПДД", "📚 Оқу")
        kb.add("💰 Сатып алу")
    else:
        kb.add("🚗 Тест ПДД", "📚 Обучение")
        kb.add("💰 Купить")
    return kb

answers_kb = ReplyKeyboardMarkup(resize_keyboard=True)
answers_kb.add("A", "B", "C", "D")
answers_kb.add("🛑 Стоп")

pay_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="✅ Я оплатил / Төледім", callback_data="paid")]
])

# ====== START ======
@dp.message_handler(commands=["start"])
async def start(msg: types.Message):
    uid = str(msg.from_user.id)

    users[uid] = users.get(uid, {
        "free_used": 0,
        "premium": False,
        "expires": None,
        "lang": None
    })
    save_users()

    await msg.answer("Выбери язык / Тілді таңда:", reply_markup=lang_kb)

# ====== LANGUAGE ======
@dp.message_handler(lambda msg: msg.text in ["🇷🇺 Русский", "🇰🇿 Қазақша"])
async def set_lang(msg: types.Message):
    uid = str(msg.from_user.id)

    if "Русский" in msg.text:
        users[uid]["lang"] = "ru"
        text = "🚗 Привет! Я AI-тренер по ПДД KZ\n\nВыбери режим 👇"
    else:
        users[uid]["lang"] = "kz"
        text = "🚗 Сәлем! Мен ПДД бойынша AI жаттықтырушы\n\nТаңдаңыз 👇"

    save_users()

    await msg.answer(text, reply_markup=get_main_kb(users[uid]["lang"]))

# ====== BUY ======
@dp.message_handler(lambda msg: msg.text in ["💰 Купить", "💰 Сатып алу"])
async def buy(msg: types.Message):
    uid = str(msg.from_user.id)
    lang = users[uid]["lang"]

    if lang == "kz":
        text = "Толық қолжетімділік:\n7 күн — 5000 тг\n30 күн — 10000 тг"
    else:
        text = "Полный доступ:\n7 дней — 5000 тг\n30 дней — 10000 тг"

    await msg.answer(text, reply_markup=pay_kb)

@dp.callback_query_handler(lambda c: c.data == "paid")
async def paid(callback: types.CallbackQuery):
    await callback.message.answer("Отправь чек администратору / Чекті админге жібер")
    await callback.answer()

# ====== TEST ======
@dp.message_handler(lambda msg: "Тест ПДД" in msg.text)
async def test(msg: types.Message):
    await send_question(msg)

# ====== STOP ======
@dp.message_handler(lambda msg: msg.text == "🛑 Стоп")
async def stop(msg: types.Message):
    uid = str(msg.from_user.id)
    lang = users[uid]["lang"]

    text = "Тест остановлен" if lang == "ru" else "Тест тоқтатылды"

    await msg.answer(text, reply_markup=get_main_kb(lang))

# ====== QUESTION ======
async def send_question(msg):
    uid = str(msg.from_user.id)
    user = users[uid]
    lang = user["lang"]

    if not is_premium(uid) and user["free_used"] >= FREE_LIMIT:
        text = "Лимит закончился. Купи доступ" if lang == "ru" else "Лимит бітті. Сатып ал"
        await msg.answer(text)
        return

    if lang == "kz":
        prompt = """
Сен — Қазақстан ПДД емтиханшысы.

1 сұрақ қой.
Формат:
Сұрақ
A)
B)
C)
D)

Жауапты жазба
"""
    else:
        prompt = """
Ты — экзаменатор ПДД Казахстана.

Задай 1 вопрос.
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

# ====== ANSWER ======
@dp.message_handler(lambda msg: msg.text in ["A", "B", "C", "D"])
async def answer(msg: types.Message):
    uid = str(msg.from_user.id)
    user = users.get(uid)

    if not user or "last_question" not in user:
        return

    lang = user["lang"]

    if lang == "kz":
        prompt = f"""
Сұрақ:
{user['last_question']}

Пайдаланушы жауабы: {msg.text}

1. Дұрыс па
2. Қысқа түсіндіру
"""
    else:
        prompt = f"""
Вопрос:
{user['last_question']}

Ответ пользователя: {msg.text}

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

# ====== RUN ======
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
