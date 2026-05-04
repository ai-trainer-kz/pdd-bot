import os
import json
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
    access_until INTEGER DEFAULT 0
)
""")

conn.commit()

# ---------------- СОСТОЯНИЯ ----------------

class Quiz(StatesGroup):
    data = State()

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

# ---------------- УТИЛИТА ----------------

def has_access(user_id):
    cursor.execute("SELECT access_until FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    if not row:
        return False
    return row[0] > int(time.time())

# ---------------- СТАРТ ----------------

@dp.message(Command("start"))
async def start(message: Message, state: FSMContext):
    cursor.execute("INSERT OR IGNORE INTO users VALUES (?, ?, 0)",
                   (message.from_user.id, message.from_user.username))
    conn.commit()

    await state.clear()
    await message.answer("Выбери режим:", reply_markup=menu())

# ---------------- ЗАПУСК ----------------

async def start_quiz(callback, state, mode):
    if mode == "exam":
        questions = random.sample(ALL_QUESTIONS, 20)
    else:
        questions = random.sample(ALL_QUESTIONS, len(ALL_QUESTIONS))

    await state.update_data(
        questions=questions,
        index=0,
        score=0,
        mistakes=0,
        free_count=0,
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
    await callback.message.answer(f"📖 {q.get('explanation', 'Нет объяснения')}")

# ---------------- ПОКУПКА ----------------

@dp.callback_query(F.data.startswith("buy_"))
async def buy(callback: CallbackQuery, state: FSMContext):
    plan = callback.data.split("_")[1]
    await state.update_data(plan=plan)

    await callback.message.answer(
        "💳 Kaspi: 4400430352720152\nПосле оплаты нажми 'Я оплатил'",
        reply_markup=pay_kb()
    )

# ---------------- Я ОПЛАТИЛ ----------------

@dp.callback_query(F.data == "paid")
async def paid(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    plan = data.get("plan")

    if not plan:
        await callback.message.answer("Сначала выбери тариф")
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"approve_{callback.from_user.id}_{plan}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{callback.from_user.id}")
        ]
    ])

    await bot.send_message(
        ADMIN_ID,
        f"💰 Оплата\nID: {callback.from_user.id}\nТариф: {plan}",
        reply_markup=kb
    )

    await callback.message.answer("⏳ Ожидай подтверждения")

# ---------------- ПОДТВЕРЖДЕНИЕ ----------------

@dp.callback_query(F.data.startswith("approve_"))
async def approve(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return

    _, user_id, plan = callback.data.split("_")
    user_id = int(user_id)

    days = 7 if plan == "7" else 30
    access_until = int(time.time()) + days * 86400

    cursor.execute("UPDATE users SET access_until=? WHERE user_id=?",
                   (access_until, user_id))
    conn.commit()

    await bot.send_message(user_id, f"✅ Доступ на {days} дней открыт")
    await callback.message.edit_text("Подтверждено")

# ---------------- СТАТИСТИКА ----------------

@dp.message(Command("admin"))
async def admin(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    cursor.execute("SELECT COUNT(*) FROM users")
    users = cursor.fetchone()[0]

    now = int(time.time())
    cursor.execute("SELECT COUNT(*) FROM users WHERE access_until > ?", (now,))
    active = cursor.fetchone()[0]

    await message.answer(
        f"👥 Всего: {users}\n"
        f"💰 С доступом: {active}"
    )

# ---------------- НАЗАД ----------------

@dp.callback_query(F.data == "back")
async def back(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("Выбери режим:", reply_markup=menu())

# ---------------- ЗАПУСК ----------------

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    print("BOT STARTED")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
