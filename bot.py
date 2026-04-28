import os
import logging
import json
from datetime import datetime, timedelta
import re
import random

from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
from openai import OpenAI

# ===== CONFIG =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

ADMIN_ID = 8398266271
KASPI = "4400430352720152"

MODEL = "gpt-4o-mini"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
client = OpenAI(api_key=OPENAI_API_KEY)

logging.basicConfig(level=logging.INFO)

users = {}

# ===== SAVE =====
def save_users():
    with open("users.json", "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def load_users():
    global users
    try:
        with open("users.json", "r", encoding="utf-8") as f:
            users = json.load(f)
    except:
        users = {}

# ===== USER =====
def ensure_user(uid):
    uid = str(uid)
    if uid not in users:
        users[uid] = {
            "lang": "ru",
            "mode": None,
            "topic": None,
            "level": None,
            "correct": 0,
            "wrong": 0,
            "total_correct": 0,
            "total_wrong": 0,
            "exam_q": 0,
            "premium_until": None,
            "correct_answer": None,
            "free_limit": 5,
            "used_free": 0,
            "plan": None
        }
        save_users()

def has_access(u):
    try:
        if u["premium_until"] and datetime.now() < datetime.fromisoformat(u["premium_until"]):
            return True
    except:
        pass

    if u["used_free"] < u["free_limit"]:
        return True

    return False

# ===== UI =====
def t(u, ru, kz):
    return ru if u["lang"] == "ru" else kz

def main_kb(u):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(t(u,"🎯 Тренировка","🎯 Жаттығу"), t(u,"🧠 Экзамен","🧠 Емтихан"))
    kb.add(t(u,"📊 Статистика","📊 Статистика"), t(u,"🌐 Язык","🌐 Тіл"))
    kb.add(t(u,"💳 Купить доступ","💳 Қолжетімділік сатып алу"))
    return kb

def lang_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🇷🇺 Русский", "🇰🇿 Қазақша")
    return kb

def topic_kb(u):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🚸 Знаки","🛣 Разметка")
    kb.add("🚦 Перекрестки","🚗 Общие")
    kb.add("⬅️ Назад")
    return kb

def level_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🟢 Легкий","🟡 Средний","🔴 Сложный")
    kb.add("⬅️ Назад")
    return kb

def answer_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("A","B","C","D")
    return kb

def pay_kb(u):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(t(u,"💰 Оплатил","💰 Төледім"))
    kb.add("⬅️ Назад")
    return kb

# ===== GPT =====
def system_prompt(u):
    lang = "на русском" if u["lang"] == "ru" else "қазақ тілінде"

    return f"""
Ты экзаменатор ПДД. Отвечай {lang}.

Сделай 1 вопрос.

Формат:
Вопрос:
...
A) ...
B) ...
C) ...
D) ...

Правильный ответ:
A
"""

def ask_gpt(u):
    try:
        r = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role":"system","content":system_prompt(u)},
                {"role":"user","content":"Вопрос"}
            ]
        )
        return r.choices[0].message.content
    except:
        return None

# ===== START =====
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    ensure_user(message.from_user.id)
    u = users[str(message.from_user.id)]

    await message.answer(
        t(u,
          "🚗 AI ПДД Инструктор\n\n5 бесплатных вопросов 🎁",
          "🚗 AI ПДД Инструктор\n\n5 тегін сұрақ 🎁"),
        reply_markup=main_kb(u)
    )

# ===== LANGUAGE =====
@dp.message_handler(lambda m: m.text in ["🌐 Язык","🌐 Тіл"])
async def lang(message: types.Message):
    await message.answer("Тілді таңда / Выбери язык", reply_markup=lang_kb())

@dp.message_handler(lambda m: m.text in ["🇷🇺 Русский","🇰🇿 Қазақша"])
async def set_lang(message: types.Message):
    u = users[str(message.from_user.id)]
    u["lang"] = "ru" if "Рус" in message.text else "kz"
    save_users()

    await message.answer("✅ OK", reply_markup=main_kb(u))

# ===== BUY =====
@dp.message_handler(lambda m: "Купить" in m.text or "сатып" in m.text)
async def buy(message: types.Message):
    u = users[str(message.from_user.id)]

    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🟢 7 дней — 2000₸")
    kb.add("🔵 30 дней — 5000₸")
    kb.add("🔴 90 дней — 12000₸")

    await message.answer(
        t(u,"Выбери тариф:","Тариф таңда:"),
        reply_markup=kb
    )

@dp.message_handler(lambda m: "дней" in m.text)
async def plan(message: types.Message):
    u = users[str(message.from_user.id)]

    if "7" in message.text:
        u["plan"] = 7
    elif "30" in message.text:
        u["plan"] = 30
    elif "90" in message.text:
        u["plan"] = 90

    save_users()

    await message.answer(f"Kaspi: {KASPI}\nОтправь чек")

# ===== RECEIPT =====
@dp.message_handler(content_types=types.ContentType.PHOTO)
async def receipt(message: types.Message):
    await bot.send_photo(
        ADMIN_ID,
        message.photo[-1].file_id,
        caption=f"Оплата от {message.from_user.id}",
        reply_markup=InlineKeyboardMarkup().add(
            InlineKeyboardButton("Выдать", callback_data=f"give_{message.from_user.id}")
        )
    )
    await message.answer("⏳ Проверка...")

@dp.callback_query_handler(lambda c: c.data.startswith("give_"))
async def give(callback: types.CallbackQuery):
    uid = callback.data.split("_")[1]
    days = users[uid].get("plan",30)

    users[uid]["premium_until"] = (datetime.now()+timedelta(days=days)).isoformat()
    save_users()

    await bot.send_message(uid,"🔥 Доступ открыт")
    await callback.answer("OK")

# ===== MODE =====
@dp.message_handler(lambda m: "Тренировка" in m.text or "Жаттығу" in m.text or "Экзамен" in m.text or "Емтихан" in m.text)
async def mode(message: types.Message):
    u = users[str(message.from_user.id)]

    if not has_access(u):
        await message.answer("🔒 Лимит закончился", reply_markup=pay_kb(u))
        return

    u["mode"] = message.text
    save_users()

    await send_question(message, u)

# ===== QUESTION =====
async def send_question(message, u):

    if not has_access(u):
        await message.answer("🔒 Купи доступ", reply_markup=pay_kb(u))
        return

    if not u.get("premium_until"):
        u["used_free"] += 1

    text = ask_gpt(u)

    if not text:
        text = "Ошибка генерации"

    match = re.search(r"([ABCD])", text)
    u["correct_answer"] = match.group(1) if match else "A"

    await message.answer(text, reply_markup=answer_kb())
    save_users()

# ===== ANSWER =====
@dp.message_handler(lambda m: m.text in ["A","B","C","D"])
async def answer(message: types.Message):
    u = users[str(message.from_user.id)]

    if message.text == u["correct_answer"]:
        await message.answer("✅")
    else:
        await message.answer(f"❌ {u['correct_answer']}")

    await send_question(message, u)

# ===== RUN =====
if __name__ == "__main__":
    load_users()
    executor.start_polling(dp, skip_updates=True)
