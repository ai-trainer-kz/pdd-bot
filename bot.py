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

ADMIN_ID = 503301815
KASPI = "4400430352720152"

MODEL = "gpt-4o-mini"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
client = OpenAI(api_key=OPENAI_API_KEY)

logging.basicConfig(level=logging.INFO)

users = {}
last_questions = {}

# ===== SAVE / LOAD =====
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

# ===== LOG PAYMENTS =====
def log_payment(user_id, plan):
    with open("payments.log", "a", encoding="utf-8") as f:
        f.write(f"{datetime.now()} | {user_id} | {plan}\n")

# ===== USER =====
def ensure_user(uid):
    uid = str(uid)
    if uid not in users:
        users[uid] = {
            "mode": None,
            "correct_answer": None,
            "explanation": "",
            "free_limit": 5,
            "used_free": 0,
            "premium_until": None,
            "plan": None,
            "status": None,  # NEW
            "correct": 0,
            "wrong": 0,
            "exam_count": 0,
            "exam_correct": 0
        }
        save_users()

def has_access(u):
    try:
        if u["premium_until"] and datetime.now() < datetime.fromisoformat(u["premium_until"]):
            return True
    except:
        pass
    return u["used_free"] < u["free_limit"]

# ===== UI =====
def main_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🎯 Тренировка", "🧠 Экзамен")
    kb.add("📊 Статистика", "💳 Купить доступ")
    return kb

def answer_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("A","B","C","D")
    kb.add("⬅️ Назад")
    return kb

# ===== GPT =====
def ask_gpt(uid):
    prompt = """
Ты экзаменатор ПДД Казахстан.

Сгенерируй 1 НОВЫЙ вопрос.

Формат:
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
        messages=[{"role":"user","content":prompt}],
        temperature=0.8
    )

    text = r.choices[0].message.content

    ans = re.search(r"Правильный ответ[:\s]*([ABCD])", text)
    exp = re.search(r"Объяснение[:\s]*(.*)", text, re.S)

    question_only = re.sub(r"Правильный ответ.*", "", text, flags=re.S)
    question_only = re.sub(r"Объяснение.*", "", question_only, flags=re.S)

    if last_questions.get(uid) == question_only:
        return ask_gpt(uid)

    last_questions[uid] = question_only

    return question_only, ans.group(1) if ans else "A", exp.group(1).strip() if exp else ""

# ===== START =====
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    ensure_user(message.from_user.id)

    u = users[str(message.from_user.id)]

    # если уже оплатил — восстановим доступ
    if u.get("premium_until"):
        try:
            if datetime.now() < datetime.fromisoformat(u["premium_until"]):
                await message.answer("🔥 У тебя уже есть доступ!")
        except:
            pass

    await message.answer(
        "🚗 Подготовка к ПДД\n\n"
        "🎁 5 бесплатных вопросов\n"
        "📊 Проверь уровень\n"
        "🚀 Сдай экзамен с первого раза\n\n"
        "👇 Выбери режим:",
        reply_markup=main_kb()
    )

# ===== BUY =====
@dp.message_handler(lambda m: "Купить" in m.text)
async def buy(message: types.Message):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("7 дней — 5000₸")
    kb.add("30 дней — 10000₸")
    kb.add("⬅️ Назад")

    await message.answer("💰 Выбери тариф:", reply_markup=kb)

# ===== PLAN =====
@dp.message_handler(lambda m: m.text in ["7 дней — 5000₸", "30 дней — 10000₸"])
async def plan(message: types.Message):
    u = users[str(message.from_user.id)]

    u["plan"] = 7 if "7" in message.text else 30
    save_users()

    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("✅ Я оплатил")
    kb.add("⬅️ Назад")

    await message.answer(
        f"💳 Kaspi: {KASPI}\n\n"
        f"📦 Тариф: {u['plan']} дней\n\n"
        "1️⃣ Оплати\n2️⃣ Нажми «Я оплатил»",
        reply_markup=kb
    )

# ===== PAYMENT =====
@dp.message_handler(lambda m: m.text == "✅ Я оплатил")
async def paid(message: types.Message):
    user = message.from_user
    u = users.get(str(user.id), {})

    u["status"] = "pending"
    save_users()

    log_payment(user.id, u.get("plan"))

    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("7 дней", callback_data=f"give_7_{user.id}"),
        InlineKeyboardButton("30 дней", callback_data=f"give_30_{user.id}")
    )
    kb.add(InlineKeyboardButton("❌ Отказать", callback_data=f"deny_{user.id}"))

    now = datetime.now()

    await bot.send_message(
        ADMIN_ID,
        f"📅 {now.strftime('%d.%m.%Y')}\n"
        f"⏰ {now.strftime('%H:%M')}\n\n"
        f"💰 ОПЛАТА\n\n"
        f"👤 @{user.username or 'нет'}\n"
        f"🆔 ID: {user.id}\n"
        f"📦 Тариф: {u.get('plan')}",
        reply_markup=kb
    )

    await message.answer("✅ Отправлено админу")

# ===== GIVE ACCESS =====
@dp.callback_query_handler(lambda c: c.data.startswith("give_"))
async def give(callback: types.CallbackQuery):
    data = callback.data.split("_")
    days = int(data[1])
    uid = data[2]

    users[uid]["premium_until"] = (datetime.now() + timedelta(days=days)).isoformat()
    users[uid]["status"] = "active"
    save_users()

    await bot.send_message(uid, f"🔥 Доступ открыт на {days} дней")
    await callback.answer("OK")

# ===== DENY =====
@dp.callback_query_handler(lambda c: c.data.startswith("deny_"))
async def deny(callback: types.CallbackQuery):
    uid = callback.data.split("_")[1]

    users[uid]["status"] = "denied"
    save_users()

    await bot.send_message(uid, "❌ Оплата отклонена")
    await callback.answer("OK")

# ===== RUN =====
if __name__ == "__main__":
    load_users()
    executor.start_polling(dp, skip_updates=True)
