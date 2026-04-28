import os
import json
import random
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup
from aiogram.utils import executor
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# ===== LOAD DATA =====
with open("questions.json", "r", encoding="utf-8") as f:
    questions_db = json.load(f)

try:
    with open("users.json", "r") as f:
        users = json.load(f)
except:
    users = {}
    "user_questions": []

def save():
    with open("users.json", "w") as f:
        json.dump(users, f)

# ===== KEYBOARDS =====
lang_kb = ReplyKeyboardMarkup(resize_keyboard=True)
lang_kb.add("🇷🇺 Русский", "🇰🇿 Қазақша")

def main_kb(lang):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    if lang == "ru":
        kb.add("🚗 Тест", "🧠 Экзамен")
        kb.add("📊 Статистика", "📚 Обучение")
    else:
        kb.add("🚗 Тест", "🧠 Емтихан")
        kb.add("📊 Статистика", "📚 Оқу")
    return kb

def answers_kb(lang):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("A", "B", "C", "D")
    kb.add("⬅️ Назад" if lang == "ru" else "⬅️ Артқа")
    return kb

# ===== START =====
@dp.message_handler(commands=["start"])
async def start(msg: types.Message):
    uid = str(msg.from_user.id)

    users[uid] = {
        "lang": None,
        "mode": None,
        "queue": [],
        "stats": {"correct": 0, "wrong": 0},
        "exam": {"q": 0, "errors": 0},
        "mistakes": []
    }
    save()

    await msg.answer("Выбери язык / Тілді таңда:", reply_markup=lang_kb)

# ===== LANG =====
@dp.message_handler(lambda m: m.text in ["🇷🇺 Русский", "🇰🇿 Қазақша"])
async def lang(msg: types.Message):
    uid = str(msg.from_user.id)
    users[uid]["lang"] = "ru" if "Русский" in msg.text else "kz"
    save()

    await msg.answer("Выбери режим", reply_markup=main_kb(users[uid]["lang"]))

# ===== TEST =====
@dp.message_handler(lambda m: "Тест" in m.text)
async def test(msg: types.Message):
    uid = str(msg.from_user.id)

    users[uid]["mode"] = "test"
    users[uid]["queue"] = random.sample(questions_db, len(questions_db))
    save()

    await send_q(msg)

# ===== EXAM =====
@dp.message_handler(lambda m: "Экзамен" in m.text or "Емтихан" in m.text)
async def exam(msg: types.Message):
    uid = str(msg.from_user.id)

    users[uid]["mode"] = "exam"
    users[uid]["exam"] = {"q": 0, "errors": 0}
    users[uid]["queue"] = random.sample(questions_db, 20)
    save()

    await msg.answer("20 вопросов / 3 ошибки = провал")
    await send_q(msg)

# ===== SEND QUESTION =====
async def send_question(msg):
    uid = str(msg.from_user.id)
    user = users[uid]
    lang = user["lang"]

    await bot.send_chat_action(msg.chat.id, "typing")

    used = user.get("used_questions", [])

    available = [q for i, q in enumerate(questions_db) if i not in used]

    if not available:
        await msg.answer("Вопросы закончились" if lang == "ru" else "Сұрақтар аяқталды")
        user["mode"] = None
        user["used_questions"] = []
        save_users()
        return

    index = questions_db.index(random.choice(available))
    q = questions_db[index]

    user["used_questions"].append(index)
    user["last_question"] = q

    if user["mode"] == "exam":
        user["exam"]["q"] += 1

    save_users()

    question = q["q_kz"] if lang == "kz" else q["q_ru"]
    options = q["options_kz"] if lang == "kz" else q["options_ru"]

    await msg.answer(
        f"{question}\n\n" + "\n".join(options),
        reply_markup=get_answers_kb(lang)
    )

# ===== ANSWER =====
@dp.message_handler(lambda m: m.text in ["A", "B", "C", "D"])
async def answer(msg: types.Message):
    uid = str(msg.from_user.id)
    user = users[uid]
    lang = user["lang"]
    q = user["last"]
    if user.get("mode") is None:
    return

    if msg.text == q["correct"]:
        user["stats"]["correct"] += 1
        text = "✅ Правильно!" if lang == "ru" else "✅ Дұрыс!"
    else:
        user["stats"]["wrong"] += 1
        user["mistakes"].append(q)
        text = f"❌ Ответ: {q['correct']}"

        if user["mode"] == "exam":
            user["exam"]["errors"] += 1

    explanation = q["ex_ru"] if lang == "ru" else q["ex_kz"]

    await msg.answer(f"{text}\n\n{explanation}")

    # экзамен логика
    if user["mode"] == "exam":
        if user["exam"]["errors"] >= 3:
            await msg.answer("❌ Провал")
            return

        if user["exam"]["q"] >= 20:
            await msg.answer("🎉 Сдал!")
            return

    save()
    await send_q(msg)

# ===== STATS =====
@dp.message_handler(lambda m: "Статистика" in m.text)
async def stats(msg: types.Message):
    uid = str(msg.from_user.id)
    
    s = users[uid]["stats"]
    users[uid]["used_questions"] = []

    await msg.answer(f"✅ {s['correct']} | ❌ {s['wrong']}")

# ===== AI TRAINER =====
@dp.message_handler(lambda m: "Обучение" in m.text or "Оқу" in m.text)
async def ai(msg: types.Message):
    uid = str(msg.from_user.id)
    mistakes = users[uid]["mistakes"][-3:]

    text = "Объясни ошибки:\n" + "\n".join([q["q_ru"] for q in mistakes])

    res = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": text}]
    )

    await msg.answer(res.choices[0].message.content)

# ===== RUN =====
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
