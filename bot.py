import os
import json
import random
import asyncio
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
        [InlineKeyboardButton(text="💳 Купить доступ", callback_data="buy")],
        [InlineKeyboardButton(text="✅ Я оплатил", callback_data="paid")]
    ])

# ---------------- СТАРТ ----------------

@dp.message(Command("start"))
async def start(message: Message, state: FSMContext):
    cursor.execute("INSERT OR IGNORE INTO users VALUES (?, ?, 0)",
                   (message.from_user.id, message.from_user.username))
    conn.commit()

    await state.clear()
    await message.answer("Выбери режим:", reply_markup=menu())

# ---------------- ЗАПУСК РЕЖИМА ----------------

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

    cursor.execute("SELECT paid FROM users WHERE user_id=?", (message.chat.id,))
    paid = cursor.fetchone()[0]

    if data["free_count"] >= 5 and not paid:
        await message.answer("🔒 Лимит закончился", reply_markup=pay_kb())
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

    # ❗ экзамен провал
    if data["mode"] == "exam" and data["mistakes"] >= 3:
        await callback.message.answer("❌ Экзамен провален (3 ошибки)")
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

# ---------------- ОПЛАТА ----------------

@dp.callback_query(F.data == "paid")
async def paid(callback: CallbackQuery):
    user = callback.from_user

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"approve_{user.id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{user.id}")
        ]
    ])

    await bot.send_message(
        ADMIN_ID,
        f"💰 Оплата от @{user.username}\nID: {user.id}",
        reply_markup=kb
    )

    await callback.message.answer("⏳ Ожидай подтверждения")

# ---------------- АДМИН ----------------

@dp.callback_query(F.data.startswith("approve_"))
async def approve(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return

    user_id = int(callback.data.split("_")[1])

    cursor.execute("UPDATE users SET paid=1 WHERE user_id=?", (user_id,))
    conn.commit()

    await bot.send_message(user_id, "✅ Доступ открыт!")
    await callback.message.edit_text("Подтверждено")

@dp.callback_query(F.data.startswith("reject_"))
async def reject(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return

    user_id = int(callback.data.split("_")[1])

    await bot.send_message(user_id, "❌ Оплата отклонена")
    await callback.message.edit_text("Отклонено")

@dp.message(Command("admin"))
async def admin(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    cursor.execute("SELECT COUNT(*) FROM users")
    users = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM users WHERE paid=1")
    paid = cursor.fetchone()[0]

    await message.answer(f"👥 Пользователи: {users}\n💰 Платные: {paid}")

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
