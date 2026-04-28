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
            "mode": None,
            "correct_answer": None,
            "explanation": "",
            "free_limit": 5,
            "used_free": 0,
            "premium_until": None,
            "plan": None,
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

Ответ строго в формате:

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

    await message.answer(
        "🚗 Подготовка к ПДД\n\n"
        "🎁 5 бесплатных вопросов\n"
        "📊 Проверь уровень\n"
        "🚀 Сдай экзамен с первого раза\n\n"
        "👇 Выбери режим:",
        reply_markup=main_kb()
    )

# ===== MODE =====
@dp.message_handler(lambda m: m.text == "🎯 Тренировка")
async def train(message: types.Message):
    u = users[str(message.from_user.id)]
    u["mode"] = "train"

    if not has_access(u):
        await message.answer("🔒 Купи доступ", reply_markup=main_kb())
        return

    await send_question(message, u)

@dp.message_handler(lambda m: m.text == "🧠 Экзамен")
async def exam(message: types.Message):
    u = users[str(message.from_user.id)]
    u["mode"] = "exam"
    u["exam_count"] = 0
    u["exam_correct"] = 0

    await message.answer("🧠 Экзамен: 20 вопросов")
    await send_question(message, u)

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

    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("7 дней", callback_data=f"give_7_{user.id}"),
        InlineKeyboardButton("30 дней", callback_data=f"give_30_{user.id}")
    )
    kb.add(
        InlineKeyboardButton("❌ Отказать", callback_data=f"deny_{user.id}")
    )

    try:
        now = datetime.now()

        await bot.send_message(
            ADMIN_ID,
            f"📅 {now.strftime('%d.%m.%Y')}\n"
            f"⏰ {now.strftime('%H:%M')}\n\n"
            f"💰 ОПЛАТА\n\n"
            f"👤 @{user.username if user.username else 'нет'}\n"
            f"🆔 ID: {user.id}\n"
            f"🌍 Язык: {user.language_code or 'неизвестно'}\n"
            f"🏙 Город: не определён\n"
            f"📦 Тариф: {u.get('plan', 'не выбран')} дней",
            reply_markup=kb
        )

        await message.answer("✅ Отправлено админу на проверку")

    except Exception as e:
        print("ERROR ADMIN:", e)
        await message.answer("❌ Ошибка отправки админу")

# ===== CALLBACK =====
@dp.callback_query_handler(lambda c: c.data.startswith("give_"))
async def give(callback: types.CallbackQuery):
    data = callback.data.split("_")
    days = int(data[1])
    uid = data[2]

    users[uid]["premium_until"] = (datetime.now() + timedelta(days=days)).isoformat()
    save_users()

    await bot.send_message(uid, f"🔥 Доступ открыт на {days} дней")
    await callback.answer("Доступ выдан")

@dp.callback_query_handler(lambda c: c.data.startswith("deny_"))
async def deny(callback: types.CallbackQuery):
    uid = callback.data.split("_")[1]

    await bot.send_message(uid, "❌ Оплата отклонена")
    await callback.answer("Отклонено")

# ===== QUESTION =====
async def send_question(message, u):
    if not has_access(u):
        await message.answer("🔒 Купи доступ", reply_markup=main_kb())
        return

    if not u["premium_until"]:
        u["used_free"] += 1

    text, ans, exp = ask_gpt(message.from_user.id)

    u["correct_answer"] = ans
    u["explanation"] = exp

    await message.answer(text, reply_markup=answer_kb())
    save_users()

# ===== ANSWER =====
@dp.message_handler(lambda m: m.text in ["A","B","C","D"])
async def answer(message: types.Message):
    u = users[str(message.from_user.id)]

    if message.text == u["correct_answer"]:
        u["correct"] += 1
        if u["mode"] == "exam":
            u["exam_correct"] += 1
        await message.answer("✅ Верно")
    else:
        u["wrong"] += 1
        await message.answer(f"❌ Неверно\nОтвет: {u['correct_answer']}")

    if u["explanation"]:
        await message.answer(f"📘 {u['explanation'][:200]}")

    if u["mode"] == "exam":
        u["exam_count"] += 1
        if u["exam_count"] >= 20:
            percent = int(u["exam_correct"]/20*100)
            status = "✅ СДАЛ" if percent >= 80 else "❌ НЕ СДАЛ"

            await message.answer(
                f"📊 Результат:\n{u['exam_correct']}/20\n{percent}%\n{status}",
                reply_markup=main_kb()
            )
            return

    save_users()
    await send_question(message, u)

# ===== BACK =====
@dp.message_handler(lambda m: m.text == "⬅️ Назад")
async def back(message: types.Message):
    ensure_user(message.from_user.id)
    users[str(message.from_user.id)]["mode"] = None
    save_users()

    await message.answer("🏠 Главное меню", reply_markup=main_kb())

# ===== STATS =====
@dp.message_handler(lambda m: m.text == "📊 Статистика")
async def stats(message: types.Message):
    u = users[str(message.from_user.id)]

    total = u["correct"] + u["wrong"]
    percent = int(u["correct"]/total*100) if total else 0

    await message.answer(
        f"📊 Статистика\n\n"
        f"✅ Правильно: {u['correct']}\n"
        f"❌ Ошибки: {u['wrong']}\n"
        f"📈 Процент: {percent}%"
    )

# ===== RUN =====
if __name__ == "__main__":
    load_users()
    executor.start_polling(dp, skip_updates=True)
