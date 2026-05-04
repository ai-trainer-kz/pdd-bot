import os
import json
import random
import asyncio
import os
import json
import sqlite3

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
    paid INTEGER DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    status TEXT
)
""")

conn.commit()

# ---------------- СОСТОЯНИЯ ----------------

class Quiz(StatesGroup):
    question_index = State()
    score = State()
    free_count = State()

# ---------------- ВОПРОСЫ ----------------

with open("questions.json", encoding="utf-8") as f:
    questions = json.load(f)

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
        [InlineKeyboardButton(text="💳 Купить доступ", callback_data="buy")],
        [InlineKeyboardButton(text="✅ Я оплатил", callback_data="paid")]
    ])

# ---------------- СТАРТ ----------------

@dp.message(Command("start"))
async def start(message: Message, state: FSMContext):
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
                   (message.from_user.id, message.from_user.username))
    conn.commit()

    await state.clear()
    await message.answer("Выбери режим:", reply_markup=menu())

# ---------------- ВОПРОС ----------------

async def send_question(message: Message, state: FSMContext):
    data = await state.get_data()

    cursor.execute("SELECT paid FROM users WHERE user_id=?", (message.chat.id,))
    paid = cursor.fetchone()[0]

    if data.get("free_count", 0) >= 5 and not paid:
        await message.answer(
            "🔒 Лимит закончился\n\nKaspi: 4400430352720152",
            reply_markup=pay_kb()
        )
        return

    index = data.get("question_index", 0)

    if index >= len(questions):
        await message.answer(f"🎉 Конец! Баллы: {data.get('score', 0)}")
        await state.clear()
        return

    q = questions[index]

    text = f"{q['question']}\n\nA) {q['A']}\nB) {q['B']}\nC) {q['C']}\nD) {q['D']}"
    await message.answer(text, reply_markup=answers())

# ---------------- РЕЖИМ ----------------

@dp.callback_query(F.data == "train")
async def train(callback: CallbackQuery, state: FSMContext):
    await state.set_state(Quiz.question_index)
    await state.update_data(question_index=0, score=0, free_count=0)
    await send_question(callback.message, state)

# ---------------- ОТВЕТ ----------------

@dp.callback_query(F.data.in_(["A", "B", "C", "D"]))
async def answer(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    index = data["question_index"]
    q = questions[index]

    if callback.data == q["correct"]:
        await callback.message.answer("✅ Верно")
        data["score"] += 1
    else:
        await callback.message.answer("❌ Неверно")

    await state.update_data(
        question_index=index + 1,
        score=data["score"],
        free_count=data["free_count"] + 1
    )

    await send_question(callback.message, state)

# ---------------- ОБЪЯСНЕНИЕ ----------------

@dp.callback_query(F.data == "exp")
async def exp(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    index = data["question_index"]
    q = questions[index]
    await callback.message.answer(q.get("explanation", "Нет объяснения"))

# ---------------- ОПЛАТА ----------------

@dp.callback_query(F.data == "paid")
async def paid(callback: CallbackQuery):
    user = callback.from_user

    cursor.execute("INSERT INTO payments (user_id, status) VALUES (?, ?)", (user.id, "pending"))
    conn.commit()

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"approve_{user.id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{user.id}")
        ]
    ])

    await bot.send_message(
        ADMIN_ID,
        f"💰 Заявка на оплату\n\n👤 @{user.username}\n🆔 {user.id}",
        reply_markup=kb
    )

    await callback.message.answer("⏳ Заявка отправлена администратору")

# ---------------- ПОДТВЕРЖДЕНИЕ ----------------

@dp.callback_query(F.data.startswith("approve_"))
async def approve(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return

    user_id = int(callback.data.split("_")[1])

    cursor.execute("UPDATE users SET paid=1 WHERE user_id=?", (user_id,))
    conn.commit()

    await bot.send_message(user_id, "✅ Оплата подтверждена! Доступ открыт")

    await callback.message.edit_text("✅ Подтверждено")

# ---------------- ОТКЛОНЕНИЕ ----------------

@dp.callback_query(F.data.startswith("reject_"))
async def reject(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return

    user_id = int(callback.data.split("_")[1])

    await bot.send_message(user_id, "❌ Оплата не найдена")

    await callback.message.edit_text("❌ Отклонено")

# ---------------- АДМИН СТАТА ----------------

@dp.message(Command("admin"))
async def admin(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    cursor.execute("SELECT COUNT(*) FROM users")
    users = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM users WHERE paid=1")
    paid = cursor.fetchone()[0]

    await message.answer(
        f"👥 Пользователей: {users}\n💰 Оплатили: {paid}"
    )

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
