import os
import logging
import json
from datetime import datetime, timedelta
import re

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
            "correct_answer": None,
            "explanation": "",
            "free_limit": 5,
            "used_free": 0,
            "premium_until": None,
            "plan": None
        }
        save_users()

def has_access(u):
    try:
        if u["premium_until"] and datetime.now() < datetime.fromisoformat(u["premium_until"]):
            return True
    except:
        pass

    return u["used_free"] < u["free_limit"]

# ===== TEXT =====
def t(u, ru, kz):
    return ru if u["lang"] == "ru" else kz

# ===== UI =====
def main_kb(u):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(t(u,"🎯 Тренировка","🎯 Жаттығу"), t(u,"🧠 Экзамен","🧠 Емтихан"))
    kb.add(t(u,"📊 Статистика","📊 Статистика"), t(u,"🌐 Язык","🌐 Тіл"))
    kb.add(t(u,"💳 Купить доступ","💳 Сатып алу"))
    return kb

def back_kb(u):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(t(u,"⬅️ Назад","⬅️ Артқа"))
    return kb

def answer_kb(u):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("A","B","C","D")
    kb.add(t(u,"⬅️ Назад","⬅️ Артқа"))
    return kb

def pay_kb(u):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(t(u,"💰 Оплатил","💰 Төледім"))
    kb.add(t(u,"⬅️ Назад","⬅️ Артқа"))
    return kb

# ===== GPT =====
def ask_gpt(u):
    try:
        prompt = f"""
Сделай экзаменационный вопрос ПДД.
НЕ ОШИБАЙСЯ В ПРАВИЛЬНОМ ОТВЕТЕ.

Формат строго:

Вопрос:
...

A) ...
B) ...
C) ...
D) ...

Правильный ответ: A
Объяснение: кратко
"""

        r = client.chat.completions.create(
            model=MODEL,
            messages=[{"role":"user","content":prompt}]
        )

        text = r.choices[0].message.content

        ans = re.search(r"Правильный ответ[:\s]*([ABCD])", text)
        exp = re.search(r"Объяснение[:\s]*(.*)", text, re.S)

        return text, ans.group(1) if ans else "A", exp.group(1).strip() if exp else ""

    except:
        return "Ошибка", "A", ""

# ===== START =====
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    ensure_user(message.from_user.id)
    u = users[str(message.from_user.id)]

    await message.answer(
        t(u,"🚗 AI ПДД\n\n5 бесплатных вопросов 🎁","🚗 AI ПДД\n\n5 тегін сұрақ 🎁"),
        reply_markup=main_kb(u)
    )

# ===== LANGUAGE =====
@dp.message_handler(lambda m: m.text in ["🌐 Язык","🌐 Тіл"])
async def lang(message: types.Message):
    await message.answer("Выбери / Таңда", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("🇷🇺 Русский","🇰🇿 Қазақша"))

@dp.message_handler(lambda m: m.text in ["🇷🇺 Русский","🇰🇿 Қазақша"])
async def set_lang(message: types.Message):
    u = users[str(message.from_user.id)]
    u["lang"] = "ru" if "Рус" in message.text else "kz"
    save_users()
    await message.answer("✅", reply_markup=main_kb(u))

# ===== BACK =====
@dp.message_handler(lambda m: "Назад" in m.text or "Артқа" in m.text)
async def back(message: types.Message):
    u = users[str(message.from_user.id)]
    await message.answer("🏠", reply_markup=main_kb(u))

# ===== BUY =====
@dp.message_handler(lambda m: "Купить" in m.text or "Сатып" in m.text)
async def buy(message: types.Message):
    u = users[str(message.from_user.id)]

    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🟢 7 дней — 2000₸   (заход)
    kb.add("🔵 30 дней — 7000₸  (основной)
    kb.add("🔴 90 дней — 15000₸ (выгодный)
    kb.add(t(u,"⬅️ Назад","⬅️ Артқа"))

    await message.answer("Тариф:", reply_markup=kb)

@dp.message_handler(lambda m: "дней" in m.text)
async def plan(message: types.Message):
    u = users[str(message.from_user.id)]

    if "7" in message.text: u["plan"]=7
    elif "30" in message.text: u["plan"]=30
    elif "90" in message.text: u["plan"]=90

    save_users()

    await message.answer(
        f"💳 Kaspi: {KASPI}\n\n"
        f"📦 Тариф: {u['plan']} дней\n\n"
        f"После оплаты нажми '💰 Оплатил' и отправь чек"
    ) 

@dp.message_handler(lambda m: "Оплатил" in m.text or "Төледім" in m.text)
async def paid(message: types.Message):
    u = users[str(message.from_user.id)]

    if not u.get("plan"):
        await message.answer("Сначала выбери тариф")
        return

    await message.answer("📸 Отправь чек (скрин)")

@dp.message_handler(content_types=types.ContentType.PHOTO)
async def receipt(message: types.Message):
    user = message.from_user
    u = users[str(user.id)]

    plan = u.get("plan", "не выбран")

    text = (
        f"💰 ОПЛАТА\n\n"
        f"👤 ID: {user.id}\n"
        f"👤 Username: @{user.username}\n"
        f"📦 Тариф: {plan} дней\n"
    )

    await bot.send_photo(
        ADMIN_ID,
        message.photo[-1].file_id,
        caption=text,
        reply_markup=InlineKeyboardMarkup().add(
            InlineKeyboardButton("✅ Выдать доступ", callback_data=f"give_{user.id}"),
            InlineKeyboardButton("❌ Отказать", callback_data=f"deny_{user.id}")
        )
    )

    await message.answer("⏳ Чек отправлен на проверку")

@dp.callback_query_handler(lambda c: c.data.startswith("deny_"))
async def deny(callback: types.CallbackQuery):
    uid = callback.data.split("_")[1]

    await bot.send_message(uid, "❌ Оплата не подтверждена")
    await callback.answer("Отказано")

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

    await send_question(message, u)

# ===== QUESTION =====
async def send_question(message, u):

    if not has_access(u):
        await message.answer("🔒 Купи доступ", reply_markup=pay_kb(u))
        return

    if not u["premium_until"]:
        u["used_free"] += 1

    text, ans, exp = ask_gpt(u)

    u["correct_answer"] = ans
    u["explanation"] = exp

    clean = re.sub(r"Правильный ответ.*", "", text, flags=re.S)
    clean = re.sub(r"Объяснение.*", "", clean, flags=re.S)

    await message.answer(clean, reply_markup=answer_kb(u))
    save_users()

# ===== ANSWER =====
@dp.message_handler(lambda m: m.text in ["A","B","C","D"])
async def answer(message: types.Message):
    u = users[str(message.from_user.id)]

    if message.text == u["correct_answer"]:
        await message.answer("✅ Верно")
    else:
        await message.answer(f"❌ Неверно\nОтвет: {u['correct_answer']}")

    if u["explanation"]:
        await message.answer(
            f"📘 Объяснение:\n{u['explanation'][:300]}"
        )

    await message.answer("👇 Следующий вопрос")

    await send_question(message, u)

# ===== RUN =====
if __name__ == "__main__":
    load_users()
    executor.start_polling(dp, skip_updates=True)
