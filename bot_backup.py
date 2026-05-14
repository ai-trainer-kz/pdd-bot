import json 
import os
import random 
import asyncio
import time

try:
    with open("questions.json", "r", encoding="utf-8") as f:
        questions = json.load(f)

    formatted_questions = []

for q in questions:

    formatted_questions.append({
        "q": q["question"],
        "options": [q["A"], q["B"], q["C"], q["D"]],
        "correct": ["A","B","C","D"].index(q["correct"]),
        "explanation": q.get("explanation", ""),
        "topic": q.get("question", "")
    })

questions = formatted_questions

    print(f"Загружено вопросов: {len(questions)}")

except Exception as e:
    print("ОШИБКА JSON:", e)
    questions = []

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

TOKEN = os.getenv("TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
ADMIN_ID = 8398266271

import psycopg2

conn = psycopg2.connect(DATABASE_URL)
conn.autocommit = True
cursor = conn.cursor()

bot = Bot(token=TOKEN)
dp = Dispatcher()
# ================= БАЗА =================
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    username TEXT,
    access_until INTEGER DEFAULT 0,
    exams_passed INTEGER DEFAULT 0,
    exams_failed INTEGER DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS mistakes (
    user_id BIGINT,
    topic TEXT,
    count INTEGER DEFAULT 1,
    PRIMARY KEY (user_id, topic)
)
""")

conn.commit()

cursor.execute("""
ALTER TABLE users
ALTER COLUMN user_id TYPE BIGINT
""")

cursor.execute("""
ALTER TABLE mistakes
ALTER COLUMN user_id TYPE BIGINT
""")

conn.commit()

# ================= AI ================
    
def get_weak_questions(user_id):
    cursor.execute("""
    SELECT topic FROM mistakes 
    WHERE user_id=? 
    ORDER BY count DESC LIMIT 5
    """, (user_id,))

    topics = [row[0] for row in cursor.fetchall()]

    weak = [q for q in questions if q.get("topic", q["q"]) in topics]

    return weak

# ================= РЕЖИМЫ =================

@dp.callback_query(F.data == "training")
async def training(callback: CallbackQuery, state: FSMContext):

    await state.set_state(QuizState.data)

    qs = random.sample(questions, min(20, len(questions)))

    await state.update_data(
        qs=qs,
        index=0,
        mistakes=0,
        mode="training",
        used=[]
    )

    await send_question(callback.message, state)

@dp.callback_query(F.data == "hard")
async def hard(callback: CallbackQuery, state: FSMContext):

    await state.set_state(QuizState.data)

    qs = random.sample(questions, min(20, len(questions)))

    await state.update_data(
        qs=qs,
        index=0,
        mistakes=0,
        mode="hard",
        used=[]
    )

    await send_question(callback.message, state)

@dp.callback_query(F.data == "gai")
async def gai(callback: CallbackQuery, state: FSMContext):

    await state.set_state(QuizState.data)

    qs = random.sample(questions, min(20, len(questions)))

    await state.update_data(
        qs=qs,
        index=0,
        mistakes=0,
        mode="gai",
        used=[]
    )

    await send_question(callback.message, state)

# ================= STATE =================

class QuizState(StatesGroup):
    data = State()

# ================= UTILS =================
def has_access(user_id):

    cursor.execute(
        "SELECT access_until FROM users WHERE user_id=%s",
        (user_id,)
    )

    row = cursor.fetchone()

    return row and row[0] > int(time.time())

def get_stats(user_id):

    cursor.execute(
        "SELECT exams_passed, exams_failed FROM users WHERE user_id=%s",
        (user_id,)
    )

    row = cursor.fetchone()

    return row if row else (0, 0)
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

    cursor.execute(
        "SELECT COUNT(*) FROM users WHERE user_id=%s",
        (message.from_user.id,)
    )
    
    exists = cursor.fetchone()[0]
    if exists == 0:
        cursor.execute(
            """
            INSERT INTO users
            (user_id, username, access_until, exams_passed, exams_failed)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                message.from_user.id,
                message.from_user.username,
                0,
                0,
                0
            ) 
        )

        conn.commit()

    await state.clear()

    await message.answer(
        "🚗 Выбери режим:",
        reply_markup=menu_kb()
    )

@dp.message(Command("admin"))
async def admin_panel(message: Message):

    if message.from_user.id != ADMIN_ID:
        return

    # сколько всего пользователей
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]

    # сколько оплатили
    cursor.execute(
        "SELECT COUNT(*) FROM users WHERE access_until > %s",
        (int(time.time()),)
    )
    paid_users = cursor.fetchone()[0]

    text = (
        f"👥 Пользователей: {total_users}\n"
        f"💰 Оплатили: {paid_users}"
    )

    await message.answer(text)

@dp.callback_query(F.data == "exam")
async def exam(callback: CallbackQuery, state: FSMContext):

    if not has_access(callback.from_user.id):
        await callback.message.answer(
            "🔒 Экзамен доступен только после оплаты",
            reply_markup=pay_kb()
        )
        return

    await state.set_state(QuizState.data)

    qs = random.sample(questions, min(20, len(questions)))

    await state.update_data(
        qs=qs,
        index=0,
        score=0,
        mistakes=0,
        mode="exam",
        used=[]
    )

    await send_question(callback.message, state)

# ================= ВОПРОС =================
async def send_question(message: Message, state: FSMContext):
    data = await state.get_data()

    qs = data["qs"]
    i = data["index"]

    used = data.get("used", [])
    
    # 🔥 конец вопросов
    if i >= len(qs):

        if data["mode"] in ["exam", "gai"]:

            if data["mistakes"] < 3:

                cursor.execute(
                    "UPDATE users SET exams_passed=exams_passed+1 WHERE user_id=%s",
                    (message.chat.id,)
                )

                text = "🎉 СДАН"

            else:

                cursor.execute(
                    "UPDATE users SET exams_failed=exams_failed+1 WHERE user_id=%s",
                    (message.chat.id,)
                )

                text = "❌ НЕ СДАН"

            conn.commit()

            await message.answer(
                text,
                reply_markup=result_kb()
            )

        else:

            await message.answer(
                f"🎉 Конец! Баллы: {data['score']}",
                reply_markup=result_kb()
            )

        await state.clear()
        return

    # ❗ текущий вопрос
    q = qs[i]

    text = f"{q['q']}\n\n"
    
    for idx, opt in enumerate(q["options"]):
        text += f"{chr(65+idx)}) {opt}\n"
    
    await message.answer(
        text,
        reply_markup=answers_kb()
    )
# ================= ОТВЕТ =================
@dp.callback_query(F.data.startswith("ans_"))
async def answer(callback: CallbackQuery, state: FSMContext):

    data = await state.get_data()

    qs = data["qs"]
    i = data["index"]

    q = qs[i]

    selected = int(callback.data.split("_")[1])

    if selected == q["correct"]:

        await callback.message.answer("✅ Верно")

        score = data.get("score", 0) + 1

        await state.update_data(score=score)

    else:

        await callback.message.answer("❌ Неверно")

        mistakes = data.get("mistakes", 0) + 1

        await state.update_data(mistakes=mistakes)

    i += 1

    await state.update_data(index=i)

    if i >= len(qs):

        score = data.get("score", 0)

        await callback.message.answer(
            f"🏁 Тест завершён\n\n✅ Правильных: {score}\n❌ Ошибок: {data.get('mistakes', 0)}"
        )

        await state.clear()

        return

    await send_question(callback.message, state)

# ================= ОБЪЯСНЕНИЕ =================

@dp.callback_query(F.data=="explain")
async def explain(callback:CallbackQuery, state:FSMContext):
    data = await state.get_data()
    i = data["index"]-1
    qs = data["qs"]

    if 0 <= i < len(qs):
        await callback.message.answer(qs[i]["explanation"])

# ================= ОПЛАТА =================

@dp.callback_query(F.data.startswith("buy_"))
async def buy(callback:CallbackQuery, state:FSMContext):
    plan = callback.data.split("_")[1]
    await state.update_data(plan=plan)

    await callback.message.answer("Kaspi: 4400430352720152\nПосле оплаты нажми кнопку ниже")

@dp.callback_query(F.data=="paid")
async def paid(callback: CallbackQuery, state:FSMContext):
    data = await state.get_data()
    plan = data.get("plan")

    if not plan:
        await callback.message.answer("Сначала выбери тариф")
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"approve_{callback.from_user.id}_{plan}")]
    ])

    await bot.send_message(ADMIN_ID, f"Оплата от {callback.from_user.id} тариф {plan}", reply_markup=kb)
    await callback.message.answer("⏳ Жди подтверждения")

@dp.callback_query(F.data.startswith("approve_"))
async def approve(callback:CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return

    _, user_id, plan = callback.data.split("_")
    user_id = int(user_id)

    days = 7 if plan=="7" else 30
    until = int(time.time()) + days * 86400

    cursor.execute("UPDATE users SET access_until=%s WHERE user_id=%s", (until, user_id))
    conn.commit()

    await bot.send_message(user_id, "✅ Доступ открыт", reply_markup=menu_kb())
    await callback.message.edit_text("Готово")

# ================= СТАТИСТИКА =================

@dp.callback_query(F.data=="stats")
async def stats(callback:CallbackQuery):
    p,f = get_stats(callback.from_user.id)
    total = p+f
    percent = int(p/total*100) if total else 0

    await callback.message.answer(f"📊 Сдал: {p}\n❌ Провалил: {f}\n📈 {percent}%")

@dp.callback_query(F.data=="top")
async def top(callback:CallbackQuery):
    cursor.execute("SELECT username, exams_passed FROM users ORDER BY exams_passed DESC LIMIT 5")
    rows = cursor.fetchall()

    text="🔥 ТОП:\n"
    for i,r in enumerate(rows,1):
        text += f"{i}. {r[0]} — {r[1]}\n"

    await callback.message.answer(text)

# ================= ДРУГОЕ =================

@dp.callback_query(F.data=="menu")
async def menu(callback:CallbackQuery, state:FSMContext):
    await state.clear()
    await callback.message.answer("Меню:", reply_markup=menu_kb())

@dp.callback_query(F.data=="restart")
async def restart(callback:CallbackQuery, state:FSMContext):
    data = await state.get_data()
    qs = random.sample(questions, 20)
    await state.set_state(QuizState.data)
    await state.update_data(qs=qs, index=0, score=0, mistakes=0, mode=data.get("mode","training"))

    await send_question(callback.message, state)

# ================= RUN =================

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    print("STARTED")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
