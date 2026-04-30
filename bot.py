import os
import json
import random
import asyncio
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup
from aiogram.utils import executor
from openai import OpenAI

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
client = OpenAI(api_key=OPENAI_API_KEY)

USERS_FILE = "users.json"
QUESTIONS_FILE = "questions.json"

# ===== LOAD =====
def load_json(file, default):
    if os.path.exists(file):
        with open(file, "r", encoding="utf-8") as f:
            return json.load(f)
    return default

def save_json(file, data):
    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

users = load_json(USERS_FILE, {})
questions = load_json(QUESTIONS_FILE, [])

# ===== USER =====
def ensure_user(uid):
    uid = str(uid)
    if uid not in users:
        users[uid] = {
            "mode": None,
            "correct_answer": None,
            "question_id": None,
            "free_limit": 5,
            "used_free": 0,
            "premium_until": None,
            "correct": 0,
            "wrong": 0,
            "waiting_answer": False
        }
        save_json(USERS_FILE, users)

def has_access(u):
    if u.get("premium_until"):
        if datetime.now() < datetime.fromisoformat(u["premium_until"]):
            return True
    return u["used_free"] < u["free_limit"]

# ===== UI =====
def main_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🎯 Тренировка", "📊 Статистика")
    return kb

def answer_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("A","B","C","D")
    return kb

# ===== GPT EXPLANATION =====
async def explain(question, correct):
    prompt = f"""
Объясни кратко вопрос ПДД.

Вопрос: {question}
Правильный ответ: {correct}

Коротко и понятно.
"""

    try:
        res = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5
        )
        return res.choices[0].message.content
    except:
        return "Ошибка объяснения"

# ===== SEND QUESTION =====
async def send_question(message, u):
    q = random.choice(questions)

    u["question_id"] = q["id"]
    u["correct_answer"] = q["correct"]
    u["waiting_answer"] = True

    if not has_access(u):
        await message.answer("🔒 Купи доступ")
        return

    u["used_free"] += 1
    save_json(USERS_FILE, users)

    text = f"""
{q['question']}

A) {q['A']}
B) {q['B']}
C) {q['C']}
D) {q['D']}
"""

    await message.answer(text, reply_markup=answer_kb())

# ===== START =====
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    ensure_user(message.from_user.id)

    await message.answer(
        "🚗 Подготовка к ПДД\n\nВыбери режим:",
        reply_markup=main_kb()
    )

# ===== TRAIN =====
@dp.message_handler(lambda m: m.text == "🎯 Тренировка")
async def train(message: types.Message):
    u = users[str(message.from_user.id)]
    u["mode"] = "train"

    await send_question(message, u)

# ===== ANSWER =====
@dp.message_handler(lambda m: m.text in ["A","B","C","D"])
async def answer(message: types.Message):
    u = users[str(message.from_user.id)]

    if not u["waiting_answer"]:
        return

    u["waiting_answer"] = False

    user_answer = message.text
    correct = u["correct_answer"]

    if user_answer == correct:
        u["correct"] += 1
        await message.answer("✅ Верно")
    else:
        u["wrong"] += 1
        await message.answer(f"❌ Неверно\nОтвет: {correct}")

    # берем вопрос
    q = next(x for x in questions if x["id"] == u["question_id"])

    explanation = await explain(q["question"], correct)
    await message.answer(f"📘 {explanation}")

    save_json(USERS_FILE, users)

    await asyncio.sleep(0.5)
    await send_question(message, u)

# ===== STATS =====
@dp.message_handler(lambda m: m.text == "📊 Статистика")
async def stats(message: types.Message):
    u = users[str(message.from_user.id)]
    total = u["correct"] + u["wrong"]
    percent = int(u["correct"]/total*100) if total else 0

    await message.answer(
        f"📊\nПравильно: {u['correct']}\nОшибки: {u['wrong']}\n{percent}%"
    )

# ===== RUN =====
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
