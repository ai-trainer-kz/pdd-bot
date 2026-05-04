import os
import json
import random
import asyncio
import sqlite3
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

TOKEN = os.getenv("TOKEN")
ADMIN_ID = 503301815

bot = Bot(token=TOKEN)
dp = Dispatcher()

# ---------------- БАЗА ----------------

conn = sqlite3.connect("db.sqlite3")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    expiry TEXT
)
""")

conn.commit()

# ---------------- СОСТОЯНИЯ ----------------

class Quiz(StatesGroup):
    questions = State()
    index = State()
    score = State()
    free_count = State()
    mistakes = State()
    mode = State()

# ---------------- ВОПРОСЫ ----------------

with open("questions.json", encoding="utf-8") as f:
    ALL_QUESTIONS = json.load(f)

# ---------------- КНОПКИ ----------------

def menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📘 Тренировка", callback_data="train")],
        [InlineKeyboardButton(text="📝 Экзамен", callback_data="exam")]
    ])

def answers():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="A", callback_data="A"),
         InlineKeyboardButton(text="B", callback_data="B")],
        [InlineKeyboardButton(text="C", callback_data="C"),
         InlineKeyboardButton(text="D", callback_data="D")],
        [InlineKeyboardButton(text="📖 Объяснение", callback_data="exp")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back")]
    ])

def pay_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 7 дней — 5000₸", callback_data="buy_7")],
        [InlineKeyboardButton(text="💳 30 дней — 10000₸", callback_data="buy_30")],
        [InlineKeyboardButton(text="✅ Я оплатил", callback_data="paid")]
    ])

# ---------------- ДОСТУП ----------------

def has_access(user_id):
    cursor.execute("SELECT expiry FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()

    if not row or row[0] is None:
        return False

    expiry = datetime.fromisoformat(row[0])
    return datetime.now() < expiry

# ---------------- СТАРТ ----------------

@dp.message(Command("start"))
async def start(message: Message, state: FSMContext):
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
                   (message.from_user.id, message.from_user.username))
    conn.commit()

    await state.clear()
    await message.answer("Выбери режим:", reply_markup=menu())

# ---------------- РЕЖИМ ----------------

async def start_quiz(callback, state, mode):
    questions = random.sample(ALL_QUESTIONS, len(ALL_QUESTIONS))

    await state.set_state(Quiz.questions)
    await state.update_data(
        questions=questions,
        index=0,
        score=0,
        free_count=0,
        mistakes=0,
        mode=mode
    )

    await send_question(callback.message, state)

@dp.callback_query(F.data == "train")
async def train(callback: CallbackQuery, state: FSMContext):
    await start_quiz(callback, state, "train")

@dp.callback_query(F.data == "exam")
async def exam(callback: CallbackQuery, state: FSMContext):
    await start_quiz(callback, state, "exam")

# ---------------- ВОПРОС ----------------

async def send_question(message: Message, state: FSMContext):
    data = await state.get_data()

    if data["free_count"] >= 5 and not has_access(message.chat.id):
        await message.answer(
            "🔒 Бесплатный лимит закончился\nВыбери тариф:",
            reply_markup=pay_kb()
        )
        return

    if data["index"] >= len(data["questions"]):
        await message.answer(f"🎉 Конец! Баллы: {data['score']}")
        await state.clear()
        return

    q = data["questions"][data["index"]]

    await state.update_data(current_q=data["index"])

    text = f"{q['question']}\n\nA) {q['A']}\nB) {q['B']}\nC) {q['C']}\nD) {q['D']}"
    await message.answer(text, reply_markup=answers())

# ---------------- ОТВЕТ ----------------

@dp.callback_query(F.data.in_(["A", "B", "C", "D"]))
async def answer(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    q = data["questions"][data["index"]]

    if callback.data == q["correct"]:
        await callback.message.answer("✅ Верно")
        data["score"] += 1
    else:
        await callback.message.answer("❌ Неверно")
        data["mistakes"] += 1

    if data["mode"] == "exam" and data["mistakes"] >= 3:
        await callback.message.answer("❌ Экзамен провален")
        await state.clear()
        return

    await state.update_data(
        index=data["index"] + 1,
        score=data["score"],
        mistakes=data["mistakes"],
        free_count=data["free_count"] + 1
    )

    await send_question(callback.message, state)

# ---------------- ОБЪЯСНЕНИЕ ----------------

@dp.callback_query(F.data == "exp")
async def explanation(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()

    idx = data.get("current_q")
    if idx is None:
        await callback.message.answer("Нет объяснения")
        return

    q = data["questions"][idx]
    text = q.get("explanation", "Объяснение не добавлено")

    await callback.message.answer(f"📖 {text}")

# ---------------- ПОКУПКА ----------------

@dp.callback_query(F.data.in_(["buy_7", "buy_30"]))
async def buy(callback: CallbackQuery, state: FSMContext):
    await state.update_data(plan=callback.data)

    await callback.message.answer(
        "💳 Оплата\n\nKaspi: 4400430352720152\n\n"
        "После оплаты нажми «Я оплатил»"
    )

# ---------------- Я ОПЛАТИЛ ----------------

def admin_kb(user_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ 7 дней", callback_data=f"approve_7_{user_id}")],
        [InlineKeyboardButton(text="✅ 30 дней", callback_data=f"approve_30_{user_id}")],
        [InlineKeyboardButton(text="❌ Отказать", callback_data=f"decline_{user_id}")]
    ])

@dp.callback_query(F.data == "paid")
async def paid(callback: CallbackQuery, state: FSMContext):
    user = callback.from_user
    data = await state.get_data()

    plan = data.get("plan", "не указан")

    await bot.send_message(
        ADMIN_ID,
        f"💰 Заявка\n@{user.username}\nID: {user.id}\nТариф: {plan}",
        reply_markup=admin_kb(user.id)
    )

    await callback.message.answer("⏳ Ожидай подтверждения")

# ---------------- АДМИН ----------------

@dp.callback_query(F.data.startswith("approve_7_"))
async def approve7(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return

    user_id = int(callback.data.split("_")[2])
    expiry = datetime.now() + timedelta(days=7)

    cursor.execute("UPDATE users SET expiry=? WHERE user_id=?",
                   (expiry.isoformat(), user_id))
    conn.commit()

    await bot.send_message(user_id, "✅ Доступ на 7 дней открыт!")
    await callback.message.answer("✔ Выдано 7 дней")

@dp.callback_query(F.data.startswith("approve_30_"))
async def approve30(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return

    user_id = int(callback.data.split("_")[2])
    expiry = datetime.now() + timedelta(days=30)

    cursor.execute("UPDATE users SET expiry=? WHERE user_id=?",
                   (expiry.isoformat(), user_id))
    conn.commit()

    await bot.send_message(user_id, "✅ Доступ на 30 дней открыт!")
    await callback.message.answer("✔ Выдано 30 дней")

@dp.callback_query(F.data.startswith("decline_"))
async def decline(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return

    user_id = int(callback.data.split("_")[1])

    await bot.send_message(user_id, "❌ Оплата отклонена")
    await callback.message.answer("Отклонено")

# ---------------- НАЗАД ----------------

@dp.callback_query(F.data == "back")
async def back(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("Выбери режим:", reply_markup=menu())

# ---------------- ЗАПУСК ----------------

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
