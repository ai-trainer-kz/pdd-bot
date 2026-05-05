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
    xp INTEGER DEFAULT 0
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
     "explanation":"Зеленый разрешает движение",
     "topic":"traffic"},

    {"q":"Максимальная скорость в городе?",
     "options":["40","60","80","100"],
     "correct":1,
     "explanation":"60 км/ч",
     "topic":"speed"},

    {"q":"Кто имеет преимущество на перекрестке?",
     "options":["Кто быстрее","По договоренности","По ПДД","Кто сигналит"],
     "correct":2,
     "explanation":"Приоритет по ПДД",
     "topic":"priority"}
]

# ================= AI ГЕНЕРАЦИЯ =================

templates = [
    "Что верно?",
    "Как правильно поступить?",
    "Выберите правильный ответ:",
    "Как действовать водителю?"
]

def generate_ai_question():
    base = random.choice(questions)

    q_text = f"{random.choice(templates)} {base['q']}"

    opts = base["options"][:]
    correct = opts[base["correct"]]

    random.shuffle(opts)

    return {
        "q": q_text,
        "options": opts,
        "correct": opts.index(correct),
        "explanation": base["explanation"],
        "topic": base["topic"]
    }

def generate_unique_question(used):
    for _ in range(10):
        q = generate_ai_question()
        if q["q"] not in used:
            used.add(q["q"])
            return q
    return random.choice(questions)

# ================= STATE =================

class QuizState(StatesGroup):
    data = State()

# ================= UTILS =================

def has_access(user_id):
    cursor.execute("SELECT access_until FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    return row and row[0] > int(time.time())

def add_xp(user_id, amount):
    cursor.execute("UPDATE users SET xp = xp + ? WHERE user_id=?", (amount, user_id))
    conn.commit()

def get_level(xp):
    return xp // 100 + 1

def get_stats(user_id):
    cursor.execute("SELECT exams_passed, exams_failed, xp FROM users WHERE user_id=?", (user_id,))
    return cursor.fetchone() or (0,0,0)

def get_weak_topics(user_id):
    cursor.execute("SELECT topic FROM mistakes WHERE user_id=? ORDER BY count DESC LIMIT 3", (user_id,))
    return [r[0] for r in cursor.fetchall()]

# ================= КНОПКИ =================

def menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📘 Тренировка", callback_data="training")],
        [InlineKeyboardButton(text="🧠 Слабые темы", callback_data="hard")],
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
    cursor.execute("INSERT OR IGNORE INTO users VALUES (?, ?, 0, 0, 0, 0)",
                   (message.from_user.id, message.from_user.username))
    conn.commit()

    await state.clear()
    await message.answer("🚗 Выбери режим:", reply_markup=menu_kb())

# ================= РЕЖИМЫ =================

@dp.callback_query(F.data == "training")
async def training(callback: CallbackQuery, state: FSMContext):
    used=set()
    qs=[generate_unique_question(used) for _ in range(15)]

    await state.set_state(QuizState.data)
    await state.update_data(qs=qs,index=0,score=0,mistakes=0,mode="training",used=[])
    await send_question(callback.message,state)

@dp.callback_query(F.data=="hard")
async def hard(callback:CallbackQuery,state:FSMContext):
    topics=get_weak_topics(callback.from_user.id)
    used=set()

    qs=[]
    while len(qs)<10:
        q=generate_unique_question(used)
        if not topics or q["topic"] in topics:
            qs.append(q)

    await state.set_state(QuizState.data)
    await state.update_data(qs=qs,index=0,score=0,mistakes=0,mode="training",used=[])
    await send_question(callback.message,state)

@dp.callback_query(F.data=="exam")
async def exam(callback:CallbackQuery,state:FSMContext):
    if not has_access(callback.from_user.id):
        await callback.message.answer("🔒 Нужна оплата",reply_markup=pay_kb())
        return

    used=set()
    qs=[generate_unique_question(used) for _ in range(20)]

    await state.set_state(QuizState.data)
    await state.update_data(qs=qs,index=0,score=0,mistakes=0,mode="exam",used=[])
    await send_question(callback.message,state)

# ================= ВОПРОС =================

async def send_question(message:Message,state:FSMContext):
    data=await state.get_data()
    qs=data["qs"]
    i=data["index"]

    if i>=len(qs):
        await message.answer(f"🎉 Баллы: {data['score']}",reply_markup=result_kb())
        await state.clear()
        return

    q=qs[i]

    text=f"{q['q']}\n\n"
    for idx,opt in enumerate(q["options"]):
        text+=f"{chr(65+idx)}) {opt}\n"

    await message.answer(text,reply_markup=answers_kb())

# ================= ОТВЕТ =================

@dp.callback_query(F.data.startswith("ans_"))
async def answer(callback:CallbackQuery,state:FSMContext):
    data=await state.get_data()
    q=data["qs"][data["index"]]

    user=int(callback.data.split("_")[1])

    if user==q["correct"]:
        data["score"]+=1
        add_xp(callback.from_user.id,10)
        await callback.message.answer("✅ Верно")
    else:
        data["mistakes"]+=1
        await callback.message.answer("❌ Неверно")

    await state.update_data(index=data["index"]+1,score=data["score"],mistakes=data["mistakes"])
    await send_question(callback.message,state)

# ================= СТАТИСТИКА =================

@dp.callback_query(F.data=="stats")
async def stats(callback:CallbackQuery):
    p,f,xp=get_stats(callback.from_user.id)
    level=get_level(xp)

    await callback.message.answer(
        f"📊 Сдал: {p}\n❌ Провалил: {f}\n⭐ Уровень: {level}\n🔥 XP: {xp}"
    )

# ================= RUN =================

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    print("STARTED")
    await dp.start_polling(bot)

if __name__=="__main__":
    asyncio.run(main())
