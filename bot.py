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
    access_until INTEGER DEFAULT 0,
    exams_passed INTEGER DEFAULT 0,
    exams_failed INTEGER DEFAULT 0
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
        "q": "Максимальная скорость в городе?",
        "options": ["40", "60", "80", "100"],
        "correct": 1,
        "explanation": "60 км/ч"
    },
    {
        "q": "Кто имеет преимущество на перекрестке?",
        "options": ["Кто быстрее", "По договоренности", "По ПДД", "Кто сигналит"],
        "correct": 2,
        "explanation": "По знакам и ПДД"
    }
]

# ---------------- STATE ----------------

class QuizState(StatesGroup):
    data = State()

# ---------------- UTILS ----------------

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
        [InlineKeyboardButton(text="💳 7 дней", callback_data="buy_7")],
        [InlineKeyboardButton(text="💳 30 дней", callback_data="buy_30")]
    ])

def result_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔁 Пройти ещё раз", callback_data="restart")],
        [InlineKeyboardButton(text="⬅️ В меню", callback_data="back")]
    ])

# ---------------- START ----------------

@dp.message(Command("start"))
async def start(message: Message, state: FSMContext):
    cursor.execute("INSERT OR IGNORE INTO users VALUES (?, ?, 0, 0, 0)",
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
        await callback.message.answer("🔒 Нужна оплата", reply_markup=pay_kb())
        return

    exam_qs = random.sample(questions, min(20, len(questions)))

    await state.set_state(QuizState.data)
    await state.update_data(
        question_index=0,
        score=0,
        mistakes=0,
        mode="exam",
        exam_qs=exam_qs
    )

    await send_question(callback.message, state)

# ---------------- ВОПРОС ----------------

async def send_question(message: Message, state: FSMContext):
    data = await state.get_data()
    index = data["question_index"]

    # лимит
    if data["mode"] == "training":
        if data["free_count"] >= 5 and not has_access(message.chat.id):
            await message.answer("🔒 Лимит закончился", reply_markup=pay_kb())
            await state.clear()
            return

    qs = data.get("exam_qs") if data["mode"] == "exam" else questions

    if index >= len(qs):

        if data["mode"] == "training":
            text = f"🎉 Конец! Баллы: {data['score']}"
            await message.answer(text, reply_markup=result_kb())

        else:
            if data["mistakes"] < 3:
                cursor.execute("UPDATE users SET exams_passed = exams_passed + 1 WHERE user_id=?", (message.chat.id,))
                text = f"🎉 Экзамен СДАН\nБаллы: {data['score']}"
            else:
                cursor.execute("UPDATE users SET exams_failed = exams_failed + 1 WHERE user_id=?", (message.chat.id,))
                text = "❌ Экзамен НЕ сдан"

            conn.commit()
            await message.answer(text, reply_markup=result_kb())

        await state.clear()
        return

    q = qs[index]

    text = f"{q['q']}\n\n"
    for i, opt in enumerate(q["options"]):
        text += f"{chr(65+i)}) {opt}\n"

    await message.answer(text, reply_markup=answers_kb())

# ---------------- ОТВЕТ ----------------

@dp.callback_query(F.data.startswith("ans_"))
async def answer(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    index = data["question_index"]

    qs = data.get("exam_qs") if data["mode"] == "exam" else questions
    q = qs[index]

    user_answer = int(callback.data.split("_")[1])

    if user_answer == q["correct"]:
        await callback.message.answer("✅ Верно")
        data["score"] += 1
    else:
        await callback.message.answer("❌ Неверно")
        data["mistakes"] += 1

    if data["mode"] == "exam" and data["mistakes"] >= 3:
        cursor.execute("UPDATE users SET exams_failed = exams_failed + 1 WHERE user_id=?", (callback.from_user.id,))
        conn.commit()
        await callback.message.answer("❌ Экзамен провален", reply_markup=result_kb())
        await state.clear()
        return

    await state.update_data(
        question_index=index + 1,
        score=data["score"],
        mistakes=data["mistakes"],
        free_count=data.get("free_count", 0) + 1
    )

    await send_question(callback.message, state)

# ---------------- ОБЪЯСНЕНИЕ ----------------
@dp.callback_query(F.data == "explain")
async def explain(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    index = data["question_index"] - 1

    qs = data.get("exam_qs", []) if data["mode"] == "exam" else questions

    if 0 <= index < len(qs):
        await callback.message.answer(f"📖 {qs[index]['explanation']}")

# ---------------- ПОКУПКА (АВТО) ----------------

@dp.callback_query(F.data.startswith("buy_"))
async def buy(callback: CallbackQuery, state: FSMContext):
    plan = callback.data.split("_")[1]

    await state.update_data(plan=plan)

    await callback.message.answer(
        "💳 Kaspi: 4400430352720152\n\nПосле оплаты нажми 'Я оплатил'",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Я оплатил", callback_data="paid")]
        ])
    )

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

    await callback.message.answer(f"✅ Доступ открыт на {days} дней")

# ---------------- СТАТИСТИКА ----------------

@dp.message(Command("admin"))
async def admin(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    cursor.execute("SELECT COUNT(*) FROM users")
    total = cursor.fetchone()[0]

    cursor.execute("SELECT SUM(exams_passed), SUM(exams_failed) FROM users")
    passed, failed = cursor.fetchone()

    await message.answer(
        f"👥 Пользователей: {total}\n"
        f"✅ Сдали: {passed or 0}\n"
        f"❌ Не сдали: {failed or 0}"
    )

# ---------------- НАЗАД ----------------

@dp.callback_query(F.data == "back")
async def back(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("Меню:", reply_markup=menu_kb())

# ---------------- РЕСТАРТ ----------------

@dp.callback_query(F.data == "restart")
async def restart(callback: CallbackQuery, state: FSMContext):
    await state.set_state(QuizState.data)
    await state.update_data(
        question_index=0,
        score=0,
        mistakes=0,
        free_count=0,
        mode="training"
    )
    await send_question(callback.message, state)

# ---------------- RUN ----------------

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    print("BOT STARTED")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
