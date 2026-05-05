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

# ================= БАЗА =================

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

# ================= ВОПРОСЫ =================

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
        "explanation": "Приоритет по ПДД"
    }
]

topics = {
    "signs": [],
    "speed": [],
    "priority": []
}

for q in questions:
    if "светофора" in q["q"]:
        topics["signs"].append(q)
    elif "скорость" in q["q"]:
        topics["speed"].append(q)
    else:
        topics["priority"].append(q)

# === КНОПКА ТЕМ ===

def topics_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚦 Знаки", callback_data="topic_signs")],
        [InlineKeyboardButton(text="🚗 Скорость", callback_data="topic_speed")],
        [InlineKeyboardButton(text="⚠️ Приоритет", callback_data="topic_priority")],
        [InlineKeyboardButton(text="⬅️ В меню", callback_data="menu")]
    ])

# ================= STATE =================

class QuizState(StatesGroup):
    data = State()

# ================= UTILS =================

def has_access(user_id):
    cursor.execute("SELECT access_until FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    return row and row[0] > int(time.time())

def get_user_stats(user_id):
    cursor.execute("SELECT exams_passed, exams_failed FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    if not row:
        return 0, 0
    return row

# ================= КНОПКИ =================

def menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📘 Тренировка", callback_data="training")],
        [InlineKeyboardButton(text="📝 Экзамен", callback_data="exam")],
        [InlineKeyboardButton(text="⭐ Моя статистика", callback_data="my_stats")],
        [InlineKeyboardButton(text="🔥 Топ игроков", callback_data="top")]
    ])

def answers_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="A", callback_data="ans_0"),
         InlineKeyboardButton(text="B", callback_data="ans_1")],
        [InlineKeyboardButton(text="C", callback_data="ans_2"),
         InlineKeyboardButton(text="D", callback_data="ans_3")],
        [InlineKeyboardButton(text="📖 Объяснение", callback_data="explain")],
        [InlineKeyboardButton(text="⬅️ В меню", callback_data="menu")]
    ])

def pay_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 7 дней — 5000₸", callback_data="buy_7")],
        [InlineKeyboardButton(text="💳 30 дней — 10000₸", callback_data="buy_30")]
    ])

def result_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔁 Пройти ещё раз", callback_data="restart")],
        [InlineKeyboardButton(text="⬅️ В меню", callback_data="menu")]
    ])

# ================= START =================

@dp.message(Command("start"))
async def start(message: Message, state: FSMContext):
    cursor.execute("INSERT OR IGNORE INTO users VALUES (?, ?, 0, 0, 0)",
                   (message.from_user.id, message.from_user.username))
    conn.commit()

    await state.clear()

    await message.answer("🚗 Добро пожаловать!\nВыбери режим:", reply_markup=menu_kb())

# ================= РЕЖИМ =================

@dp.callback_query(F.data == "training")
async def training(callback: CallbackQuery, state: FSMContext):
    await state.set_state(QuizState.data)
    await state.update_data(question_index=0, score=0, mistakes=0, free_count=0, mode="training")
    await send_question(callback.message, state)

@dp.callback_query(F.data == "exam")
async def exam(callback: CallbackQuery, state: FSMContext):
    if not has_access(callback.from_user.id):
        await callback.message.answer("🔒 Экзамен доступен после оплаты", reply_markup=pay_kb())
        return

@dp.callback_query(F.data == "topics")
async def topics_menu(callback: CallbackQuery):
    await callback.message.answer("Выбери тему:", reply_markup=topics_kb())

@dp.callback_query(F.data.startswith("topic_"))
async def topic_start(callback: CallbackQuery, state: FSMContext):
    topic = callback.data.split("_")[1]

    qs = topics.get(topic, questions)

    await state.set_state(QuizState.data)
    await state.update_data(
        question_index=0,
        score=0,
        mistakes=0,
        mode="topic",
        topic_qs=qs
    )

    await send_question(callback.message, state)

    exam_qs = random.sample(questions * 10, 20)
    await state.set_state(QuizState.data)
    await state.update_data(question_index=0, score=0, mistakes=0, mode="exam", exam_qs=exam_qs)

    await send_question(callback.message, state)

# ================= ВОПРОС =================

async def send_question(message: Message, state: FSMContext):
    data = await state.get_data()
    index = data["question_index"]

    if data["mode"] == "exam":
        qs = data.get("exam_qs")
    elif data["mode"] == "topic":
        qs = data.get("topic_qs")
    else:
        qs = questions

    if index >= len(qs):

        if data["mode"] == "training":
            await message.answer(f"🎉 Тренировка завершена!\nБаллы: {data['score']}", reply_markup=result_kb())

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

# ================= ОТВЕТ =================

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

# ================= ОБЪЯСНЕНИЕ =================

@dp.callback_query(F.data == "explain")
async def explain(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    index = data["question_index"] - 1

    qs = data.get("exam_qs") if data["mode"] == "exam" else questions

    if 0 <= index < len(qs):
        await callback.message.answer(f"📖 {qs[index]['explanation']}")

# ================= RESTART =================
@dp.callback_query(F.data == "restart")
async def restart(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    mode = data.get("mode", "training")

    await state.set_state(QuizState.data)

    new_data = {
        "question_index": 0,
        "score": 0,
        "mistakes": 0,
        "free_count": 0,
        "mode": mode
    }

    if mode == "exam":
        new_data["exam_qs"] = random.sample(questions * 10, 20)

    if mode == "topic":
        new_data["topic_qs"] = data.get("topic_qs")

    await state.update_data(**new_data)

    await send_question(callback.message, state)

# ================= MENU =================

@dp.callback_query(F.data == "menu")
async def menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("Выбери режим:", reply_markup=menu_kb())

def menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📘 Тренировка", callback_data="training")],
        [InlineKeyboardButton(text="🧠 По темам", callback_data="topics")],
        [InlineKeyboardButton(text="📝 Экзамен", callback_data="exam")],
        [InlineKeyboardButton(text="⭐ Моя статистика", callback_data="my_stats")],
        [InlineKeyboardButton(text="🔥 Топ игроков", callback_data="top")]
    ])

# ================= СТАТИСТИКА =================

@dp.callback_query(F.data == "my_stats")
async def my_stats(callback: CallbackQuery):
    passed, failed = get_user_stats(callback.from_user.id)
    total = passed + failed
    percent = int((passed / total) * 100) if total > 0 else 0

    await callback.message.answer(
        f"📊 Твоя статистика:\n\n"
        f"✅ Сдал: {passed}\n"
        f"❌ Провалил: {failed}\n"
        f"📈 Успешность: {percent}%\n\n"
        f"🧠 Рекомендуем тренировать слабые темы"
    )
@dp.callback_query(F.data == "top")
async def top(callback: CallbackQuery):
    cursor.execute("""
    SELECT username, exams_passed 
    FROM users 
    ORDER BY exams_passed DESC 
    LIMIT 5
    """)

    rows = cursor.fetchall()

    text = "🔥 ТОП игроков:\n\n"
    for i, row in enumerate(rows, start=1):
        name = row[0] or "Без имени"
        score = row[1]
        text += f"{i}. {name} — {score}\n"

    await callback.message.answer(text)

# ================= RUN =================

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    print("BOT STARTED")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
