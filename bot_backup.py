import json 
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
DB_PATH = "db.sqlite3"

if not os.path.exists(DB_PATH):
    open(DB_PATH, "a").close()

conn = sqlite3.connect(DB_PATH)
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

{"q":"Какой сигнал светофора разрешает движение?","options":["Красный","Желтый","Зеленый","Мигающий красный"],"correct":2,"explanation":"Зеленый сигнал разрешает движение."},

{"q":"Что означает красный сигнал светофора?","options":["Можно ехать","Нужно остановиться","Можно повернуть","Нет значения"],"correct":1,"explanation":"Красный — стоп."},

{"q":"Что означает желтый сигнал?","options":["Стоп","Предупреждение","Ехать","Приоритет"],"correct":1,"explanation":"Желтый предупреждает."},

{"q":"Максимальная скорость в городе?","options":["40","60","80","100"],"correct":1,"explanation":"60 км/ч"},

{"q":"Максимальная скорость вне города?","options":["60","80","90","110"],"correct":2,"explanation":"90 км/ч"},

{"q":"Кто имеет преимущество на перекрестке?","options":["Кто быстрее","По ПДД","Кто сигналит","Кто первый"],"correct":1,"explanation":"Приоритет по ПДД"},

{"q":"Что означает знак 'Уступи дорогу'?","options":["Ехать первым","Остановиться","Уступить","Разворот"],"correct":2,"explanation":"Нужно уступить"},

{"q":"Когда включать поворотник?","options":["После","Во время","Заранее","Не нужно"],"correct":2,"explanation":"Заранее"},

{"q":"Можно ли обгонять на перекрестке?","options":["Да","Нет","Иногда","Можно ночью"],"correct":1,"explanation":"Нельзя"},

{"q":"Что означает знак 'Стоп'?","options":["Замедлиться","Остановиться полностью","Ехать","Приоритет"],"correct":1,"explanation":"Полная остановка"},

{"q":"Где запрещен обгон?","options":["На мосту","На прямой","На трассе","В городе"],"correct":0,"explanation":"На мосту запрещено"},

{"q":"Кто уступает пешеходу?","options":["Пешеход","Водитель","Никто","По договоренности"],"correct":1,"explanation":"Водитель обязан уступить"},

{"q":"Можно ли парковаться на переходе?","options":["Да","Нет","Иногда","Ночью можно"],"correct":1,"explanation":"Запрещено"},

{"q":"Что означает сплошная линия?","options":["Можно пересекать","Нельзя пересекать","Можно обгонять","Нет значения"],"correct":1,"explanation":"Пересекать нельзя"},

{"q":"Когда можно использовать дальний свет?","options":["Всегда","В городе","Вне города","Никогда"],"correct":2,"explanation":"Вне города"},

{"q":"Что делать при ДТП?","options":["Уехать","Остановиться","Позвонить другу","Игнорировать"],"correct":1,"explanation":"Остановиться"},

{"q":"Разрешен ли разворот на мосту?","options":["Да","Нет","Иногда","Ночью"],"correct":1,"explanation":"Запрещено"},

{"q":"Что означает знак 'Пешеходный переход'?","options":["Газ","Стоп","Пешеходы","Обгон"],"correct":2,"explanation":"Пешеходы"},

{"q":"Когда включать аварийку?","options":["При поломке","Всегда","На трассе","Не нужно"],"correct":0,"explanation":"При аварии"},

{"q":"Что делать при мигающем желтом?","options":["Стоп","Ехать осторожно","Газ","Разворот"],"correct":1,"explanation":"Осторожно"},

{"q":"Можно ли ехать без ремня?","options":["Да","Нет","Иногда","Ночью"],"correct":1,"explanation":"Нельзя"},

{"q":"Кто главный на круге?","options":["Въезжающий","На круге","Пешеход","Никто"],"correct":1,"explanation":"Кто на круге"},

{"q":"Что означает знак 'Дети'?","options":["Школа","Дети","Опасность","Газ"],"correct":1,"explanation":"Дети"},

{"q":"Можно ли ехать на красный?","options":["Да","Нет","Иногда","Если никого нет"],"correct":1,"explanation":"Нельзя"},

{"q":"Когда включать ближний свет?","options":["Всегда","Ночью","Днем","Не нужно"],"correct":0,"explanation":"Всегда"},

{"q":"Что делать при заносе?","options":["Газ","Тормоз","Контроль","Прыжок"],"correct":2,"explanation":"Контроль"},

{"q":"Что означает двойная сплошная?","options":["Можно","Нельзя","Обгон","Газ"],"correct":1,"explanation":"Нельзя"},

{"q":"Можно ли стоять на остановке?","options":["Да","Нет","Иногда","Ночью"],"correct":1,"explanation":"Нельзя"},

{"q":"Кто уступает при повороте?","options":["Пешеход","Водитель","Никто","По договору"],"correct":1,"explanation":"Водитель уступает"},

{"q":"Что означает знак 'Обгон запрещен'?","options":["Можно","Нельзя","Иногда","Газ"],"correct":1,"explanation":"Запрещен"},

{"q":"Можно ли парковаться на мосту?","options":["Да","Нет","Иногда","Ночью"],"correct":1,"explanation":"Запрещено"},

{"q":"Что делать при тумане?","options":["Газ","Фары","Стоп","Ничего"],"correct":1,"explanation":"Фары"},

{"q":"Можно ли ехать без прав?","options":["Да","Нет","Иногда","Ночью"],"correct":1,"explanation":"Нельзя"},

{"q":"Что означает знак 'Главная дорога'?","options":["Ты главный","Стоп","Газ","Ничего"],"correct":0,"explanation":"Главная"},

{"q":"Когда уступать?","options":["Всегда","По знакам","Никогда","Иногда"],"correct":1,"explanation":"По знакам"},

{"q":"Можно ли обгонять справа?","options":["Да","Нет","Иногда","Ночью"],"correct":1,"explanation":"Нельзя"},

{"q":"Что означает знак 'Кирпич'?","options":["Можно","Нельзя","Газ","Парковка"],"correct":1,"explanation":"Въезд запрещен"},

{"q":"Можно ли ехать по тротуару?","options":["Да","Нет","Иногда","Ночью"],"correct":1,"explanation":"Нельзя"},

{"q":"Что делать при поломке?","options":["Ехать","Стоп","Аварийка","Газ"],"correct":2,"explanation":"Аварийка"},

{"q":"Можно ли ехать задним ходом на трассе?","options":["Да","Нет","Иногда","Ночью"],"correct":1,"explanation":"Нельзя"},

{"q":"Что означает знак 'Ограничение скорости'?","options":["Газ","Лимит","Стоп","Ничего"],"correct":1,"explanation":"Ограничение"},

{"q":"Можно ли ехать по встречке?","options":["Да","Нет","Иногда","Ночью"],"correct":1,"explanation":"Нельзя"},

{"q":"Что делать при гололеде?","options":["Газ","Медленно","Стоп","Ничего"],"correct":1,"explanation":"Медленно"},

{"q":"Когда уступать автобусу?","options":["Всегда","Никогда","Иногда","По настроению"],"correct":0,"explanation":"Всегда"},

{"q":"Можно ли ехать без света?","options":["Да","Нет","Иногда","Ночью"],"correct":1,"explanation":"Нельзя"},

{"q":"Что означает знак 'ЖД переезд'?","options":["Поезд","Газ","Стоп","Ничего"],"correct":0,"explanation":"Переезд"},

{"q":"Можно ли сигналить в городе?","options":["Да","Нет","Иногда","При опасности"],"correct":3,"explanation":"Только при опасности"},

{"q":"Что делать при пробке?","options":["Газ","Ждать","Разворот","Обгон"],"correct":1,"explanation":"Ждать"},

{"q":"Можно ли ехать на красный при повороте?","options":["Да","Нет","Иногда","Ночью"],"correct":1,"explanation":"Нельзя"},

{"q":"Что означает знак 'Парковка'?","options":["Стоянка","Газ","Стоп","Ничего"],"correct":0,"explanation":"Стоянка разрешена"},

{"q":"Можно ли парковаться на перекрестке?","options":["Да","Нет","Иногда","Ночью"],"correct":1,"explanation":"Нельзя"},

{"q":"Что делать при дожде?","options":["Газ","Медленно","Стоп","Ничего"],"correct":1,"explanation":"Медленно"}
]


# ================= AI =================
base_questions = questions

def generate_ai_question():
    # берём нормальный вопрос из базы
    q = random.choice(questions)

    # копируем
    new_q = {
        "q": q["q"],
        "options": q["options"][:],
        "correct": q["correct"],
        "explanation": q.get("explanation", ""),
        "topic": q.get("topic", q["q"])
    }

    # перемешиваем ответы (как экзамен)
    opts = new_q["options"]
    correct_text = opts[new_q["correct"]]

    random.shuffle(opts)

    new_q["options"] = opts
    new_q["correct"] = opts.index(correct_text)

    return new_q
    
def get_weak_questions(user_id):
    cursor.execute("""
    SELECT topic FROM mistakes 
    WHERE user_id=? 
    ORDER BY count DESC LIMIT 5
    """, (user_id,))

    topics = [row[0] for row in cursor.fetchall()]

    weak = [q for q in questions if q.get("topic", q["q"]) in topics]

    return weak


# === УЛУЧШАЕМ POOL ===

def generate_big_pool():
    pool = []

    for i in range(1000):  # 🔥 больше
        base = random.choice(base_questions)

        text = base["q"] + f" ({i})"

        opts = base["options"][:]
        correct = opts[base["correct"]]

        random.shuffle(opts)

        pool.append({
            "q": text,
            "options": opts,
            "correct": opts.index(correct),
            "explanation": base["explanation"],
            "topic": base.get("topic", base["q"])
        })

    return pool


questions = base_questions + generate_big_pool()


# ================= РЕЖИМЫ =================

@dp.callback_query(F.data == "training")
async def training(callback: CallbackQuery, state: FSMContext):

    await state.set_state(QuizState.data)

    qs = random.sample(questions * 2, 20)
    await state.update_data(
        qs=qs,
        index=0,
        score=0,
        mistakes=0,
        mode="training",
        used=[],
        last_q=None
    )

    await send_question(callback.message, state)


@dp.callback_query(F.data == "hard")
async def hard(callback: CallbackQuery, state: FSMContext):

    weak = get_weak_questions(callback.from_user.id)

    if weak:
        qs = weak * 3
        random.shuffle(qs)
    else:
        qs = [generate_ai_question() for _ in range(15)]

    await state.set_state(QuizState.data)

    await state.update_data(
        qs=qs,
        index=0,
        score=0,
        mistakes=0,
        mode="training",
        used=[],
        last_q=None
    )

    await send_question(callback.message, state)


@dp.callback_query(F.data == "gai")
async def gai(callback: CallbackQuery, state: FSMContext):

    if not has_access(callback.from_user.id):
        await callback.message.answer("🔒 Только после оплаты", reply_markup=pay_kb())
        return

    qs = random.sample(questions, min(30, len(questions)))

    used_q = {q["q"] for q in qs}

    while len(qs) < 30:
        q = generate_ai_question()
        if q["q"] not in used_q:
            qs.append(q)
            used_q.add(q["q"])

    await state.set_state(QuizState.data)

    await state.update_data(
        qs=qs,
        index=0,
        score=0,
        mistakes=0,
        mode="gai",
        used=[],
        last_q=None
    )

    await send_question(callback.message, state)
# ================= STATE =================

class QuizState(StatesGroup):
    data = State()

# ================= UTILS =================
def has_access(user_id):

    cursor.execute(
        "SELECT access_until FROM users WHERE user_id=?",
        (user_id,)
    )

    row = cursor.fetchone()

    return row and row[0] > int(time.time())

def get_stats(user_id):

    cursor.execute(
        "SELECT exams_passed, exams_failed FROM users WHERE user_id=?",
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

    cursor.execute("""
    INSERT INTO users (user_id, username)
    VALUES (?, ?)
    ON CONFLICT(user_id) DO UPDATE SET username=excluded.username
    """, (message.from_user.id, message.from_user.username))

    conn.commit()

    await state.clear()
    await message.answer("🚗 Выбери режим:", reply_markup=menu_kb())

@dp.message(Command("admin"))
async def admin_panel(message: Message):

    if message.from_user.id != ADMIN_ID:
        return

    # сколько всего пользователей
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]

    # сколько оплатили
    cursor.execute(
        "SELECT COUNT(*) FROM users WHERE access_until > ?",
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

    # 🔥 перемешиваем и убираем повторы
    qs = random.sample(questions * 5, min(20, len(questions * 5)))

    # если мало — добавляем AI
    used_q = {q["q"] for q in qs}

    while len(qs) < 20:
        q = generate_ai_question()
        if q["q"] not in used_q:
            qs.append(q)
            used_q.add(q["q"])

    await state.set_state(QuizState.data)

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

    # 🔥 анти-дубликаты
    while i < len(qs) and qs[i]["q"] in used:
        i += 1
    # ❗ текущий вопрос
    q = qs[i]
    
    used.append(q["q"])
    
    await state.update_data(
        used=used,
        index=i
    )
   

    # 🔥 конец
    if i >= len(qs):

        if data["mode"] in ["exam", "gai"]:
            if data["mistakes"] < 3:
                cursor.execute(
                    "UPDATE users SET exams_passed=exams_passed+1 WHERE user_id=?",
                    (message.chat.id,)
                )
                text = "🎉 СДАН"
            else:
                cursor.execute(
                    "UPDATE users SET exams_failed=exams_failed+1 WHERE user_id=?",
                    (message.chat.id,)
                )
                text = "❌ НЕ СДАН"

            conn.commit()
            await message.answer(text, reply_markup=result_kb())

        else:
            await message.answer(
                f"🎉 Конец! Баллы: {data['score']}",
                reply_markup=result_kb()
            )

        await state.clear()
        return

    text = f"{q['q']}\n\n"
    for idx, opt in enumerate(q["options"]):
        text += f"{chr(65+idx)}) {opt}\n"

    await message.answer(text, reply_markup=answers_kb())

# ================= ОТВЕТ =================

@dp.callback_query(F.data.startswith("ans_"))
async def answer(callback:CallbackQuery, state:FSMContext):
    data = await state.get_data()
    qs = data["qs"]
    i = data["index"]

    q = qs[i]
    user = int(callback.data.split("_")[1])

    if user == q["correct"]:
        data["score"] += 1
        await callback.message.answer("✅ Верно")
    else:
        data["mistakes"] += 1
        await callback.message.answer("❌ Неверно")

        cursor.execute("""
        INSERT INTO mistakes (user_id, topic, count)
        VALUES (?, ?, 1)
        ON CONFLICT(user_id, topic)
        DO UPDATE SET count = count + 1
        """, (callback.from_user.id, q.get("topic", q["q"])))
        conn.commit()

    if data["mode"] in ["exam", "gai"] and data["mistakes"] >= 3:
        cursor.execute("UPDATE users SET exams_failed=exams_failed+1 WHERE user_id=?", (callback.from_user.id,))
        conn.commit()

        await callback.message.answer("❌ Провал", reply_markup=result_kb())
        await state.clear()
        return

    await state.update_data(index=i+1, score=data["score"], mistakes=data["mistakes"])
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

    cursor.execute("UPDATE users SET access_until=? WHERE user_id=?", (until, user_id))
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
