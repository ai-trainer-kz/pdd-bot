import os
import json
import random
import asyncio
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor

BOT_TOKEN = os.getenv("BOT_TOKEN")

ADMIN_ID = 503301815
KASPI = "4400430352720152"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

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
            "question": None,
            "free_limit": 5,
            "used_free": 0,
            "premium_until": None,
            "correct": 0,
            "wrong": 0,
            "waiting_answer": False,
            "waiting_payment": False,
            "exam_questions": [],
            "exam_index": 0,
            "exam_correct": 0
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
    kb.add("🧠 Экзамен", "🎯 Тренировка")
    kb.add("📊 Статистика")
    return kb

def answer_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("A","B","C","D")
    kb.add("⬅️ Назад")
    return kb

def buy_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("💰 Купить доступ")
    kb.add("⬅️ Назад")
    return kb

def after_pay_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🧠 Экзамен", "🎯 Тренировка")
    kb.add("⬅️ Назад")
    return kb

# ===== GPT (гибрид) =====
async def explain_answer(q, correct):
    # тут потом подключишь OpenAI
    await asyncio.sleep(0.5)
    return f"📘 Объяснение:\nПравильный ответ: {correct}"

# ===== QUESTION =====
async def send_question(message, u):

    if not has_access(u):
        u["waiting_answer"] = False
        await message.answer(
            f"🔒 Доступ ограничен\n\nKaspi:\n{KASPI}",
            reply_markup=buy_kb()
        )
        return

    if not questions:
        await message.answer("Нет вопросов")
        return

    if u["mode"] == "exam":
        if u["exam_index"] >= len(u["exam_questions"]):
            await message.answer(
                f"🏁 Экзамен завершён\n\n"
                f"✅ {u['exam_correct']} из {len(u['exam_questions'])}",
                reply_markup=main_kb()
            )
            u["mode"] = None
            return

        q = u["exam_questions"][u["exam_index"]]
    else:
        q = random.choice(questions)

    u["question"] = q
    u["correct_answer"] = q["correct"]
    u["waiting_answer"] = True

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
    await message.answer("🚗 Подготовка к ПДД\n\nВыбери режим:", reply_markup=main_kb())

# ===== MENU =====
@dp.message_handler(lambda m: m.text in ["🧠 Экзамен", "🎯 Тренировка", "📊 Статистика", "⬅️ Назад"])
async def menu(message: types.Message):
    u = users[str(message.from_user.id)]

    if message.text == "⬅️ Назад":
        u["mode"] = None
        u["waiting_answer"] = False
        u["waiting_payment"] = False
        await message.answer("Главное меню", reply_markup=main_kb())
        return

    if message.text == "📊 Статистика":
        total = u["correct"] + u["wrong"]
        percent = int(u["correct"] / total * 100) if total else 0
        await message.answer(f"📊\n✅ {u['correct']}\n❌ {u['wrong']}\n📈 {percent}%")
        return

    if message.text == "🎯 Тренировка":
        u["mode"] = "train"
        await send_question(message, u)

    if message.text == "🧠 Экзамен":
        u["mode"] = "exam"
        u["exam_questions"] = random.sample(questions, min(20, len(questions)))
        u["exam_index"] = 0
        u["exam_correct"] = 0
        await message.answer("🧠 Экзамен начался (20 вопросов)")
        await send_question(message, u)

# ===== BUY =====
@dp.message_handler(lambda m: m.text == "💰 Купить доступ")
async def buy(message: types.Message):
    await message.answer(
        f"Kaspi: {KASPI}\n\nПосле оплаты нажми:",
        reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("✅ Я оплатил", "⬅️ Назад")
    )

# ===== PAID =====
@dp.message_handler(lambda m: m.text == "✅ Я оплатил")
async def paid(message: types.Message):
    user = message.from_user
    u = users[str(user.id)]

    if u["waiting_payment"]:
        await message.answer("⏳ Уже отправлено")
        return

    u["waiting_payment"] = True
    save_json(USERS_FILE, users)

    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("7 дней", callback_data=f"give_7_{user.id}"),
        InlineKeyboardButton("30 дней", callback_data=f"give_30_{user.id}")
    )
    kb.add(InlineKeyboardButton("❌ Отказ", callback_data=f"deny_{user.id}"))

    await bot.send_message(ADMIN_ID, f"💰 {user.full_name} @{user.username} {user.id}", reply_markup=kb)
    await message.answer("⏳ Ожидай", reply_markup=main_kb())

# ===== ADMIN =====
@dp.callback_query_handler(lambda c: True)
async def admin(callback: types.CallbackQuery):
    await callback.answer()

    data = callback.data

    if "deny_" in data:
        uid = data.split("_")[1]
        users[uid]["waiting_payment"] = False
        await bot.send_message(uid, "❌ Отказ")
        return

    uid = data.split("_")[2]
    days = 7 if "give_7_" in data else 30

    users[uid]["premium_until"] = (datetime.now() + timedelta(days=days)).isoformat()
    users[uid]["waiting_payment"] = False

    save_json(USERS_FILE, users)

    await bot.send_message(uid, f"✅ Доступ на {days} дней", reply_markup=after_pay_kb())

# ===== ANSWER =====
@dp.message_handler(lambda m: m.text in ["A","B","C","D"])
async def answer(message: types.Message):
    u = users[str(message.from_user.id)]

    if not u["waiting_answer"]:
        return

    correct = u["correct_answer"]

    if message.text == correct:
        u["correct"] += 1
        if u["mode"] == "exam":
            u["exam_correct"] += 1
        text = "✅ Верно"
    else:
        u["wrong"] += 1
        text = f"❌ Неверно\nОтвет: {correct}"

    await message.answer(text)

    # GPT объяснение (не тормозит UI)
    asyncio.create_task(send_explanation(message, u))

    if u["mode"] == "exam":
        u["exam_index"] += 1

    u["waiting_answer"] = False
    save_json(USERS_FILE, users)

    await asyncio.sleep(0.3)
    await send_question(message, u)

# ===== EXPLAIN =====
async def send_explanation(message, u):
    q = u["question"]
    text = await explain_answer(q["question"], q["correct"])
    await message.answer(text)

# ===== RUN =====
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
