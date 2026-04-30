import os
import logging
import json
from datetime import datetime, timedelta
import re
import asyncio

USERS_FILE = "users.json"

def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_users():
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

users = load_users()

from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
from openai import OpenAI

# ===== CONFIG =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

ADMIN_ID = 503301815
KASPI = "4400430352720152"

MODEL = "gpt-4o-mini"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
client = OpenAI(api_key=OPENAI_API_KEY)

logging.basicConfig(level=logging.INFO)

users = load_users()
last_questions = {}

# ===== SAVE =====
def save_users():
    with open("users.json", "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def load_users():
    global users
    try:
        with open("users.json", "r", encoding="utf-8") as f:
            users = json.load(f)
    except:
        users = {}

# ===== USER =====
def ensure_user(uid):
    uid = str(uid)
    if uid not in users:
        users[uid] = {
            "mode": None,
            "correct_answer": None,
            "explanation": "",
            "free_limit": 5,
            "used_free": 0,
            "premium_until": None,
            "plan": None,
            "correct": 0,
            "wrong": 0,
            "exam_count": 0,
            "exam_correct": 0,
            "waiting_answer": False
        }
        save_users()

def has_access(u):
    try:
        if u.get("premium_until"):
            if datetime.now() < datetime.fromisoformat(u["premium_until"]):
                return True
    except:
        pass

    return u.get("used_free", 0) < u.get("free_limit", 5)

# ===== UI =====
def main_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🎯 Тренировка", "🧠 Экзамен")
    kb.add("📊 Статистика", "💳 Купить доступ")
    return kb

def answer_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("A","B","C","D")
    kb.add("⬅️ Назад")
    return kb

# ===== GPT =====
async def ask_gpt(uid):
    prompt = """
Ты помощник для подготовки к экзамену ПДД Казахстан.

Сгенерируй 1 новый вопрос по правилам дорожного движения.

Требования:
- Пиши только на русском языке
- Без приветствий и лишнего текста
- Вопрос должен быть понятным и реальным (как на экзамене)
- 4 варианта ответа (A, B, C, D)
- Только 1 правильный ответ
- Объяснение короткое и понятное

Формат ответа строго такой:

Вопрос:
текст вопроса

A) вариант
B) вариант
C) вариант
D) вариант

Правильный ответ: A
Объяснение: краткое объяснение
"""

    loop = asyncio.get_event_loop()

    r = await loop.run_in_executor(
        None,
        lambda: client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.6
        )
    )

    text = r.choices[0].message.content

    # защита от мусора
    if "Hello" in text or "assist" in text or len(text) < 50:
        return await ask_gpt(uid)

    ans = re.search(r"Правильный ответ[:\s]*([ABCD])", text)
    exp = re.search(r"Объяснение[:\s]*(.*)", text, re.S)

    question_only = re.sub(r"Правильный ответ.*", "", text, flags=re.S)
    question_only = re.sub(r"Объяснение.*", "", question_only, flags=re.S)

    return question_only, ans.group(1) if ans else "A", exp.group(1).strip() if exp else ""
# ===== START =====
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    ensure_user(message.from_user.id)

    await message.answer(
        "🚗 Подготовка к ПДД\n\n"
        "🎁 5 бесплатных вопросов\n"
        "📊 Проверь уровень\n"
        "🚀 Сдай экзамен с первого раза\n\n"
        "👇 Выбери режим:",
        reply_markup=main_kb()
    )

# ===== MODE =====
@dp.message_handler(lambda m: m.text == "🎯 Тренировка")
async def train(message: types.Message):
    ensure_user(message.from_user.id)
    u = users[str(message.from_user.id)]

    u["mode"] = "train"
    u["waiting_answer"] = False
    
    if not has_access(u):
        await message.answer(
            "🔒 Бесплатные вопросы закончились\n\n"
            "🔥 Купи доступ и готовься без ограничений",
            reply_markup=main_kb()
        )
        return
    # защита от дубля запуска
    if u.get("waiting_answer"):
        return

    await asyncio.sleep(0.3)
    return await send_question(message, u)

@dp.message_handler(lambda m: m.text == "🧠 Экзамен")
async def exam(message: types.Message):
    ensure_user(message.from_user.id)
    u = users[str(message.from_user.id)]

    u["mode"] = "exam"
    u["exam_count"] = 0
    u["exam_correct"] = 0
    u["waiting_answer"] = False

    if not has_access(u):
        await message.answer("🔒 Нет доступа", reply_markup=main_kb())
        return

    await message.answer("🧠 Экзамен: 20 вопросов")

    # защита от дубля запуска
    if u.get("waiting_answer"):
        return

    await asyncio.sleep(0.3)
    return await send_question(message, u)
# ===== BUY =====
@dp.message_handler(lambda m: m.text and "Купить" in m.text)
async def buy(message: types.Message):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("7 дней — 5000₸")
    kb.add("30 дней — 10000₸")
    kb.add("⬅️ Назад")

    await message.answer(
        "💰 Выбери тариф:\n\n"
        "🔥 Безлимитные вопросы\n"
        "🧠 Умные объяснения\n"
        "📈 Быстрый рост результата",
        reply_markup=kb
    )


# ===== PLAN =====
@dp.message_handler(lambda m: m.text and m.text.strip() in ["7 дней — 5000₸", "30 дней — 10000₸"])
async def plan(message: types.Message):
    ensure_user(message.from_user.id)
    u = users[str(message.from_user.id)]

    if "7" in message.text:
        u["plan"] = 7
    else:
        u["plan"] = 30

    save_users()

    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("✅ Я оплатил")
    kb.add("⬅️ Назад")

    await message.answer(
        f"💳 Kaspi: {KASPI}\n\n"
        f"📦 Тариф: {u['plan']} дней\n\n"
        "🔥 Полный доступ:\n"
        "• Безлимитные вопросы\n"
        "• Экзамен без ограничений\n"
        "• Объяснения от AI\n\n"
        "1️⃣ Оплати\n2️⃣ Нажми «Я оплатил»",
        reply_markup=kb
    )


# ===== PAYMENT =====
@dp.message_handler(lambda m: m.text == "✅ Я оплатил")
async def paid(message: types.Message):
    ensure_user(message.from_user.id)
    user = message.from_user
    u = users[str(user.id)]

    if not u.get("plan"):
        await message.answer("❗ Сначала выбери тариф")
        return

    u["status"] = "pending"
    save_users()

    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("7 дней", callback_data=f"give_7_{user.id}"),
        InlineKeyboardButton("30 дней", callback_data=f"give_30_{user.id}")
    )
    kb.add(
        InlineKeyboardButton("❌ Отказать", callback_data=f"deny_{user.id}")
    )

    try:
        now = datetime.now()

        await bot.send_message(
            ADMIN_ID,
            f"📅 {now.strftime('%d.%m.%Y')}\n"
            f"⏰ {now.strftime('%H:%M')}\n\n"
            f"💰 ОПЛАТА\n\n"
            f"👤 @{user.username if user.username else 'нет'}\n"
            f"🆔 ID: {user.id}\n"
            f"📦 Тариф: {u.get('plan')} дней",
            reply_markup=kb
        )

        await message.answer("✅ Отправлено админу на проверку")

    except Exception as e:
        print("ERROR ADMIN:", e)
        await message.answer("❌ Ошибка отправки админу")

# ===== PAYMENT =====
@dp.message_handler(lambda m: m.text == "✅ Я оплатил")
async def paid(message: types.Message):
    user = message.from_user
    u = users.get(str(user.id), {})
    
    u["status"] = "pending"
    users[str(user.id)] = u
    save_users()

    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("7 дней", callback_data=f"give_7_{user.id}"),
        InlineKeyboardButton("30 дней", callback_data=f"give_30_{user.id}")
    )
    kb.add(
        InlineKeyboardButton("❌ Отказать", callback_data=f"deny_{user.id}")
    )

    try:
        now = datetime.now()

        await bot.send_message(
            ADMIN_ID,
            f"📅 {now.strftime('%d.%m.%Y')}\n"
            f"⏰ {now.strftime('%H:%M')}\n\n"
            f"💰 ОПЛАТА\n\n"
            f"👤 @{user.username if user.username else 'нет'}\n"
            f"🆔 ID: {user.id}\n"
            f"🌍 Язык: {user.language_code or 'неизвестно'}\n"
            f"🏙 Город: не определён\n"
            f"📦 Тариф: {u.get('plan', 'не выбран')} дней",
            reply_markup=kb
        )

        await message.answer("✅ Отправлено админу на проверку")

    except Exception as e:
        print("ERROR ADMIN:", e)
        await message.answer("❌ Ошибка отправки админу")

# ===== CALLBACK =====
@dp.callback_query_handler(lambda c: c.data.startswith("give_7_"))
async def give_7(callback: types.CallbackQuery):
    user_id = callback.data.split("_")[2]

    if user_id not in users:
        users[user_id] = {}

    u = users[user_id]

    u["status"] = "active"
    u["plan"] = 7
    u["premium_until"] = (datetime.now() + timedelta(days=7)).isoformat()
    u["used_free"] = 0

    save_users()

    await bot.send_message(user_id, "🔥 Доступ открыт на 7 дней")
    await callback.answer("Выдано 7 дней")


@dp.callback_query_handler(lambda c: c.data.startswith("give_30_"))
async def give_30(callback: types.CallbackQuery):
    user_id = callback.data.split("_")[2]
    u = users.get(user_id, {})
    u["status"] = "active"
    u["plan"] = 30
    u["premium_until"] = (datetime.now() + timedelta(days=30)).isoformat()

    users[user_id] = u
    save_users()

    await bot.send_message(user_id, "🔥 Доступ открыт на 30 дней")
    await callback.answer("Выдано 30 дней")

@dp.callback_query_handler(lambda c: c.data.startswith("deny_"))
async def deny(callback: types.CallbackQuery):
    user_id = callback.data.split("_")[1]

    await bot.send_message(user_id, "❌ Оплата отклонена")
    await callback.answer("Отклонено")
    
# ===== QUESTION =====
async def send_question(message, u):
    if not has_access(u):
        await message.answer(
            "🔒 Бесплатные вопросы закончились\n\n"
            "🔥 Открой полный доступ и готовься без ограничений\n"
            "💯 Сдашь с первого раза",
            reply_markup=main_kb()
        )
        return

    if u.get("waiting_answer"):
        return

    if not u["premium_until"]:
        u["used_free"] += 1

    text, ans, exp = await ask_gpt(message.from_user.id)
    
    u["correct_answer"] = ans
    u["explanation"] = exp
    u["waiting_answer"] = True

    progress = ""
    if u["mode"] == "exam":
        progress = f"\n\n📊 Вопрос {u['exam_count'] + 1}/20"

    await message.answer(text + progress, reply_markup=answer_kb())
    save_users()
# ===== ANSWER =====
@dp.message_handler(lambda m: m.text in ["A","B","C","D"])
async def answer(message: types.Message):
    u = users[str(message.from_user.id)]

    if u.get("processing"):
        return

    u["processing"] = True

    if not u.get("waiting_answer"):
        await message.answer("⏳ Подожди вопрос...")
        u["processing"] = False
        return

    u["waiting_answer"] = False

    if message.text == u["correct_answer"]:
        u["correct"] += 1
        if u["mode"] == "exam":
            u["exam_correct"] += 1
        await message.answer("✅ Верно")
    else:
        u["wrong"] += 1
        await message.answer(f"❌ Неверно\nОтвет: {u['correct_answer']}")

    if u["explanation"]:
        await message.answer(f"📘 {u['explanation'][:200]}")

    await asyncio.sleep(0.3)
    await send_question(message, u)

    u["processing"] = False
    
    # ===== ЭКЗАМЕН =====
    if u["mode"] == "exam":
        u["exam_count"] += 1

        if u["exam_count"] >= 20:
            percent = int(u["exam_correct"] / 20 * 100)

            msg = (
                f"📊 Результат:\n"
                f"{u['exam_correct']}/20\n"
                f"{percent}%\n\n"
            )

            if percent < 80:
                msg += "❌ Не сдал\n\n🔥 Пройди тренировку и попробуй снова"
            else:
                msg += "🔥 Отлично! Ты готов к экзамену"

            await message.answer(msg, reply_markup=main_kb())
            save_users()
            return

    save_users()

    if u["mode"] in ["train", "exam"]:
        await asyncio.sleep(0.4)
        await send_question(message, u)
# ===== BACK =====
@dp.message_handler(lambda m: m.text == "⬅️ Назад")
async def back(message: types.Message):
    ensure_user(message.from_user.id)
    u = users[str(message.from_user.id)]

    u["mode"] = None
    u["waiting_answer"] = False

    save_users()

    await message.answer("🏠 Главное меню", reply_markup=main_kb())
# ===== STATS =====
@dp.message_handler(lambda m: m.text == "📊 Статистика")
async def stats(message: types.Message):
    u = users[str(message.from_user.id)]

    total = u["correct"] + u["wrong"]
    percent = int(u["correct"]/total*100) if total else 0

    await message.answer(
        f"📊 Статистика\n\n"
        f"✅ Правильно: {u['correct']}\n"
        f"❌ Ошибки: {u['wrong']}\n"
        f"📈 Процент: {percent}%"
    )

# ===== RUN =====
if __name__ == "__main__":
    load_users()
    executor.start_polling(dp, skip_updates=True)
