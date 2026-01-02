import telebot
from telebot import types
import sqlite3
from datetime import datetime

BOT_TOKEN = "8273792973:AAEJT7SZL6RjaIJW6jUfGppGqrDeAm0VtaA"
ADMIN_ID = 1577850433
ADMIN_CODE = "ADMIN123"


bot = telebot.TeleBot(BOT_TOKEN)

# ------------------ БАЗА ------------------
db = sqlite3.connect("orders.db", check_same_thread=False)
sql = db.cursor()
sql.execute("""
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT,
    for_whom TEXT,
    functions TEXT,
    description TEXT,
    price TEXT,
    status TEXT,
    created TEXT
)
""")
db.commit()

user_states = {}
admin_mode = set()
reply_temp = {}

# ------------------ КЛАВИАТУРЫ ------------------
def user_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📂 Примеры", "🛒 Заказать бота", "🤖 О ботах")
    return kb

# ------------------ START ------------------
@bot.message_handler(commands=["start"])
def start(m):
    bot.send_message(m.chat.id, "👋 Привет!\nЯ делаю Telegram-ботов.\nВыбери действие 👇", reply_markup=user_kb())

# ------------------ ПРИМЕРЫ ------------------
@bot.message_handler(func=lambda m: m.text == "📂 Примеры")
def examples(m):
    bot.send_message(m.chat.id,
        "📌 Примеры:\n"
        "1️⃣ Бот заявок\n"
        "2️⃣ Магазин-бот\n"
        "3️⃣ Instagram-бот")

# ------------------ О БОТАХ ------------------
@bot.message_handler(func=lambda m: m.text == "🤖 О ботах")
def about(m):
    bot.send_message(m.chat.id,
        "🤖 Боты работают 24/7\n"
        "✔ автоматизация\n"
        "✔ экономия времени\n"
        "✔ рост клиентов")

# ------------------ ЗАКАЗ ------------------
@bot.message_handler(func=lambda m: m.text == "🛒 Заказать бота")
def order_start(m):
    user_states[m.chat.id] = {"step": 1}
    bot.send_message(m.chat.id, "Для кого бот?")

@bot.message_handler(func=lambda m: m.chat.id in user_states)
def order_steps(m):
    state = user_states[m.chat.id]
    if state["step"] == 1:
        state["for_whom"] = m.text
        state["step"] = 2
        bot.send_message(m.chat.id, "Какой функционал?")
    elif state["step"] == 2:
        state["functions"] = m.text
        state["step"] = 3
        bot.send_message(m.chat.id, "Описание бота")
    elif state["step"] == 3:
        state["description"] = m.text
        state["step"] = 4
        bot.send_message(m.chat.id, "Бюджет (₸)")
    elif state["step"] == 4:
        sql.execute(
            "INSERT INTO orders VALUES (NULL,?,?,?,?,?,?,?,?)",
            (
                m.chat.id,
                m.from_user.username,
                state["for_whom"],
                state["functions"],
                state["description"],
                m.text,
                "🟡 Новая",
                datetime.now().strftime("%d.%m.%Y %H:%M")
            )
        )
        db.commit()
        user_states.pop(m.chat.id)
        bot.send_message(m.chat.id, "✅ Заявка отправлена!")

# ------------------ ВХОД В АДМИНКУ ------------------
@bot.message_handler(func=lambda m: m.text == ADMIN_CODE and m.chat.id == ADMIN_ID)
def admin_login(m):
    admin_mode.add(m.chat.id)
    send_admin_dashboard(m.chat.id)

# ------------------ ФУНКЦИИ АДМИН ------------------
def send_admin_dashboard(chat_id):
    rows = sql.execute("SELECT id, username, for_whom, functions, description, price, status FROM orders").fetchall()
    if not rows:
        bot.send_message(chat_id, "Нет заявок")
        return
    for r in rows:
        msg = (f"🆔 ID: {r[0]}\n"
               f"👤 @{r[1]}\n"
               f"📌 Для кого: {r[2]}\n"
               f"⚙ Функционал: {r[3]}\n"
               f"📝 Описание: {r[4]}")
        bot.send_message(chat_id, msg)
        bot.send_message(chat_id, f"💰 Цена: {r[5]} ₸\n📊 Статус: {r[6]}",
                         reply_markup=order_buttons(r[0]))

def order_buttons(order_id):
    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton("✉️ Ответить", callback_data=f"reply_{order_id}"),
        types.InlineKeyboardButton("🔄 Статус", callback_data=f"status_{order_id}"),
        types.InlineKeyboardButton("❌ Отменить", callback_data=f"cancel_{order_id}")
    )
    return kb

# ------------------ CALLBACK ------------------
@bot.callback_query_handler(func=lambda c: True)
def inline_buttons(c):
    if c.data.startswith("reply_") and c.message.chat.id == ADMIN_ID:
        order_id = int(c.data.split("_")[1])
        reply_temp[c.message.chat.id] = order_id
        bot.send_message(c.message.chat.id, "Напишите ответ клиенту:")
    elif c.data.startswith("status_") and c.message.chat.id == ADMIN_ID:
        order_id = int(c.data.split("_")[1])
        bot.send_message(c.message.chat.id, f"Введите новый статус для заявки {order_id} (например: В работе)")
        reply_temp[c.message.chat.id] = f"status_{order_id}"
    elif c.data.startswith("cancel_") and c.message.chat.id == ADMIN_ID:
        order_id = int(c.data.split("_")[1])
        sql.execute("UPDATE orders SET status='❌ Отменён' WHERE id=?", (order_id,))
        db.commit()
        bot.send_message(c.message.chat.id, f"❌ Заявка {order_id} отменена")

# ------------------ ОБРАБОТКА СООБЩЕНИЙ ОТ АДМИНА ------------------
@bot.message_handler(func=lambda m: m.chat.id in reply_temp)
def process_admin_reply(m):
    data = reply_temp[m.chat.id]
    if isinstance(data, int):
        # Ответ клиенту
        user_id = sql.execute("SELECT user_id FROM orders WHERE id=?", (data,)).fetchone()
        if user_id:
            bot.send_message(user_id[0], f"✉️ Ответ:\n{m.text}")
            bot.send_message(m.chat.id, "✅ Отправлено клиенту")
        reply_temp.pop(m.chat.id)
    elif isinstance(data, str) and data.startswith("status_"):
        order_id = int(data.split("_")[1])
        sql.execute("UPDATE orders SET status=? WHERE id=?", (m.text, order_id))
        db.commit()
        bot.send_message(m.chat.id, f"✅ Статус заявки {order_id} обновлён")
        reply_temp.pop(m.chat.id)

# ------------------ RUN ------------------
import time

while True:
    try:
        bot.polling(none_stop=True)
    except Exception as e:
        print("Ошибка подключения к Telegram:", e)
        time.sleep(5)  # ждём 5 секунд и пробуем снова


