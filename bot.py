import os
import logging
import json
from datetime import datetime, timedelta
import re

from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
from openai import OpenAI

# ===== CONFIG =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

ADMIN_ID = 8398266271
KASPI = "4400430352720152"

MODEL = "gpt-4o-mini"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
client = OpenAI(api_key=OPENAI_API_KEY)

logging.basicConfig(level=logging.INFO)

users = {}

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
def ensure_user(uid, lang_code=None):
    uid = str(uid)

    if uid not in users:
        # авто-определение языка
        lang = "ru"
        if lang_code:
            if "kk" in lang_code:
                lang = "kz"
            elif "ru" in lang_code:
                lang = "ru"

        users[uid] = {
            "lang": lang,
            "mode": None,
            "correct_answer": None,
            "explanation": "",
            "free_limit": 5,
            "used_free": 0,
            "premium_until": None,
            "plan": None,
            "correct": 0,
            "wrong": 0
        }
        save_users()

def has_access(u):
    try:
        if u["premium_until"] and datetime.now() < datetime.fromisoformat(u["premium_until"]):
            return True
    except:
        pass
    return u["used_free"] < u["free_limit"]

# ===== TEXT =====
def t(u, ru, kz):
    return ru if u["lang"] == "ru" else kz

# ===== UI =====
def main_kb(u):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(t(u,"🎯 Тренировка","🎯 Жаттығу"), t(u,"🧠 Экзамен","🧠 Емтихан"))
    kb.add(t(u,"📊 Статистика","📊 Статистика"), t(u,"🌐 Язык","🌐 Тіл"))
    kb.add(t(u,"💳 Купить доступ","💳 Сатып алу"))
    return kb

def answer_kb(u):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("A","B","C","D")
    kb.add(t(u,"⬅️ Назад","⬅️ Артқа"))
    return kb

def pay_kb(u):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(t(u,"💰 Купить доступ","💰 Сатып алу"))
    kb.add(t(u,"⬅️ Назад","⬅️ Артқа"))
    return kb

# ===== GPT =====
def ask_gpt():
    prompt = """
Сделай экзаменационный вопрос ПДД Казахстан.
Формат строго:

Вопрос:
...

A) ...
B) ...
C) ...
D) ...

Правильный ответ: A
Объяснение: кратко
"""
    r = client.chat.completions.create(
        model=MODEL,
        messages=[{"role":"user","content":prompt}]
    )

    text = r.choices[0].message.content

    ans = re.search(r"Правильный ответ[:\s]*([ABCD])", text)
    exp = re.search(r"Объяснение[:\s]*(.*)", text, re.S)

    return text, ans.group(1) if ans else "A", exp.group(1).strip() if exp else ""

# ===== START =====
@dp.message_handler(commands=['start'])
async def start(message: types.Message):

    ensure_user(
        message.from_user.id,
        message.from_user.language_code
    )

    u = users[str(message.from_user.id)]

    # авто-язык
    lang_code = message.from_user.language_code or ""
    if "ru" in lang_code:
        u["lang"] = "ru"
    else:
        u["lang"] = "kz"

    save_users()

    await message.answer(
        "🌐 Язык: Русский" if u["lang"] == "ru" else "🌐 Тіл: Қазақша"
    )

    await message.answer(
        t(u,
          "🚗 Подготовка к ПДД\n\n"
          "👇 Выбери режим:",
          "🚗 ПДД дайындық\n\n"
          "👇 Режимді таңда:"
        ),
        reply_markup=main_kb(u)
    )

@dp.message_handler(lambda m: "Язык" in m.text or "Тіл" in m.text)
async def lang(message: types.Message):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🇷🇺 Русский", "🇰🇿 Қазақша")
    kb.add("⬅️ Назад", "⬅️ Артқа")

    await message.answer("Выбери язык / Тілді таңда:", reply_markup=kb)


@dp.message_handler(lambda m: "Русский" in m.text or "Қазақша" in m.text)
async def set_lang(message: types.Message):
    u = users[str(message.from_user.id)]

    if "Рус" in message.text:
        u["lang"] = "ru"
    else:
        u["lang"] = "kz"

    save_users()

    await message.answer("✅", reply_markup=main_kb(u))
    
# ===== MODE =====
@dp.message_handler(lambda m: "Тренировка" in m.text or "Жаттығу" in m.text)
async def train(message: types.Message):
    u = users[str(message.from_user.id)]
    u["mode"] = "train"

    if not has_access(u):
        await limit_message(message, u)
        return

    await send_question(message, u)

@dp.message_handler(lambda m: "Экзамен" in m.text or "Емтихан" in m.text)
async def exam(message: types.Message):
    u = users[str(message.from_user.id)]
    u["mode"] = "exam"
    u["exam_count"] = 0
    u["exam_correct"] = 0

    await message.answer("🧠 Экзамен начался (20 вопросов)")
    await send_question(message, u)

# ===== LIMIT =====
async def limit_message(message, u):
    await message.answer(
        "🔒 Бесплатные вопросы закончились\n\n"
        f"📊 Ты ответил: {u['correct']} правильно\n"
        "🚗 Рекомендуем довести до 90%\n\n"
        "💰 Доступ:\n"
        "7 дней — 5000₸\n"
        "30 дней — 10000₸",
        reply_markup=pay_kb(u)
    )

# ===== BUY =====
@dp.message_handler(lambda m: "Купить" in m.text or "Сатып" in m.text)
async def buy(message: types.Message):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("7 дней — 5000₸")
    kb.add("30 дней — 10000₸")
    kb.add("⬅️ Назад", "⬅️ Артқа")

    await message.answer("💰 Выбери тариф:", reply_markup=kb)


# ===== BACK =====
@dp.message_handler(lambda m: "Назад" in m.text or "Артқа" in m.text)
async def back(message: types.Message):
    u = users[str(message.from_user.id)]
    await message.answer("🏠 Главное меню", reply_markup=main_kb(u))


# ===== PLAN =====
@dp.message_handler(lambda m: "дней" in m.text)
async def plan(message: types.Message):
    u = users[str(message.from_user.id)]

    if "7" in message.text:
        u["plan"] = 7
    elif "30" in message.text:
        u["plan"] = 30

    save_users()

    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("💰 Оплатил")
    kb.add("⬅️ Назад", "⬅️ Артқа")

    await message.answer(
        f"💳 Kaspi: {KASPI}\n\n"
        f"📦 Тариф: {u['plan']} дней\n\n"
        "📸 После оплаты нажми '💰 Оплатил' и отправь чек",
        reply_markup=kb
    )


# ===== PAID =====
@dp.message_handler(lambda m: "Оплатил" in m.text or "Төледім" in m.text)
async def paid(message: types.Message):
    u = users[str(message.from_user.id)]

    if not u.get("plan"):
        await message.answer("Сначала выбери тариф")
        return

    await message.answer("📸 Отправь чек (скрин)")


# ===== PHOTO (САМОЕ ВАЖНОЕ) =====
@dp.message_handler(content_types=types.ContentType.PHOTO)
async def receipt(message: types.Message):
    user = message.from_user
    u = users[str(user.id)]

    await bot.send_photo(
        ADMIN_ID,
        message.photo[-1].file_id,
        caption=f"💰 Оплата\nID: {user.id}\nТариф: {u.get('plan')}",
        reply_markup=InlineKeyboardMarkup().add(
            InlineKeyboardButton("✅ Дать доступ", callback_data=f"give_{user.id}")
        )
    )
    await message.answer("⏳ Чек отправлен на проверку")
    
@dp.callback_query_handler(lambda c: c.data.startswith("give_"))
async def give(callback: types.CallbackQuery):
    uid = callback.data.split("_")[1]
    days = users[uid].get("plan", 7)

    users[uid]["premium_until"] = (datetime.now()+timedelta(days=days)).isoformat()
    save_users()

    await bot.send_message(uid, "🔥 Доступ открыт!")
    await callback.answer("OK")

# ===== QUESTION =====
async def send_question(message, u):
    if not has_access(u):
        await limit_message(message, u)
        return

    if not u["premium_until"]:
        u["used_free"] += 1

    text, ans, exp = ask_gpt()

    u["correct_answer"] = ans
    u["explanation"] = exp

    clean = re.sub(r"Правильный ответ.*", "", text, flags=re.S)
    clean = re.sub(r"Объяснение.*", "", clean, flags=re.S)

    await message.answer(clean, reply_markup=answer_kb(u))
    save_users()

# ===== ANSWER =====
@dp.message_handler(lambda m: m.text in ["A","B","C","D"])
async def answer(message: types.Message):
    u = users[str(message.from_user.id)]

    if message.text == u["correct_answer"]:
        u["correct"] += 1
        await message.answer("✅ Верно")
    else:
        u["wrong"] += 1
        await message.answer(f"❌ Неверно\nОтвет: {u['correct_answer']}")

    if u["explanation"]:
        await message.answer(f"📘 {u['explanation'][:300]}")

    if u.get("mode") == "exam":
        u["exam_count"] += 1
        if message.text == u["correct_answer"]:
            u["exam_correct"] += 1

        if u["exam_count"] >= 20:
            await message.answer(
                f"📊 Результат:\n"
                f"{u['exam_correct']} / 20"
            )
            return

    await send_question(message, u)

# ===== STATS =====
@dp.message_handler(lambda m: "Статистика" in m.text)
async def stats(message: types.Message):
    u = users[str(message.from_user.id)]

    await message.answer(
        f"📊 Статистика\n\n"
        f"✅ Правильно: {u['correct']}\n"
        f"❌ Ошибки: {u['wrong']}\n"
        f"💎 Подписка до: {u['premium_until'] or 'нет'}"
    )

# ===== RUN =====
if __name__ == "__main__":
    load_users()
    executor.start_polling(dp, skip_updates=True)
