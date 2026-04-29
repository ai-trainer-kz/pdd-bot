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

USERS_FILE = "users.json"

# ===== USERS =====
def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_users():
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

users = load_users()
last_questions = {}

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
            "status": None,
            "correct": 0,
            "wrong": 0,
            "exam_count": 0,
            "exam_correct": 0,
            "waiting_answer": False
        }
        save_users()

def has_access(u):
    try:
        if u.get("premium_until"):
            if datetime.now() < datetime.fromisoformat(u["premium_until"]):
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

Ответ строго:

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

# ===== TRAIN =====
@dp.message_handler(lambda m: m.text == "🎯 Тренировка")
async def train(message: types.Message):
    ensure_user(message.from_user.id)
    u = users[str(message.from_user.id)]

    u["mode"] = "train"
    u["waiting_answer"] = False

    if not has_access(u):
        await message.answer("🔒 Нет доступа", reply_markup=main_kb())
        return

    return await send_question(message, u)

# ===== EXAM =====
@dp.message_handler(lambda m: m.text == "🧠 Экзамен")
async def exam(message: types.Message):
    ensure_user(message.from_user.id)
    u = users[str(message.from_user.id)]

    u["mode"] = "exam"
    u["exam_count"] = 0
    u["exam_correct"] = 0
    u["waiting_answer"] = False

    if not has_access(u):
        await message.answer("🔒 Нет доступа", reply_markup=main_kb())
        return

    await message.answer("🧠 Экзамен: 20 вопросов")
    return await send_question(message, u)

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
    ensure_user(message.from_user.id)
    u = users[str(message.from_user.id)]

    u["plan"] = 7 if "7" in message.text else 30
    u["status"] = "pending"
    save_users()

    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("✅ Я оплатил")
    kb.add("⬅️ Назад")

    await message.answer(
        f"💳 Kaspi: {KASPI}\n"
        f"📦 {u['plan']} дней\n\n"
        "После оплаты нажми кнопку",
        reply_markup=kb
    )

# ===== QUESTION =====
async def send_question(message, u):
    if not has_access(u):
        await message.answer("🔒 Нет доступа", reply_markup=main_kb())
        return

    u["waiting_answer"] = True

    if not u.get("premium_until"):
        u["used_free"] += 1

    text, ans, exp = ask_gpt(message.from_user.id)

    if u["mode"] == "exam":
        text += f"\n\n📊 Вопрос {u['exam_count']+1}/20"

    u["correct_answer"] = ans
    u["explanation"] = exp

    await message.answer(text, reply_markup=answer_kb())
    save_users()

# ===== ANSWER =====
@dp.message_handler(lambda m: m.text in ["A","B","C","D"])
async def answer(message: types.Message):
    u = users[str(message.from_user.id)]

    if not u.get("waiting_answer"):
        return

    u["waiting_answer"] = False

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
            await message.answer(f"Результат: {percent}%", reply_markup=main_kb())
            return

    save_users()

    return await send_question(message, u)

# ===== BACK =====
@dp.message_handler(lambda m: m.text == "⬅️ Назад")
async def back(message: types.Message):
    ensure_user(message.from_user.id)
    u = users[str(message.from_user.id)]

    u["mode"] = None
    u["waiting_answer"] = False
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
        f"✅ {u['correct']}\n"
        f"❌ {u['wrong']}\n"
        f"{percent}%"
    )

# ===== RUN =====
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
