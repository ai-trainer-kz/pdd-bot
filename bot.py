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

def save():
    with open("users.json", "w") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

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

    users[uid] = users.get(uid, {
    "lang": None,
    "mode": None,
    "stats": {"correct": 0, "wrong": 0},
    "exam": {"q": 0, "errors": 0},
    "used_questions": [],
    "mistakes": []
})

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

# ===== LANGUAGE =====
@dp.message_handler(lambda m: m.text in ["🇷🇺 Русский", "🇰🇿 Қазақша"])
async def lang(msg: types.Message):
    uid = str(msg.from_user.id)
    users[uid]["lang"] = "ru" if "Русский" in msg.text else "kz"
    save()

    await msg.answer("Выбери режим", reply_markup=main_kb(users[uid]["lang"]))

# ===== TEST =====
@dp.message_handler(lambda msg: "Тест ПДД" in msg.text)
async def test(msg: types.Message):
    uid = str(msg.from_user.id)
    user = users[uid]

    if user.get("mode") == "test":
        return

    user["mode"] = "test"
    user["used_questions"] = []

    save_users()

    await send_question(msg)

# ===== EXAM =====
@dp.message_handler(lambda msg: "Экзамен" in msg.text or "Емтихан" in msg.text)
async def exam(msg: types.Message):
    uid = str(msg.from_user.id)
    user = users[uid]
    lang = user["lang"]

    # ❗ если уже в режиме — не даём перезапуск
    if user.get("mode") == "exam":
        await msg.answer("Экзамен уже запущен" if lang == "ru" else "Емтихан басталған")
        return

    user["mode"] = "exam"
    user["exam"] = {"q": 0, "errors": 0}
    user["used_questions"] = []

    save_users()

    await msg.answer("20 вопросов / 3 ошибки = провал" if lang == "ru"
                     else "20 сұрақ / 3 қате = құлау")

    await send_question(msg)

# ===== BACK =====
@dp.message_handler(lambda m: m.text in ["⬅️ Назад", "⬅️ Артқа"])
async def back(msg: types.Message):
    uid = str(msg.from_user.id)
    lang = users[uid]["lang"]

    users[uid]["mode"] = None
    users[uid]["queue"] = []
    save()

    await msg.answer("Главное меню" if lang == "ru" else "Басты мәзір",
                     reply_markup=main_kb(lang))

# ===== SEND QUESTION =====
async def send_question(msg):
    uid = str(msg.from_user.id)
    user = users[uid]
    lang = user["lang"]

    used = user.get("used_questions", [])

    available = [i for i in range(len(questions_db)) if i not in used]

    if not available:
        await msg.answer("Вопросы закончились" if lang == "ru" else "Сұрақтар аяқталды")
    
        user["mode"] = None
        user["used_questions"] = []
        user["exam"] = {"q": 0, "errors": 0}
    
        save_users()
        return

    index = random.choice(available)
    q = questions_db[index]

    user["used_questions"].append(index)
    user["last_question"] = q

    if user["mode"] == "exam":
        user["exam"]["q"] += 1

    save_users()

    text = (q["q_kz"] if lang == "kz" else q["q_ru"]) + "\n\n"
    text += "\n".join(q["options_kz"] if lang == "kz" else q["options_ru"])

    await msg.answer(text, reply_markup=get_answers_kb(lang))
# ===== ANSWER =====
@dp.message_handler(lambda m: m.text in ["A", "B", "C", "D"])
async def answer(msg: types.Message):
    uid = str(msg.from_user.id)
    user = users.get(uid)
    if user.get("mode") not in ["test", "exam"]:
        return

    if user.get("mode") is None:
        return

    if not user or user.get("mode") is None:
        return

    lang = user["lang"]
    q = user["last_question"]

    await bot.send_chat_action(msg.chat.id, "typing")

    if msg.text == q["correct"]:
        user["stats"]["correct"] += 1
        text = "✅ Правильно!" if lang == "ru" else "✅ Дұрыс!"
    else:
        user["stats"]["wrong"] += 1
        user["mistakes"].append(q)
        text = f"❌ Ответ: {q['correct']}" if lang == "ru" else f"❌ Дұрыс жауап: {q['correct']}"

        if user["mode"] == "exam":
            user["exam"]["errors"] += 1

    explanation = q["ex_ru"] if lang == "ru" else q["ex_kz"]

    await msg.answer(f"{text}\n\n{explanation}")

    # ===== EXAM LOGIC =====
    if user["mode"] == "exam":
        if user["exam"]["errors"] >= 3:
            await msg.answer("❌ Провал" if lang == "ru" else "❌ Құладың")
            user["mode"] = None
            save()
            return

        if user["exam"]["q"] >= 20:
            await msg.answer("🎉 Сдал!" if lang == "ru" else "🎉 Өттің!")
            user["mode"] = None
            save()
            return

        if msg.text != correct:
            user["mistakes"].append(q)

    save()
    await send_question(msg)

# ===== STATS =====
@dp.message_handler(lambda m: "Статистика" in m.text)
async def stats(msg: types.Message):
    uid = str(msg.from_user.id)
    s = users[uid]["stats"]

    await msg.answer(f"✅ {s['correct']} | ❌ {s['wrong']}")

# ===== AI TRAINER =====
@dp.message_handler(lambda msg: "Обучение" in msg.text or "Оқу" in msg.text)
async def training(msg: types.Message):
    uid = str(msg.from_user.id)
    user = users[uid]
    lang = user["lang"]

    mistakes = user.get("mistakes", [])

    if not mistakes:
        await msg.answer("Нет ошибок для разбора" if lang == "ru" else "Қателер жоқ")
        return

    text = "Разбор ошибок:\n\n" if lang == "ru" else "Қателер талдауы:\n\n"

    for q in mistakes[-5:]:
        text += f"{q['q_ru' if lang=='ru' else 'q_kz']}\n"
        text += f"👉 {q['ex_ru' if lang=='ru' else 'ex_kz']}\n\n"

    await msg.answer(text)

# ===== RUN =====
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
