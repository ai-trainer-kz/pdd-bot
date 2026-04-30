import os
import json
import random
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
            "question_id": None,
            "free_limit": 5,
            "used_free": 0,
            "premium_until": None,
            "correct": 0,
            "wrong": 0,
            "waiting_answer": False,
            "waiting_payment": False
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

# ===== SEND QUESTION =====
async def send_question(message, u):

    if not has_access(u):
        await message.answer(
            f"🔒 Доступ ограничен\n\nОплата Kaspi:\n{KASPI}",
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
                f"Правильных: {u['exam_correct']} из {len(u['exam_questions'])}"
            )
            u["mode"] = None
            return

        q = u["exam_questions"][u["exam_index"]]
    else:
        q = random.choice(questions)

    u["question_id"] = q["id"]
    u["correct_answer"] = q["correct"]
    u["waiting_answer"] = True

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

# ===== МЕНЮ =====
@dp.message_handler(lambda m: m.text in ["🧠 Экзамен", "🎯 Тренировка", "📊 Статистика", "⬅️ Назад"])
async def menu(message: types.Message):
    u = users[str(message.from_user.id)]

    if message.text == "⬅️ Назад":
        u["waiting_answer"] = False
        u["mode"] = None
        u["waiting_payment"] = False

        await show_menu(message)
        return

    if message.text == "📊 Статистика":
        total = u["correct"] + u["wrong"]
        percent = int(u["correct"] / total * 100) if total else 0

        await message.answer(
            f"📊 Статистика\n\n"
            f"✅ {u['correct']}\n"
            f"❌ {u['wrong']}\n"
            f"📈 {percent}%"
        )
        return

    if message.text == "🎯 Тренировка":
        u["mode"] = "train"
        await send_question(message, u)
        return

    if message.text == "🧠 Экзамен":
        u["mode"] = "exam"
        u["exam_questions"] = random.sample(questions, min(20, len(questions)))
        u["exam_index"] = 0
        u["exam_correct"] = 0

        await message.answer("🧠 Экзамен начался (20 вопросов)")
        await send_question(message, u)
        return

# ===== ПОКУПКА =====
@dp.message_handler(lambda m: m.text == "💰 Купить доступ")
async def buy(message: types.Message):
    u = users[str(message.from_user.id)]

    await message.answer(
        f"💳 Оплата Kaspi:\n{KASPI}\n\nПосле оплаты нажми:",
        reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("✅ Я оплатил")
    )

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def payment_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("✅ Я оплатил"))
    kb.add(KeyboardButton("⬅️ Назад"))
    return kb

@dp.message_handler(lambda m: m.text == "✅ Я оплатил")
async def paid(message: types.Message):
    user = message.from_user
    u = users[str(user.id)]

    if u.get("waiting_payment"):
        await message.answer("⏳ Ты уже отправил заявку")
        return

    u["waiting_payment"] = True
    save_json(USERS_FILE, users)

    username = f"@{user.username}" if user.username else "нет"

    text = f"""
💰 Новая заявка

👤 Имя: {user.full_name}
📛 Username: {username}
🆔 ID: {user.id}
"""

    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("7 дней", callback_data=f"give_7_{user.id}"),
        InlineKeyboardButton("30 дней", callback_data=f"give_30_{user.id}")
    )
    kb.add(
        InlineKeyboardButton("❌ Отказ", callback_data=f"deny_{user.id}")
    )

    await bot.send_message(ADMIN_ID, text, reply_markup=kb)
    await message.answer("⏳ Ожидай подтверждения")

# ===== АДМИН =====
@dp.callback_query_handler(lambda c: True)
async def admin(callback: types.CallbackQuery):
    data = callback.data

    if "give_7_" in data:
        user_id = data.split("_")[2]
        days = 7

    elif "give_30_" in data:
        user_id = data.split("_")[2]
        days = 30

    elif "deny_" in data:
        user_id = data.split("_")[1]
        users[user_id]["waiting_payment"] = False
        await bot.send_message(user_id, "❌ Отказ")
        return

    u = users[user_id]
    u["premium_until"] = (datetime.now() + timedelta(days=days)).isoformat()
    u["waiting_payment"] = False

    save_json(USERS_FILE, users)

    await bot.send_message(user_id, f"✅ Доступ на {days} дней")
    await callback.answer("OK")

# ===== ОТВЕТ =====
@dp.message_handler()
async def handler(message: types.Message):
    u = users[str(message.from_user.id)]

    # 🔥 1. НАЗАД всегда первый
    if message.text == "⬅️ Назад":
        u["waiting_answer"] = False
        u["waiting_payment"] = False
        u["mode"] = None

        await show_menu(message)
        return

    # 🔥 2. ОПЛАТА
    if message.text == "✅ Я оплатил":
        if u.get("waiting_payment"):
            await send_to_admin(message)
        return

    # 🔥 3. ОТВЕТЫ
    if message.text in ["A", "B", "C", "D"]:
        if not u.get("waiting_answer"):
            return

        # твоя логика ответа
        ...

    u["waiting_answer"] = False

    if message.text == u["correct_answer"]:
        u["correct"] += 1
        if u["mode"] == "exam":
            u["exam_correct"] += 1
        await message.answer("✅ Верно")
    else:
        u["wrong"] += 1
        await message.answer(f"❌ Неверно\nОтвет: {u['correct_answer']}")

    if u["mode"] == "exam":
        u["exam_index"] += 1

    await send_question(message, u)

# ===== RUN =====
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
