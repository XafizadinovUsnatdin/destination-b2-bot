import telebot
import sqlite3
import random

# Bot tokenini o'rnating
API_TOKEN = '7862259394:AAEa6K0__-9CzuTHyIS6jT1vLeZGB9Hm2NE'
bot = telebot.TeleBot(API_TOKEN)

# Ma'lumotlar bazasi bilan ishlash
conn = sqlite3.connect('vocabulary.db', check_same_thread=False)
cursor = conn.cursor()

# Jadval yaratish
cursor.execute('''
    CREATE TABLE IF NOT EXISTS units (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE
    )
''')
cursor.execute('''
    CREATE TABLE IF NOT EXISTS sections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        unit_id INTEGER,
        name TEXT,
        FOREIGN KEY (unit_id) REFERENCES units(id)
    )
''')
cursor.execute('''
    CREATE TABLE IF NOT EXISTS vocabulary (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        section_id INTEGER,
        english_word TEXT,
        definition TEXT,
        FOREIGN KEY (section_id) REFERENCES sections(id)
    )
''')
conn.commit()

# Global o'zgaruvchilar
ADMIN_IDS = [1221779366]  # Admin ID larni qo'shing
user_states = {}  # Foydalanuvchi holatlari

# Boshlash
@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id
    if chat_id in ADMIN_IDS:
        bot.send_message(chat_id, "Welcome, Admin! You can:\n"
                                  "1. Add a new unit (Format: `New Unit: unit_name`)\n"
                                  "2. Add a new section (Format: `New Section: unit_name - section_name`)\n"
                                  "3. Add vocabulary (Format: `unit_name - section_name: word – definition`)")
    else:
        units = get_units()
        if not units:
            bot.send_message(chat_id, "No units available yet. Please contact the admin.")
        else:
            user_states[chat_id] = {"stage": "selecting_unit"}
            markup = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
            for unit in units:
                markup.add(unit)
            bot.send_message(chat_id, "Welcome! Select a unit to start the quiz:", reply_markup=markup)

# Admin yangi unit qo'shadi
@bot.message_handler(func=lambda msg: msg.text.startswith("New Unit:"))
def add_unit(message):
    if message.chat.id not in ADMIN_IDS:
        bot.send_message(message.chat.id, "You don't have permission to add units.")
        return

    unit_name = message.text.replace("New Unit:", "").strip()
    try:
        cursor.execute("INSERT INTO units (name) VALUES (?)", (unit_name,))
        conn.commit()
        bot.send_message(message.chat.id, f"✅ Unit '{unit_name}' added successfully.")
    except sqlite3.IntegrityError:
        bot.send_message(message.chat.id, f"❌ Unit '{unit_name}' already exists!")

# Admin yangi bo'lim qo'shadi
@bot.message_handler(func=lambda msg: msg.text.startswith("New Section:"))
def add_section(message):
    if message.chat.id not in ADMIN_IDS:
        bot.send_message(message.chat.id, "You don't have permission to add sections.")
        return

    try:
        unit_name, section_name = map(str.strip, message.text.replace("New Section:", "").split("-"))
        cursor.execute("SELECT id FROM units WHERE name = ?", (unit_name,))
        unit = cursor.fetchone()
        if not unit:
            bot.send_message(message.chat.id, f"❌ Unit '{unit_name}' does not exist!")
            return

        cursor.execute("INSERT INTO sections (unit_id, name) VALUES (?, ?)", (unit[0], section_name))
        conn.commit()
        bot.send_message(message.chat.id, f"✅ Section '{section_name}' added to unit '{unit_name}'.")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error adding section: {e}")

# Admin bir nechta so‘zlarni bir vaqtning o‘zida qo‘shadi
@bot.message_handler(func=lambda msg: ":" in msg.text and "–" in msg.text)
def add_multiple_vocabularies(message):
    if message.chat.id not in ADMIN_IDS:
        bot.send_message(message.chat.id, "You don't have permission to add vocabulary.")
        return

    try:
        unit_section, vocab_entries = map(str.strip, message.text.split(":", 1))
        unit_name, section_name = map(str.strip, unit_section.split("-", 1))

        cursor.execute("SELECT sections.id FROM sections JOIN units ON sections.unit_id = units.id WHERE units.name = ? AND sections.name = ?", (unit_name, section_name))
        section = cursor.fetchone()
        if not section:
            bot.send_message(message.chat.id, f"❌ Section '{section_name}' in unit '{unit_name}' does not exist!")
            return

        vocab_list = vocab_entries.strip().split("\n")
        added_count = 0
        for vocab_entry in vocab_list:
            if "–" in vocab_entry:
                word, definition = map(str.strip, vocab_entry.split("–", 1))
                cursor.execute("INSERT INTO vocabulary (section_id, english_word, definition) VALUES (?, ?, ?)", (section[0], word, definition))
                added_count += 1

        conn.commit()
        bot.send_message(message.chat.id, f"✅ Added {added_count} vocabularies to section '{section_name}' in unit '{unit_name}'.")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Error adding vocabulary: {e}")

# Unitlarni olish funksiyasi
def get_units():
    cursor.execute("SELECT name FROM units")
    return [row[0] for row in cursor.fetchall()]

# Section (bo'lim)larni olish funksiyasi
def get_sections(unit_name):
    cursor.execute("SELECT sections.name FROM sections JOIN units ON sections.unit_id = units.id WHERE units.name = ?", (unit_name,))
    return [row[0] for row in cursor.fetchall()]

# Foydalanuvchi unitni tanlaydi
@bot.message_handler(func=lambda msg: msg.text in get_units())
def select_unit(message):
    chat_id = message.chat.id
    unit_name = message.text

    sections = get_sections(unit_name)
    if not sections:
        bot.send_message(chat_id, "No sections available in this unit. Please contact the admin.")
        return

    user_states[chat_id] = {"stage": "selecting_section", "unit": unit_name}
    markup = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    for section in sections:
        markup.add(section)
    bot.send_message(chat_id, "Select a section:", reply_markup=markup)

# Foydalanuvchi bo'limni tanlaydi
@bot.message_handler(func=lambda msg: user_states.get(msg.chat.id, {}).get("stage") == "selecting_section")
def select_section(message):
    chat_id = message.chat.id
    section_name = message.text
    unit_name = user_states[chat_id]["unit"]

    cursor.execute("""
        SELECT vocabulary.english_word, vocabulary.definition
        FROM vocabulary
        JOIN sections ON vocabulary.section_id = sections.id
        JOIN units ON sections.unit_id = units.id
        WHERE units.name = ? AND sections.name = ?
    """, (unit_name, section_name))
    vocabularies = cursor.fetchall()

    if not vocabularies:
        bot.send_message(chat_id, "No vocabularies found in this section. Please contact the admin.")
        return

    user_states[chat_id] = {
        "stage": "in_quiz",
        "unit": unit_name,
        "section": section_name,
        "vocabularies": vocabularies,
        "current_index": 0,
        "score": 0
    }
    ask_question(chat_id)

# Savol berish funksiyasi
def ask_question(chat_id):
    state = user_states[chat_id]
    vocabularies = state["vocabularies"]
    current_index = state["current_index"]

    if current_index >= len(vocabularies):
        score = state["score"]
        total = len(vocabularies)
        bot.send_message(chat_id, f"✅ Quiz finished! Your score: {score}/{total}")

        # Barcha unitlardan tanlash qismiga qaytish
        units = get_units()
        if units:
            user_states[chat_id] = {"stage": "selecting_unit"}
            markup = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
            for unit in units:
                markup.add(unit)
            bot.send_message(chat_id, "📚 Select a unit to start a new quiz:", reply_markup=markup)
        else:
            bot.send_message(chat_id, "❌ No units available. Please contact the admin.")
        return

    word, correct_definition = vocabularies[current_index]
    incorrect_definitions = [v[1] for v in vocabularies if v[1] != correct_definition]
    options = [correct_definition] + random.sample(incorrect_definitions, min(3, len(incorrect_definitions)))
    random.shuffle(options)

    markup_def = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    for option in options:
        markup_def.add(option)

    bot.send_message(chat_id, f"🔍 What is the definition of '{word}'?", reply_markup=markup_def)

# Javobni tekshirish
@bot.message_handler(func=lambda msg: user_states.get(msg.chat.id, {}).get("stage") == "in_quiz")
def check_answer(message):
    chat_id = message.chat.id
    state = user_states[chat_id]
    vocabularies = state["vocabularies"]
    current_index = state["current_index"]

    word, correct_definition = vocabularies[current_index]
    if message.text == correct_definition:
        state["score"] += 1
        bot.send_message(chat_id, "✅ Correct!")
    else:
        bot.send_message(chat_id, f"❌ Wrong! The correct answer was: {correct_definition}")

    state["current_index"] += 1
    ask_question(chat_id)

# Botni ishga tushirish
bot.polling(none_stop=True)
