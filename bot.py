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
    exams_failed INTEGER DEFAULT 0,
    xp INTEGER DEFAULT 0,
    streak INTEGER DEFAULT 0,
    last_answer INTEGER DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS mistakes (
    user_id INTEGER,
    topic TEXT,
    count INTEGER DEFAULT 1,
    PRIMARY KEY (user_id, topic)
)
""")

conn.commit()

# ================= ВОПРОСЫ =================

questions = [
    {"q":"Какой сигнал светофора разрешает движение?",
     "options":["Красный","Желтый","Зеленый","Мигающий красный"],
     "correct":2,
     "explanation":"Зеленый сигнал разрешает движение."},

    {"q":"Максимальная скорость в городе?",
     "options":["40","60","80","100"],
     "correct":1,
     "explanation":"60 км/ч"},

    {"q":"Кто имеет преимущество на перекрестке?",
     "options":["Кто быстрее","По договоренности","По ПДД","Кто сигналит"],
     "correct":2,
     "explanation":"Приоритет по ПДД"}
]

# ================= AI =================

def generate_ai_question():
    base = random.choice(questions)

    options = base["options"][:]
    correct_text = options[base["correct"]]
    random.shuffle(options)

    return {
        "q": random.choice([
            base["q"],
            f"Как правильно: {base['q']}",
            f"Что должен сделать водитель: {base['q']}"
        ]),
        "options": options,
        "correct": options.index(correct_text),
        "explanation": base["explanation"],
        "topic": base["q"]
    }

# ================= СЛОЖНЫЕ ТЕМЫ =================

def get_weak_questions(user_id):
    cursor.execute("""
        SELECT topic FROM mistakes
        WHERE user_id=?
        ORDER BY count DESC
        LIMIT 5
    """, (user_id,))
    
    rows = cursor.fetchall()
    topics = [r[0] for r in rows]

    return [q for q in questions if q["q"] in topics]

# ================= STATE =================

class QuizState(StatesGroup):
    data = State()

# ================= UTILS =================

def has_access(user_id):
    cursor.execute("SELECT access_until FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    return row and row[0] > int(time.time())

def get_stats(user_id):
    cursor.execute("SELECT exams_passed, exams_failed FROM users WHERE user_id=?", (user_id,))
    return cursor.fetchone() or (0,0)

def update_xp(user_id, correct):
    cursor.execute("SELECT xp, streak, last_answer FROM users WHERE user_id=?", (user_id,))
    xp, streak, last = cursor.fetchone()

    now = int(time.time())

    if correct:
        if now - last < 3600:
            streak += 1
        else:
            streak = 1

        xp += 10 + streak
    else:
        streak = 0

    cursor.execute("""
        UPDATE users SET xp=?, streak=?, last_answer=? WHERE user_id=?
    """, (xp, streak, now, user_id))

    conn.commit()

# ================= КНОПКИ =================

def menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📘 Тренировка", callback_data="training")],
        [InlineKeyboardButton(text="🧠 Сложные темы", callback_data="hard")],
        [InlineKeyboardButton(text="🎯 ГАИ режим", callback_data="gai")],
        [InlineKeyboardButton(text="📝 Экзамен", callback_data="exam")],
        [InlineKeyboardButton(text="⭐ Статистика", callback_data="stats")],
        [InlineKeyboardButton(text="🔥 Топ", callback_data="top")]
    ])

def answers_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="A", callback_data="ans_0"),
         InlineKeyboardButton(text="B", callback_data="ans_1")],
        [InlineKeyboardButton(text="C", callback_data="ans_2"),
         InlineKeyboardButton(text="D", callback_data="ans_3")],
        [InlineKeyboardButton(text="📖 Объяснение", callback_data="explain")],
        [InlineKeyboardButton(text="⬅️ Меню", callback_data="menu")]
    ])

def pay_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 7 дней — 5000₸", callback_data="buy_7")],
        [InlineKeyboardButton(text="💳 30 дней — 10000₸", callback_data="buy_30")],
        [InlineKeyboardButton(text="✅ Я оплатил", callback_data="paid")]
    ])

def result_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔁 Пройти ещё раз", callback_data="restart")],
        [InlineKeyboardButton(text="⬅️ Меню", callback_data="menu")]
    ])

# ================= START =================

@dp.message(Command("start"))
async def start(message: Message, state: FSMContext):
    cursor.execute("INSERT OR IGNORE INTO users VALUES (?, ?, 0, 0, 0, 0, 0, 0)",
                   (message.from_user.id, message.from_user.username))
    conn.commit()

    await state.clear()
    await message.answer("🚗 Выбери режим:", reply_markup=menu_kb())

# ================= РЕЖИМЫ =================

@dp.callback_query(F.data == "training")
async def training(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    qs = random.sample(questions * 3, 15)

    await state.set_state(QuizState.data)
    await state.update_data(qs=qs, index=0, score=0, mistakes=0, mode="training")

    await send_question(callback.message, state)


@dp.callback_query(F.data == "hard")
async def hard(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    weak = get_weak_questions(callback.from_user.id)
    qs = weak * 3 if weak else [generate_ai_question() for _ in range(10)]

    await state.set_state(QuizState.data)
    await state.update_data(qs=qs, index=0, score=0, mistakes=0, mode="training")

    await send_question(callback.message, state)


@dp.callback_query(F.data == "gai")
async def gai(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    if not has_access(callback.from_user.id):
        await callback.message.answer("🔒 Нужна оплата", reply_markup=pay_kb())
        return

    qs = random.sample(questions, min(20, len(questions)))

    while len(qs) < 20:
        qs.append(generate_ai_question())

    await state.set_state(QuizState.data)
    await state.update_data(qs=qs, index=0, score=0, mistakes=0, mode="gai")

    await send_question(callback.message, state)


@dp.callback_query(F.data == "exam")
async def exam(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    if not has_access(callback.from_user.id):
        await callback.message.answer("🔒 Нужна оплата", reply_markup=pay_kb())
        return

    qs = random.sample(questions * 5, 20)

    await state.set_state(QuizState.data)
    await state.update_data(qs=qs, index=0, score=0, mistakes=0, mode="exam")

    await send_question(callback.message, state)

# ================= ВОПРОС =================

async def send_question(message: Message, state: FSMContext):
    data = await state.get_data()
    qs = data["qs"]
    i = data["index"]

    if i >= len(qs):
        await message.answer(f"🎉 Конец! Баллы: {data['score']}", reply_markup=result_kb())
        await state.clear()
        return

    q = qs[i]

    await state.update_data(current_q=q)

    text = f"{q['q']}\n\n"
    for idx, opt in enumerate(q["options"]):
        text += f"{chr(65+idx)}) {opt}\n"

    await message.answer(text, reply_markup=answers_kb())

# ================= ОТВЕТ =================

@dp.callback_query(F.data.startswith("ans_"))
async def answer(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    data = await state.get_data()
    q = data["qs"][data["index"]]

    user = int(callback.data.split("_")[1])

    correct = user == q["correct"]

    if correct:
        data["score"] += 1
        await callback.message.answer("✅ Верно")
    else:
        data["mistakes"] += 1
        await callback.message.answer("❌ Неверно")

    update_xp(callback.from_user.id, correct)

    await state.update_data(index=data["index"]+1, score=data["score"], mistakes=data["mistakes"])

    await send_question(callback.message, state)

# ================= ОБЪЯСНЕНИЕ =================

@dp.callback_query(F.data=="explain")
async def explain(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    data = await state.get_data()
    q = data.get("current_q")

    if q:
        await callback.message.answer(q["explanation"])

# ================= ОПЛАТА =================

@dp.callback_query(F.data.startswith("buy_"))
async def buy(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    plan = callback.data.split("_")[1]

    cursor.execute("INSERT OR IGNORE INTO users VALUES (?, ?, 0, 0, 0, 0, 0, 0)",
                   (callback.from_user.id, callback.from_user.username))
    conn.commit()

    await state.update_data(plan=plan)

    await callback.message.answer("Kaspi: 4400430352720152\nПосле оплаты нажми 'Я оплатил'")

@dp.callback_query(F.data=="paid")
async def paid(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    data = await state.get_data()
    plan = data.get("plan")

    if not plan:
        await callback.message.answer("Выбери тариф")
        return

    # 🔥 авто-подтверждение (заглушка Kaspi API)
    days = 7 if plan=="7" else 30
    until = int(time.time()) + days * 86400

    cursor.execute("UPDATE users SET access_until=? WHERE user_id=?", (until, callback.from_user.id))
    conn.commit()

    await callback.message.answer("✅ Доступ открыт")

# ================= СТАТИСТИКА =================

@dp.callback_query(F.data=="stats")
async def stats(callback: CallbackQuery):
    await callback.answer()

    p,f = get_stats(callback.from_user.id)

    cursor.execute("SELECT xp, streak FROM users WHERE user_id=?", (callback.from_user.id,))
    xp, streak = cursor.fetchone()

    await callback.message.answer(
        f"📊 Сдал: {p}\n❌ Провал: {f}\n⭐ XP: {xp}\n🔥 Streak: {streak}"
    )

@dp.callback_query(F.data=="top")
async def top(callback: CallbackQuery):
    await callback.answer()

    cursor.execute("SELECT username, xp FROM users ORDER BY xp DESC LIMIT 5")
    rows = cursor.fetchall()

    text="🔥 ТОП:\n"
    for i,r in enumerate(rows,1):
        text += f"{i}. {r[0]} — {r[1]} XP\n"

    await callback.message.answer(text)

# ================= МЕНЮ =================

@dp.callback_query(F.data=="menu")
async def menu(callback: CallbackQuery, state:FSMContext):
    await callback.answer()
    await state.clear()
    await callback.message.answer("Меню:", reply_markup=menu_kb())

@dp.callback_query(F.data=="restart")
async def restart(callback: CallbackQuery, state:FSMContext):
    await callback.answer()
    await training(callback, state)

# ================= RUN =================

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    print("STARTED")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
