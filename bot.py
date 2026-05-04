import os
import random
import asyncio
import sqlite3
import time

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

TOKEN = os.getenv("TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()

# ---------------- БАЗА ----------------

conn = sqlite3.connect("db.sqlite3")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    access_until INTEGER DEFAULT 0,
    free_until INTEGER DEFAULT 0,
    last_answer INTEGER DEFAULT 0
)
""")

conn.commit()

# ---------------- ВОПРОСЫ ----------------

questions = [
    {
        "q": "Какой сигнал светофора разрешает движение?",
        "options": ["Красный", "Желтый", "Зеленый", "Мигающий красный"],
        "correct": 2,
        "explanation": "Зеленый сигнал разрешает движение."
    },
    {
        "q": "Когда включается ближний свет?",
        "options": ["Только ночью", "Всегда при движении", "Только в городе", "По желанию"],
        "correct": 1,
        "explanation": "Ближний свет должен быть включен всегда."
    },
    {
        "q": "Максимальная скорость в городе?",
        "options": ["40", "60", "80", "100"],
        "correct": 1,
        "explanation": "Обычно 60 км/ч."
    }
]

# ---------------- СОСТОЯНИЕ ----------------

class QuizState(StatesGroup):
    data = State()

# ---------------- УТИЛИТЫ ----------------

def has_access(user_id):
    cursor.execute("SELECT access_until FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    return row and row[0] > int(time.time())

def has_free(user_id):
    cursor.execute("SELECT free_until FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    return row and row[0] > int(time.time())

# ---------------- КНОПКИ ----------------

def menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📘 Тренировка", callback_data="training")],
        [InlineKeyboardButton(text="📝 Экзамен", callback_data="exam")]
    ])

def answers_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="A", callback_data="ans_0"),
         InlineKeyboardButton(text="B", callback_data="ans_1")],
        [InlineKeyboardButton(text="C", callback_data="ans_2"),
         InlineKeyboardButton(text="D", callback_data="ans_3")],
        [InlineKeyboardButton(text="📖 Объяснение", callback_data="explain")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back")]
    ])

def pay_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔥 7 дней — 5000₸", callback_data="buy_7")],
        [InlineKeyboardButton(text="💎 30 дней — 10000₸", callback_data="buy_30")],
        [InlineKeyboardButton(text="✅ Я оплатил", callback_data="paid")]
    ])

# ---------------- СТАРТ ----------------

@dp.message(Command("start"))
async def start(message: Message, state: FSMContext):
    now = int(time.time())

    # 1 день бесплатно
    free_until = now + 86400

    cursor.execute("""
    INSERT OR REPLACE INTO users (user_id, username, free_until)
    VALUES (?, ?, ?)
    """, (message.from_user.id, message.from_user.username, free_until))

    conn.commit()

    await state.clear()
    await message.answer(
        "👋 Добро пожаловать!\n\n🎁 Тебе доступен 1 день бесплатно!\n\nВыбери режим:",
        reply_markup=menu_kb()
    )

# ---------------- РЕЖИМ ----------------

@dp.callback_query(F.data == "training")
async def training(callback: CallbackQuery, state: FSMContext):
    await state.set_state(QuizState.data)
    await state.update_data(question_index=0, score=0, mistakes=0, mode="training")
    await send_question(callback.message, state)

@dp.callback_query(F.data == "exam")
async def exam(callback: CallbackQuery, state: FSMContext):

    if not has_access(callback.from_user.id):
        await callback.message.answer(
            "🔒 Экзамен доступен только после оплаты",
            reply_markup=pay_kb()
        )
        return

    await state.set_state(QuizState.data)
    await state.update_data(question_index=0, score=0, mistakes=0, mode="exam")
    await send_question(callback.message, state)

# ---------------- ВОПРОС ----------------

async def send_question(message: Message, state: FSMContext):
    data = await state.get_data()
    index = data["question_index"]

    # доступ
    if not has_access(message.chat.id) and not has_free(message.chat.id):
        await message.answer("🔒 Доступ закончился", reply_markup=pay_kb())
        await state.clear()
        return

    if index >= len(questions):
        await message.answer(f"🎉 Конец! Баллы: {data['score']}")
        await state.clear()
        return

    q = questions[index]

    text = f"{q['q']}\n\n"
    for i, opt in enumerate(q["options"]):
        text += f"{chr(65+i)}) {opt}\n"

    await message.answer(text, reply_markup=answers_kb())

# ---------------- ОТВЕТ ----------------

@dp.callback_query(F.data.startswith("ans_"))
async def answer(callback: CallbackQuery, state: FSMContext):

    # анти-накрутка (1 секунда)
    now = int(time.time())

    cursor.execute("SELECT last_answer FROM users WHERE user_id=?", (callback.from_user.id,))
    last = cursor.fetchone()[0]

    if now - last < 1:
        await callback.answer("⏳ Подожди секунду")
        return

    cursor.execute("UPDATE users SET last_answer=? WHERE user_id=?",
                   (now, callback.from_user.id))
    conn.commit()

    data = await state.get_data()
    index = data["question_index"]
    q = questions[index]

    user_answer = int(callback.data.split("_")[1])

    if user_answer == q["correct"]:
        await callback.message.answer("✅ Верно")
        data["score"] += 1
    else:
        await callback.message.answer("❌ Неверно")
        data["mistakes"] += 1

    # экзамен провален
    if data["mode"] == "exam" and data["mistakes"] >= 3:
        await callback.message.answer("❌ Экзамен провален")
        await state.clear()
        return

    await state.update_data(
        question_index=index + 1,
        score=data["score"],
        mistakes=data["mistakes"]
    )

    await send_question(callback.message, state)

# ---------------- ОБЪЯСНЕНИЕ ----------------

@dp.callback_query(F.data == "explain")
async def explain(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    index = data["question_index"]

    if index < len(questions):
        await callback.message.answer(f"📖 {questions[index]['explanation']}")

# ---------------- ПОКУПКА ----------------

@dp.callback_query(F.data.startswith("buy_"))
async def buy(callback: CallbackQuery, state: FSMContext):
    plan = callback.data.split("_")[1]
    await state.update_data(plan=plan)

    await callback.message.answer(
        "💳 Оплата через Kaspi\n\n"
        "Номер: 4400430352720152\n\n"
        "После оплаты нажми кнопку ниже 👇",
        reply_markup=pay_kb()
    )

# ---------------- АВТО ОПЛАТА ----------------

@dp.callback_query(F.data == "paid")
async def paid(callback: CallbackQuery, state: FSMContext):

    data = await state.get_data()
    plan = data.get("plan")

    if not plan:
        await callback.message.answer("Сначала выбери тариф")
        return

    days = 7 if plan == "7" else 30
    access_until = int(time.time()) + days * 86400

    cursor.execute("UPDATE users SET access_until=? WHERE user_id=?",
                   (access_until, callback.from_user.id))
    conn.commit()

    await callback.message.answer(f"✅ Доступ на {days} дней открыт!")

# ---------------- НАЗАД ----------------

@dp.callback_query(F.data == "back")
async def back(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("Выбери режим:", reply_markup=menu_kb())

# ---------------- ЗАПУСК ----------------

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    print("BOT STARTED")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
