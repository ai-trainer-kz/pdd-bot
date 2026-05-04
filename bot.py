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

cursor.execute("""
CREATE TABLE IF NOT EXISTS payments (
    user_id INTEGER,
    plan TEXT,
    status TEXT
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
        "explanation": "По ПДД ближний свет должен быть включен всегда."
    },
    {
        "q": "Максимальная скорость в городе?",
        "options": ["40", "60", "80", "100"],
        "correct": 1,
        "explanation": "В большинстве случаев — 60 км/ч."
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

# ---------------- КНОПКИ ----------------

def menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📘 Тренировка", callback_data="training")],
        [InlineKeyboardButton(text="📝 Экзамен", callback_data="exam")]
    ])

def answers_kb(mode):
    buttons = [
        [InlineKeyboardButton(text="A", callback_data="ans_0"),
         InlineKeyboardButton(text="B", callback_data="ans_1")],
        [InlineKeyboardButton(text="C", callback_data="ans_2"),
         InlineKeyboardButton(text="D", callback_data="ans_3")]
    ]

    if mode == "training":
        buttons.append([InlineKeyboardButton(text="📖 Объяснение", callback_data="explain")])

    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

def pay_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 7 дней — 5000₸", callback_data="buy_7")],
        [InlineKeyboardButton(text="💳 30 дней — 10000₸", callback_data="buy_30")],
        [InlineKeyboardButton(text="✅ Я оплатил", callback_data="paid")]
    ])

def end_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 В меню", callback_data="menu")]
    ])

# ---------------- СТАРТ ----------------

@dp.message(Command("start"))
async def start(message: Message, state: FSMContext):
    cursor.execute("INSERT OR IGNORE INTO users VALUES (?, ?, 0)",
                   (message.from_user.id, message.from_user.username))
    conn.commit()

    await state.clear()
    await message.answer("Выбери режим:", reply_markup=menu_kb())

# ---------------- РЕЖИМ ----------------

@dp.callback_query(F.data == "training")
async def training(callback: CallbackQuery, state: FSMContext):
    await state.set_state(QuizState.data)
    await state.update_data(
        question_index=0,
        score=0,
        mistakes=0,
        mode="training",
        free_count=0
    )
    await send_question(callback.message, state)

@dp.callback_query(F.data == "exam")
async def exam(callback: CallbackQuery, state: FSMContext):
    if not has_access(callback.from_user.id):
        await callback.message.answer("🔒 Доступ только после оплаты", reply_markup=pay_kb())
        return

    await state.set_state(QuizState.data)
    await state.update_data(
        question_index=0,
        score=0,
        mistakes=0,
        mode="exam",
        free_count=0
    )
    await send_question(callback.message, state)

# ---------------- ВОПРОС ----------------

async def send_question(message: Message, state: FSMContext):
    data = await state.get_data()
    index = data["question_index"]

    if data["mode"] == "training":
        if data["free_count"] >= 5 and not has_access(message.chat.id):
            await message.answer("🔒 Бесплатный лимит закончился", reply_markup=pay_kb())
            return

    if index >= len(questions):
        await message.answer(
            f"🎉 Конец!\nБаллы: {data['score']}",
            reply_markup=end_kb()
        )
        await state.clear()
        return

    q = questions[index]

    text = f"{q['q']}\n\n"
    for i, opt in enumerate(q["options"]):
        text += f"{chr(65+i)}) {opt}\n"

    await message.answer(text, reply_markup=answers_kb(data["mode"]))

# ---------------- ОТВЕТ ----------------

@dp.callback_query(F.data.startswith("ans_"))
async def answer(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    index = data["question_index"]
    q = questions[index]

    await state.update_data(last_q=index)

    user_answer = int(callback.data.split("_")[1])

    if user_answer == q["correct"]:
        await callback.message.answer("✅ Верно")
        data["score"] += 1
    else:
        await callback.message.answer("❌ Неверно")
        data["mistakes"] += 1

    if data["mode"] == "exam" and data["mistakes"] >= 3:
        await callback.message.answer("❌ Экзамен провален", reply_markup=end_kb())
        await state.clear()
        return

    await state.update_data(
        question_index=index + 1,
        score=data["score"],
        mistakes=data["mistakes"],
        free_count=data["free_count"] + 1
    )

    await send_question(callback.message, state)

# ---------------- ОБЪЯСНЕНИЕ ----------------

@dp.callback_query(F.data == "explain")
async def explain(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()

    if data.get("mode") == "exam":
        await callback.answer("❌ В экзамене нельзя")
        return

    index = data.get("last_q")

    if index is None:
        await callback.message.answer("Нет объяснения")
        return

    await callback.message.answer(f"📖 {questions[index]['explanation']}")

# ---------------- ПОКУПКА ----------------

@dp.callback_query(F.data.startswith("buy_"))
async def buy(callback: CallbackQuery, state: FSMContext):
    plan = callback.data.split("_")[1]

    await state.update_data(plan=plan)

    await callback.message.answer(
        "💳 Kaspi: 4400430352720152\nПосле оплаты нажми 'Я оплатил'"
    )

# ---------------- Я ОПЛАТИЛ ----------------

@dp.callback_query(F.data == "paid")
async def paid(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    plan = data.get("plan")

    if not plan:
        await callback.message.answer("Сначала выбери тариф")
        return

    cursor.execute(
        "INSERT INTO payments (user_id, plan, status) VALUES (?, ?, ?)",
        (callback.from_user.id, plan, "pending")
    )
    conn.commit()

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"approve_{callback.from_user.id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{callback.from_user.id}")
        ]
    ])

    await bot.send_message(
        ADMIN_ID,
        f"💰 Оплата\nID: {callback.from_user.id}\nТариф: {plan}",
        reply_markup=kb
    )

    await callback.message.answer("⏳ Ожидай подтверждения")

# ---------------- АДМИН ----------------

@dp.callback_query(F.data.startswith("approve_"))
async def approve(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return

    user_id = int(callback.data.split("_")[1])

    cursor.execute(
        "SELECT plan FROM payments WHERE user_id=? AND status='pending' ORDER BY rowid DESC LIMIT 1",
        (user_id,)
    )
    row = cursor.fetchone()

    if not row:
        await callback.message.answer("Нет заявки")
        return

    plan = row[0]
    days = 7 if plan == "7" else 30

    access_until = int(time.time()) + days * 86400

    cursor.execute("UPDATE users SET access_until=? WHERE user_id=?",
                   (access_until, user_id))

    cursor.execute("UPDATE payments SET status='done' WHERE user_id=? AND status='pending'",
                   (user_id,))

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

    await message.answer(f"👥 Всего: {users}\n💰 Активных: {active}")

# ---------------- МЕНЮ ----------------

@dp.callback_query(F.data == "menu")
async def menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("Выбери режим:", reply_markup=menu_kb())

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
