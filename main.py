import logging
import json
import os
from dotenv import load_dotenv
import threading
from datetime import datetime, timedelta
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters, ConversationHandler

# Load environment variables
load_dotenv()

# Enhanced logging configuration
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[logging.FileHandler("bot.log"),
              logging.StreamHandler()])
logger = logging.getLogger(__name__)

# States for conversation
SUBJECT, WORK_TIME, BREAK_TIME, START_TIME, END_TIME, RUNNING = range(6)

# Constants
MIN_WORK_TIME = 5
MAX_WORK_TIME = 120
MIN_BREAK_TIME = 1
MAX_BREAK_TIME = 60

# Store active timers
active_timers = {}

# User data file path
USER_DATA_FILE = "user_data.json"

# Predefined emoji sets
SUBJECT_EMOJIS = {
    "Русский язык": "📚",
    "История Беларуси": "🏛️",
    "Биология": "🧬",
    "Математика": "🔢",
    "Химия": "⚗️",
    "Физика": "⚛️",
    "Английский язык": "🌐",
    "Литература": "📖",
    "Информатика": "💻",
    "География": "🌍",
    "Обществознание": "👥"
}

# Default emoji for custom subjects
DEFAULT_CUSTOM_EMOJI = "📝"

# Help messages
HELP_MESSAGES = {
    "main": (
        "🔍 *Помощь по использованию бота*\n\n"
        "*Основные команды:*\n"
        "• /start - Начать новую сессию\n"
        "• /stop - Остановить текущий таймер\n"
        "• /stats - Показать статистику\n"
        "• /help - Показать эту справку\n\n"
        "*Как использовать:*\n"
        "1. Нажми /start, чтобы начать новую сессию\n"
        "2. Выбери предмет для изучения или добавь новый\n"
        "3. Укажи время работы (25-45 минут рекомендуется)\n"
        "4. Укажи время отдыха (5-15 минут рекомендуется)\n"
        "5. Выбери время начала и окончания\n"
        "6. Бот будет автоматически чередовать периоды работы и отдыха\n\n"
        "*Управление таймером:*\n"
        "• ⏸️ Пауза - приостановить таймер\n"
        "• ▶️ Продолжить - возобновить таймер после паузы\n"
        "• ⏭️ Пропустить отдых - перейти к следующему рабочему интервалу\n"
        "• ⏹️ Остановить - полностью остановить таймер и сохранить статистику\n\n"
        "*Советы:*\n"
        "• Используйте метод Помодоро: 25 минут работы, 5 минут отдыха\n"
        "• Делайте более длинный перерыв (15-30 минут) после 4-х циклов\n"
        "• Убирайте отвлекающие факторы во время работы\n\n"
        "Приятной и продуктивной учебы! 📚"
    ),
    "subject": (
        "*Выбор предмета*\n\n"
        "Выбери предмет из списка или добавь новый.\n"
        "Ты можешь добавить свои предметы, нажав '➕ Добавить предмет'.\n\n"
        "*Совет:* Создавай отдельные предметы для разных тем или проектов."
    ),
    "work_time": (
        "*Выбор времени работы*\n\n"
        "Выбери продолжительность периода работы в минутах.\n"
        "Оптимальное время работы — 25-45 минут.\n\n"
        "*Совет:* Не устанавливай слишком длинные периоды работы, "
        "это может снизить эффективность."
    ),
    "break_time": (
        "*Выбор времени отдыха*\n\n"
        "Выбери продолжительность периода отдыха в минутах.\n"
        "Оптимальное время отдыха — 5-15 минут.\n\n"
        "*Совет:* Используй перерыв, чтобы встать, размяться или выпить воды."
    ),
    "start_time": (
        "*Выбор времени начала*\n\n"
        "Выбери, когда начать отсчет таймера.\n"
        "Можешь начать сейчас или указать конкретное время.\n\n"
        "*Совет:* Если начинаешь не сразу, используй это время для подготовки."
    ),
    "end_time": (
        "*Выбор времени окончания*\n\n"
        "Выбери, когда закончить сессию, или выбери 'Без окончания'.\n\n"
        "*Совет:* Определи реалистичное время для достижения твоих целей."
    )
}


def load_user_data():
    """Load user statistics from file."""
    if os.path.exists(USER_DATA_FILE):
        try:
            with open(USER_DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading user data: {e}")
    return {}


def save_user_data(user_data):
    """Save user statistics to file."""
    try:
        with open(USER_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(user_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Error saving user data: {e}")


class UserSession:
    """Class to store and manage user session data."""

    def __init__(self):
        self.subject = None
        self.work_time = None
        self.break_time = None
        self.start_time = None
        self.end_time = None
        self.is_working = False
        self.is_paused = False
        self.task = None
        self.start_timestamp = None  # To track when the session started
        self.total_work_time = 0  # Track actual work time in seconds
        self.total_work_sessions = 0  # Track number of completed work sessions
        self.pause_start_time = None  # Track when a pause started
        self.current_progress = 0  # Track current progress in percentage


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the conversation and ask for subject."""
    user_id = update.effective_user.id

    # Check if user already has an active timer
    if user_id in active_timers:
        keyboard = [
            [InlineKeyboardButton("⏹️ Остановить текущий таймер", callback_data="force_stop")],
            [InlineKeyboardButton("🔙 Вернуться к текущему таймеру", callback_data="return_to_timer")],
            [InlineKeyboardButton("❓ Помощь", callback_data="help")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "⚠️ *У вас уже есть активный таймер!*\n\n"
            "Что вы хотите сделать?",
            reply_markup=reply_markup,
            parse_mode='Markdown')
        return RUNNING

    # Initialize user session
    context.user_data['session'] = UserSession()

    # Get predefined and custom subjects from user data
    user_data = load_user_data()
    user_str_id = str(user_id)

    if user_str_id not in user_data:
        user_data[user_str_id] = {"stats": {}, "custom_subjects": []}
        save_user_data(user_data)

    # Combine predefined and custom subjects
    predefined_subjects = [
        "📚 Русский язык", "🏛️ История Беларуси", "🧬 Биология",
        "🔢 Математика", "⚗️ Химия", "⚛️ Физика"
    ]

    custom_subjects = user_data[user_str_id].get("custom_subjects", [])

    # Create keyboard for subjects
    keyboard = []

    # Add predefined subjects
    for subject in predefined_subjects:
        keyboard.append([subject])

    # Add custom subjects
    for subject in custom_subjects:
        # Check if subject already has an emoji
        if " " in subject and any(emoji in subject for emoji in SUBJECT_EMOJIS.values()):
            keyboard.append([subject])
        else:
            # Add default emoji if none exists
            keyboard.append([f"{DEFAULT_CUSTOM_EMOJI} {subject}"])

    # Add options to add new subject or cancel
    keyboard.append(["➕ Добавить предмет"])
    keyboard.append(["❓ Помощь", "❌ Отмена"])

    reply_markup = ReplyKeyboardMarkup(keyboard,
                                    one_time_keyboard=True,
                                    resize_keyboard=True)

    await update.message.reply_text(
        "👋 *Привет! Я помогу тебе распределить время для учебы.*\n\n"
        "Выбери предмет, которым будешь заниматься:\n\n" +
        HELP_MESSAGES["subject"],
        reply_markup=reply_markup,
        parse_mode='Markdown')

    return SUBJECT


async def add_custom_subject(update: Update,
                          context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle adding a custom subject."""
    # Create cancel button
    keyboard = [["❌ Отмена"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

    await update.message.reply_text(
        "🖊 *Добавление нового предмета*\n\n"
        "Введи название предмета:\n\n"
        "Примеры: 'История искусств', 'Программирование', 'Подготовка к экзамену'\n\n"
        "Нажми 'Отмена', чтобы вернуться к выбору предмета.",
        parse_mode='Markdown',
        reply_markup=reply_markup)

    context.user_data['adding_subject'] = True
    return SUBJECT


async def subject(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store the selected subject and ask for work time."""
    # Check for help command
    if update.message.text == "❓ Помощь":
        await update.message.reply_text(
            HELP_MESSAGES["main"],
            parse_mode='Markdown'
        )
        return await start(update, context)

    # Check for cancel command
    if update.message.text == "❌ Отмена":
        return await cancel(update, context)

    # Check if user is adding a new subject
    if context.user_data.get('adding_subject'):
        user_id = str(update.effective_user.id)
        new_subject = update.message.text

        # Skip if cancel is pressed
        if new_subject == "❌ Отмена":
            context.user_data['adding_subject'] = False
            return await start(update, context)

        # Load user data
        user_data = load_user_data()

        # Add the new subject
        if user_id not in user_data:
            user_data[user_id] = {"stats": {}, "custom_subjects": []}

        if "custom_subjects" not in user_data[user_id]:
            user_data[user_id]["custom_subjects"] = []

        # Add emoji if not present
        if not any(emoji in new_subject for emoji in list(SUBJECT_EMOJIS.values()) + [DEFAULT_CUSTOM_EMOJI]):
            new_subject = f"{DEFAULT_CUSTOM_EMOJI} {new_subject}"

        user_data[user_id]["custom_subjects"].append(new_subject)

        # Save user data
        save_user_data(user_data)

        # Clear the flag
        context.user_data['adding_subject'] = False

        # Confirmation message
        await update.message.reply_text(
            f"✅ Предмет *{new_subject}* успешно добавлен!",
            parse_mode='Markdown'
        )

        # Restart the subject selection
        return await start(update, context)

    session = context.user_data['session']
    # Remove emoji if present
    subject_text = update.message.text
    if "➕ Добавить предмет" in subject_text:
        return await add_custom_subject(update, context)

    # Extract the subject name without emoji
    if " " in subject_text and any(emoji in subject_text for emoji in list(SUBJECT_EMOJIS.values()) + [DEFAULT_CUSTOM_EMOJI]):
        parts = subject_text.split(" ", 1)
        emoji = parts[0]
        subject_name = parts[1]
        session.subject = subject_name
        session.subject_with_emoji = subject_text  # Store full name with emoji
    else:
        session.subject = subject_text
        session.subject_with_emoji = f"{DEFAULT_CUSTOM_EMOJI} {subject_text}"

    # Create styled inline keyboard for work time
    keyboard = []
    row = []
    times = [20, 25, 30, 35, 40, 45, 50, 55, 60]

    for i, time in enumerate(times):
        row.append(
            InlineKeyboardButton(f"⏱️ {time} мин",
                              callback_data=f"work_{time}"))
        if (i + 1) % 3 == 0:
            keyboard.append(row)
            row = []

    if row:
        keyboard.append(row)

    keyboard.append(
        [InlineKeyboardButton("✏️ Свое время", callback_data="work_custom")])
    keyboard.append([InlineKeyboardButton("❓ Помощь", callback_data="help_work_time")])
    keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="cancel")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"📌 *Выбран предмет: {session.subject}*\n\n"
        f"{HELP_MESSAGES['work_time']}",
        reply_markup=reply_markup,
        parse_mode='Markdown')

    return WORK_TIME


async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show help message based on current state."""
    query = update.callback_query
    if query:
        await query.answer()
        
        # Determine which help message to show based on callback data
        help_type = query.data.replace("help_", "")
        
        if help_type in HELP_MESSAGES:
            await query.message.reply_text(
                HELP_MESSAGES[help_type],
                parse_mode='Markdown'
            )
        else:
            await query.message.reply_text(
                HELP_MESSAGES["main"],
                parse_mode='Markdown'
            )
        
        # Return to previous state
        return -1  # Will keep current state
    
    # If reached by text command, show main help
    await update.message.reply_text(
        HELP_MESSAGES["main"],
        parse_mode='Markdown'
    )
    return -1


async def custom_work_time(update: Update,
                         context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle custom work time input."""
    # Create cancel button
    keyboard = [["❌ Отмена"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    
    await update.callback_query.message.reply_text(
        "✏️ *Ввод времени работы*\n\n"
        f"Введи желаемое время работы в минутах (от {MIN_WORK_TIME} до {MAX_WORK_TIME}):\n\n"
        "Пример: 42",
        parse_mode='Markdown',
        reply_markup=reply_markup)
    
    context.user_data['expecting_custom_work'] = True
    return WORK_TIME


async def work_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store the work time and ask for break time."""
    session = context.user_data['session']

    query = update.callback_query

    if query:
        await query.answer()

        if query.data == "cancel":
            await query.message.reply_text(
                "❌ Настройка отменена. Нажми /start чтобы начать заново.")
            return ConversationHandler.END
            
        if query.data == "help_work_time":
            await query.message.reply_text(
                HELP_MESSAGES["work_time"],
                parse_mode='Markdown'
            )
            return WORK_TIME

        if query.data == "work_custom":
            return await custom_work_time(update, context)

        work_time = int(query.data.split("_")[1])
        session.work_time = work_time

        # Create stylish inline keyboard for break time
        keyboard = []
        row = []
        times = [5, 10, 15, 20, 25, 30]

        for i, time in enumerate(times):
            row.append(
                InlineKeyboardButton(f"☕ {time} мин",
                                 callback_data=f"break_{time}"))
            if (i + 1) % 3 == 0:
                keyboard.append(row)
                row = []

        if row:
            keyboard.append(row)

        keyboard.append([
            InlineKeyboardButton("✏️ Свое время", callback_data="break_custom")
        ])
        keyboard.append([InlineKeyboardButton("❓ Помощь", callback_data="help_break_time")])
        keyboard.append(
            [InlineKeyboardButton("❌ Отмена", callback_data="cancel")])

        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.message.reply_text(
            f"⏱️ *Время работы: {session.work_time} минут*\n\n"
            f"{HELP_MESSAGES['break_time']}",
            reply_markup=reply_markup,
            parse_mode='Markdown')

        return BREAK_TIME
    else:
        # Handle text input for custom time
        try:
            # Check for cancel
            if update.message.text == "❌ Отмена":
                return await cancel(update, context)
                
            work_time = int(update.message.text)
            if work_time < MIN_WORK_TIME or work_time > MAX_WORK_TIME:
                await update.message.reply_text(
                    f"⚠️ Время должно быть в пределах от {MIN_WORK_TIME} до {MAX_WORK_TIME} минут. "
                    f"Попробуй еще раз:")
                return WORK_TIME

            session.work_time = work_time

            # Create inline keyboard for break time
            keyboard = []
            row = []
            times = [5, 10, 15, 20, 25, 30]

            for i, time in enumerate(times):
                row.append(
                    InlineKeyboardButton(f"☕ {time} мин",
                                     callback_data=f"break_{time}"))
                if (i + 1) % 3 == 0:
                    keyboard.append(row)
                    row = []

            if row:
                keyboard.append(row)

            keyboard.append([
                InlineKeyboardButton("✏️ Свое время",
                                 callback_data="break_custom")
            ])
            keyboard.append([InlineKeyboardButton("❓ Помощь", callback_data="help_break_time")])
            keyboard.append(
                [InlineKeyboardButton("❌ Отмена", callback_data="cancel")])

            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                f"⏱️ *Время работы: {session.work_time} минут*\n\n"
                f"{HELP_MESSAGES['break_time']}",
                reply_markup=reply_markup,
                parse_mode='Markdown')

            return BREAK_TIME
        except ValueError:
            await update.message.reply_text(
                f"⚠️ Пожалуйста, введи целое число минут (от {MIN_WORK_TIME} до {MAX_WORK_TIME}):")
            return WORK_TIME


async def custom_break_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle custom break time input."""
    # Create cancel button
    keyboard = [["❌ Отмена"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    
    await update.callback_query.message.reply_text(
        "✏️ *Ввод времени отдыха*\n\n"
        f"Введи желаемое время отдыха в минутах (от {MIN_BREAK_TIME} до {MAX_BREAK_TIME}):\n\n"
        "Пример: 15",
        parse_mode='Markdown',
        reply_markup=reply_markup)
    
    context.user_data['expecting_custom_break'] = True
    return BREAK_TIME


async def break_time(update: Update,
                   context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store the break time and ask for start time."""
    session = context.user_data['session']

    query = update.callback_query

    if query:
        await query.answer()

        if query.data == "cancel":
            await query.message.reply_text(
                "❌ Настройка отменена. Нажми /start чтобы начать заново.")
            return ConversationHandler.END
            
        if query.data == "help_break_time":
            await query.message.reply_text(
                HELP_MESSAGES["break_time"],
                parse_mode='Markdown'
            )
            return BREAK_TIME

        if query.data == "break_custom":
            return await custom_break_time(update, context)

        break_time = int(query.data.split("_")[1])
        session.break_time = break_time

        # Create a visual time picker interface
        current_time = datetime.now()
        hour = current_time.hour
        minute = current_time.minute

        # Round up to the nearest 5 minutes
        minute = ((minute + 4) // 5) * 5
        if minute >= 60:
            minute = 0
            hour = (hour + 1) % 24

        formatted_time = f"{hour:02d}:{minute:02d}"

        # Create a keyboard with quick time options
        keyboard = []

        # Current time
        keyboard.append([
            InlineKeyboardButton(f"⏱️ Сейчас ({formatted_time})",
                             callback_data=f"time_{formatted_time}")
        ])

        # Common times
        suggestions = []
        for h in range(hour, hour + 3):
            h = h % 24
            for m in [0, 15, 30, 45]:
                # Create a datetime to compare
                suggest_time = datetime.now().replace(hour=h%24, minute=m, second=0, microsecond=0)
                # Only include future times
                if suggest_time > current_time:
                    suggestions.append(f"{h%24:02d}:{m:02d}")

        row = []
        for i, time_str in enumerate(suggestions[:6]):
            row.append(
                InlineKeyboardButton(time_str,
                                 callback_data=f"time_{time_str}"))
            if (i + 1) % 3 == 0:
                keyboard.append(row)
                row = []

        if row:
            keyboard.append(row)

        keyboard.append([
            InlineKeyboardButton("✏️ Ввести вручную",
                             callback_data="time_custom")
        ])
        keyboard.append([InlineKeyboardButton("❓ Помощь", callback_data="help_start_time")])
        keyboard.append(
            [InlineKeyboardButton("❌ Отмена", callback_data="cancel")])

        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.message.reply_text(
            f"☕ *Время отдыха: {session.break_time} минут*\n\n"
            f"{HELP_MESSAGES['start_time']}",
            reply_markup=reply_markup,
            parse_mode='Markdown')

        # Store that we're now expecting custom time input
        context.user_data['expecting_custom_time'] = False

        return START_TIME
    else:
        # Handle text input for custom time
        try:
            # Check for cancel
            if update.message.text == "❌ Отмена":
                return await cancel(update, context)
                
            break_time = int(update.message.text)
            if break_time < MIN_BREAK_TIME or break_time > MAX_BREAK_TIME:
                await update.message.reply_text(
                    f"⚠️ Время должно быть в пределах от {MIN_BREAK_TIME} до {MAX_BREAK_TIME} минут. "
                    f"Попробуй еще раз:")
                return BREAK_TIME

            session.break_time = break_time

            # Create a visual time picker interface
            current_time = datetime.now()
            hour = current_time.hour
            minute = current_time.minute

            # Round up to the nearest 5 minutes
            minute = ((minute + 4) // 5) * 5
            if minute >= 60:
                minute = 0
                hour = (hour + 1) % 24

            formatted_time = f"{hour:02d}:{minute:02d}"

            # Create a keyboard with quick time options
            keyboard = []

            # Current time
            keyboard.append([
                InlineKeyboardButton(f"⏱️ Сейчас ({formatted_time})",
                                 callback_data=f"time_{formatted_time}")
            ])

            # Options to add +15, +30, +45 minutes to current time
            row = []
            for mins, label in [(15, "+15 мин"), (30, "+30 мин"), (45, "+45 мин")]:
                future_time = current_time + timedelta(minutes=mins)
                time_str = future_time.strftime("%H:%M")
                row.append(
                    InlineKeyboardButton(f"{label} ({time_str})",
                                     callback_data=f"time_{time_str}"))

            keyboard.append(row)

            keyboard.append([
                InlineKeyboardButton("✏️ Ввести вручную",
                                 callback_data="time_custom")
            ])
            keyboard.append([InlineKeyboardButton("❓ Помощь", callback_data="help_start_time")])
            keyboard.append(
                [InlineKeyboardButton("❌ Отмена", callback_data="cancel")])

            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                f"☕ *Время отдыха: {session.break_time} минут*\n\n"
                f"{HELP_MESSAGES['start_time']}",
                reply_markup=reply_markup,
                parse_mode='Markdown')

            return START_TIME
        except ValueError:
            await update.message.reply_text(
                f"⚠️ Пожалуйста, введи целое число минут (от {MIN_BREAK_TIME} до {MAX_BREAK_TIME}):")
            return BREAK_TIME


async def custom_start_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle custom start time input."""
    # Create cancel button
    keyboard = [["❌ Отмена"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    
    await update.callback_query.message.reply_text(
        "✏️ *Ввод времени начала*\n\n"
        "Введи время начала в формате ЧЧ:ММ\n\n"
        "Примеры: 14:30, 09:15",
        parse_mode='Markdown',
        reply_markup=reply_markup)
    
    context.user_data['expecting_custom_time'] = True
    return START_TIME


async def start_time(update: Update,
                   context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store the start time and ask for end time."""
    session = context.user_data['session']

    # Handle callback query for time selection
    if update.callback_query:
        query = update.callback_query
        await query.answer()

        if query.data == "cancel":
            await query.message.reply_text(
                "❌ Настройка отменена. Нажми /start чтобы начать заново.")
            return ConversationHandler.END
            
        if query.data == "help_start_time":
            await query.message.reply_text(
                HELP_MESSAGES["start_time"],
                parse_mode='Markdown'
            )
            return START_TIME

        if query.data == "time_custom":
            return await custom_start_time(update, context)

        if query.data.startswith("time_"):
            time_str = query.data.split("_")[1]
            try:
                # Parse the time string
                start_time = datetime.strptime(time_str, "%H:%M").time()
                current_date = datetime.now().date()

                # Combine date and time
                session.start_time = datetime.combine(current_date, start_time)

                # Now create end time options
                keyboard = []
                
                # No end time option
                keyboard.append([
                    InlineKeyboardButton("⏱️ Без окончания", callback_data="end_none")
                ])
                
                # Suggested durations
                row = []
                durations = [1, 2, 3, 4]
                for i, hours in enumerate(durations):
                    end_time = session.start_time + timedelta(hours=hours)
                    time_str = end_time.strftime("%H:%M")
                    row.append(
                        InlineKeyboardButton(f"+{hours}ч ({time_str})",
                                         callback_data=f"end_{time_str}"))
                    if (i + 1) % 2 == 0:
                        keyboard.append(row)
                        row = []

                if row:
                    keyboard.append(row)

                keyboard.append([
                    InlineKeyboardButton("✏️ Ввести вручную", callback_data="end_custom")
                ])
                keyboard.append([InlineKeyboardButton("❓ Помощь", callback_data="help_end_time")])
                keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="cancel")])

                reply_markup = InlineKeyboardMarkup(keyboard)

                await query.message.reply_text(
                    f"🕒 *Время начала: {start_time.strftime('%H:%M')}*\n\n"
                    f"{HELP_MESSAGES['end_time']}",
                    reply_markup=reply_markup,
                    parse_mode='Markdown')

                return END_TIME

            except ValueError:
                await query.message.reply_text(
                    "⚠️ Неверный формат времени. Пожалуйста, попробуй еще раз."
                )
                return START_TIME

    # Handle text input for custom time
    elif update.message:
        # Check for stop command
        if update.message.text == "❌ Отмена":
            return await cancel(update, context)

        if context.user_data.get('expecting_custom_time', False):
            try:
                time_str = update.message.text
                # Parse the time string
                start_time = datetime.strptime(time_str, "%H:%M").time()
                current_date = datetime.now().date()

                # Combine date and time
                session.start_time = datetime.combine(current_date, start_time)

                # Now create end time options similar to above
                keyboard = []
                
                # No end time option
                keyboard.append([
                    InlineKeyboardButton("⏱️ Без окончания", callback_data="end_none")
                ])
                
                # Suggested durations
                row = []
                durations = [1, 2, 3, 4]
                for i, hours in enumerate(durations):
                    end_time = session.start_time + timedelta(hours=hours)
                    time_str = end_time.strftime("%H:%M")
                    row.append(
                        InlineKeyboardButton(f"+{hours}ч ({time_str})",
                                         callback_data=f"end_{time_str}"))
                    if (i + 1) % 2 == 0:
                        keyboard.append(row)
                        row = []

                if row:
                    keyboard.append(row)

                keyboard.append([
                    InlineKeyboardButton("✏️ Ввести вручную", callback_data="end_custom")
                ])
                keyboard.append([InlineKeyboardButton("❓ Помощь", callback_data="help_end_time")])
                keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="cancel")])

                reply_markup = InlineKeyboardMarkup(keyboard)

                await update.message.reply_text(
                    f"🕒 *Время начала: {start_time.strftime('%H:%M')}*\n\n"
                    f"{HELP_MESSAGES['end_time']}",
                    reply_markup=reply_markup,
                    parse_mode='Markdown')

                return END_TIME

            except ValueError:
                await update.message.reply_text(
                    "⚠️ Неверный формат времени. Пожалуйста, введи время в формате ЧЧ:ММ (например, 14:30):"
                )
                return START_TIME

    return START_TIME


async def custom_end_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle custom end time input."""
    # Create cancel button
    keyboard = [["❌ Отмена"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    
    await update.callback_query.message.reply_text(
        "✏️ *Ввод времени окончания*\n\n"
        "Введи время окончания в формате ЧЧ:ММ\n\n"
        "Примеры: 16:45, 22:00",
        parse_mode='Markdown',
        reply_markup=reply_markup)
    
    context.user_data['expecting_custom_end_time'] = True
    return END_TIME


async def end_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store the end time and start the timer."""
    session = context.user_data['session']

    # Handle callback query
    if update.callback_query:
        query = update.callback_query
        await query.answer()

        if query.data == "cancel":
            await query.message.reply_text(
                "❌ Настройка отменена. Нажми /start чтобы начать заново.")
            return ConversationHandler.END
            
        if query.data == "help_end_time":
            await query.message.reply_text(
                HELP_MESSAGES["end_time"],
                parse_mode='Markdown'
            )
            return END_TIME

        if query.data == "end_none":
            session.end_time = None
            return await start_timer(update, context)

        if query.data == "end_custom":
            return await custom_end_time(update, context)

        if query.data.startswith("end_"):
            time_str = query.data.split("_")[1]
            try:
                # Parse the time string
                end_time = datetime.strptime(time_str, "%H:%M").time()
                current_date = datetime.now().date()

                # Combine date and time
                session.end_time = datetime.combine(current_date, end_time)

                # Check if end time is before start time
                if session.end_time < session.start_time:
                    # Assume it's for the next day
                    session.end_time += timedelta(days=1)

                return await start_timer(update, context)

            except ValueError:
                await query.message.reply_text(
                    "⚠️ Неверный формат времени. Пожалуйста, попробуй еще раз."
                )
                return END_TIME

    # Handle text input for custom end time
    elif update.message:
        # Check for stop command
        if update.message.text == "❌ Отмена":
            return await cancel(update, context)

        if context.user_data.get('expecting_custom_end_time', False):
            try:
                time_str = update.message.text
                # Parse the time string
                end_time = datetime.strptime(time_str, "%H:%M").time()
                current_date = datetime.now().date()

                # Combine date and time
                session.end_time = datetime.combine(current_date, end_time)

                # Check if end time is before start time
                if session.end_time < session.start_time:
                    # Assume it's for the next day
                    session.end_time += timedelta(days=1)

                return await start_timer(update, context)

            except ValueError:
                await update.message.reply_text(
                    "⚠️ Неверный формат времени. Пожалуйста, введи время в формате ЧЧ:ММ (например, 16:45):"
                )
                return END_TIME

    return END_TIME


async def start_timer(update: Update,
                    context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the work/break cycle."""
    session = context.user_data['session']
    user_id = update.effective_user.id

    # Initialize session start timestamp
    session.start_timestamp = datetime.now()

    # Create a visually appealing summary of settings
    summary = (f"📚 *Предмет*: {session.subject}\n"
             f"⏱ *Время работы*: {session.work_time} минут\n"
             f"☕ *Время отдыха*: {session.break_time} минут\n"
             f"🕒 *Время начала*: {session.start_time.strftime('%H:%M')}\n")

    if session.end_time:
        summary += f"🏁 *Время окончания*: {session.end_time.strftime('%H:%M')}\n"
    else:
        summary += "🏁 *Время окончания*: Не указано\n"

    # Create more interactive keyboard for timer control
    keyboard = [
        [InlineKeyboardButton("⏹️ Остановить", callback_data="stop_timer")],
        [
            InlineKeyboardButton("⏸️ Пауза", callback_data="pause_timer"),
            InlineKeyboardButton("▶️ Продолжить", callback_data="resume_timer")
        ],
        [InlineKeyboardButton("❓ Помощь", callback_data="help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Also provide a persistent quick stop button
    stop_keyboard = [
        [KeyboardButton("❌ Остановить таймер")],
        [KeyboardButton("📊 Статистика"), KeyboardButton("⏸️ Пауза/▶️ Продолжить")],
        [KeyboardButton("❓ Помощь")]
    ]
    stop_markup = ReplyKeyboardMarkup(stop_keyboard, resize_keyboard=True)

    # Start the first work session
    session.is_working = True
    active_timers[user_id] = session

    # Create and start the timer task
    session.task = asyncio.create_task(run_timer(update, context, user_id))

    # Send confirmation message with fancy formatting
    if update.message:
        await update.message.reply_text(
            f"✅ *Настройки сохранены!*\n\n{summary}\n"
            f"🚀 Начинаем работу прямо сейчас! Удачи с изучением предмета *{session.subject}*!\n"
            f"Используй кнопки для управления таймером.",
            reply_markup=reply_markup,
            parse_mode='Markdown')
        await update.message.reply_text(
            "Быстрые кнопки управления:",
            reply_markup=stop_markup)
    else:
        await update.callback_query.message.reply_text(
            f"✅ *Настройки сохранены!*\n\n{summary}\n"
            f"🚀 Начинаем работу прямо сейчас! Удачи с изучением предмета *{session.subject}*!\n"
            f"Используй кнопки для управления таймером.",
            reply_markup=reply_markup,
            parse_mode='Markdown')
        await update.callback_query.message.reply_text(
            "Быстрые кнопки управления:", 
            reply_markup=stop_markup)

    return RUNNING


async def run_timer(update: Update, context: ContextTypes.DEFAULT_TYPE,
                  user_id: int):
    """Run the work/break cycle."""
    session = active_timers.get(user_id)
    if not session:
        return

    # Get the chat ID from the update
    chat_id = update.effective_chat.id

    # Add pause functionality
    session.is_paused = False

    try:
        while True:
            now = datetime.now()

            # Check if we've reached the end time
            if session.end_time and now >= session.end_time:
                # Update statistics
                await update_statistics(user_id, session)

                # Create return keyboard
                keyboard = [
                    [KeyboardButton("🔄 Начать новую сессию")],
                    [KeyboardButton("📊 Статистика"), KeyboardButton("❓ Помощь")]
                ]
                reply_markup = ReplyKeyboardMarkup(keyboard,
                                                resize_keyboard=True)

                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"⏰ *Время окончания достигнуто!*\n\n"
                    f"Сессия по предмету *{session.subject}* завершена.\n\n"
                    f"📊 *Статистика сессии:*\n"
                    f"• Выполнено рабочих интервалов: *{session.total_work_sessions}*\n"
                    f"• Общее время работы: *{format_time_duration(session.total_work_time)}*\n\n"
                    f"Молодец! Для начала новой сессии нажми кнопку 'Начать новую сессию' или /start.",
                    parse_mode='Markdown',
                    reply_markup=reply_markup)
                if user_id in active_timers:
                    del active_timers[user_id]
                break

            # Check if timer is paused
            while session.is_paused:
                await asyncio.sleep(1)  # Check every second if pause state has changed

                # If timer was deleted while paused, exit
                if user_id not in active_timers:
                    return

            if session.is_working:
                # Working period
                # Create inline keyboard for quick control
                keyboard = [
                    [
                        InlineKeyboardButton("⏸️ Пауза", callback_data="pause_timer"),
                        InlineKeyboardButton("⏹️ Стоп", callback_data="stop_timer")
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)

                # Calculate end time of this work session
                end_work = now + timedelta(minutes=session.work_time)

                # Calculate progress for this session
                progress_message = create_progress_bar(0, session.work_time)

                work_message = await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"🚀 *Начинаем работу!*\n\n"
                    f"📚 Предмет: *{session.subject}*\n"
                    f"⏱️ Продолжительность: *{session.work_time}* минут\n"
                    f"🕒 До: *{end_work.strftime('%H:%M')}*\n\n"
                    f"{progress_message}",
                    parse_mode='Markdown',
                    reply_markup=reply_markup)

                # Track the start time of work session for statistics
                work_start_time = datetime.now()

                # Sleep in shorter intervals and update the progress bar
                remaining_seconds = session.work_time * 60
                update_interval = 30  # Update progress every 30 seconds

                while remaining_seconds > 0:
                    # Sleep for shorter interval or remaining time, whichever is smaller
                    sleep_time = min(update_interval, remaining_seconds)
                    await asyncio.sleep(sleep_time)

                    # If paused or stopped, break the loop
                    if session.is_paused or user_id not in active_timers:
                        break

                    remaining_seconds -= sleep_time
                    elapsed_minutes = (session.work_time * 60 - remaining_seconds) / 60

                    # Update progress bar
                    progress_message = create_progress_bar(elapsed_minutes, session.work_time)
                    
                    # Update progress percentage for session
                    session.current_progress = int((elapsed_minutes / session.work_time) * 100)

                    try:
                        await context.bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=work_message.message_id,
                            text=f"🚀 *Работа над предметом*\n\n"
                            f"📚 Предмет: *{session.subject}*\n"
                            f"⏱️ Осталось: *{int(remaining_seconds / 60)}* мин *{remaining_seconds % 60}* сек\n"
                            f"🕒 До: *{end_work.strftime('%H:%M')}*\n\n"
                            f"{progress_message}",
                            parse_mode='Markdown',
                            reply_markup=reply_markup)
                    except Exception as e:
                        logger.error(f"Error updating progress: {e}")

                # If the timer was paused or stopped, don't continue
                if session.is_paused or user_id not in active_timers:
                    continue

                # Update work statistics
                work_end_time = datetime.now()
                work_duration = (work_end_time - work_start_time).total_seconds()
                session.total_work_time += work_duration
                session.total_work_sessions += 1

                # Play a sound or send a notification that work session is complete
                await context.bot.send_message(
                    chat_id=chat_id,
                    text="🎵 *Дзинь!* Рабочий период завершен! Время для отдыха.",
                    parse_mode='Markdown'
                )

                # Switch to break
                session.is_working = False

                # Create inline keyboard for break time
                keyboard = [
                    [
                        InlineKeyboardButton("⏸️ Пауза", callback_data="pause_timer"),
                        InlineKeyboardButton("⏹️ Стоп", callback_data="stop_timer")
                    ],
                    [InlineKeyboardButton("⏭️ Пропустить отдых", callback_data="skip_break")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)

                # Calculate end time of this break session
                end_break = now + timedelta(minutes=session.break_time)

                # Create progress bar for break
                break_progress = create_progress_bar(0, session.break_time)

                break_message = await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"☕ *Время отдыха!*\n\n"
                    f"💤 Отдыхай *{session.break_time}* минут\n"
                    f"🕒 До: *{end_break.strftime('%H:%M')}*\n\n"
                    f"{break_progress}",
                    parse_mode='Markdown',
                    reply_markup=reply_markup)
                    
                # Sleep in shorter intervals and update the progress bar for break
                remaining_seconds = session.break_time * 60
                update_interval = 15  # Update progress more frequently during break

                while remaining_seconds > 0:
                    # Sleep for shorter interval or remaining time, whichever is smaller
                    sleep_time = min(update_interval, remaining_seconds)
                    await asyncio.sleep(sleep_time)

                    # If paused or stopped, break the loop
                    if session.is_paused or user_id not in active_timers:
                        break

                    remaining_seconds -= sleep_time
                    elapsed_minutes = (session.break_time * 60 - remaining_seconds) / 60

                    # Update progress bar
                    break_progress = create_progress_bar(elapsed_minutes, session.break_time)

                    try:
                        await context.bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=break_message.message_id,
                            text=f"☕ *Время отдыха!*\n\n"
                            f"💤 Осталось: *{int(remaining_seconds / 60)}* мин *{remaining_seconds % 60}* сек\n"
                            f"🕒 До: *{end_break.strftime('%H:%M')}*\n\n"
                            f"{break_progress}",
                            parse_mode='Markdown',
                            reply_markup=reply_markup)
                    except Exception as e:
                        logger.error(f"Error updating break progress: {e}")

                # If the timer was paused or stopped, don't continue
                if session.is_paused or user_id not in active_timers:
                    continue

                # Play a sound or send a notification that break is complete
                await context.bot.send_message(
                    chat_id=chat_id,
                    text="🔔 *Дзинь!* Перерыв окончен! Пора возвращаться к работе.",
                    parse_mode='Markdown'
                )

                # Switch to work
                session.is_working = True

                # Create inline keyboard for work period
                keyboard = [
                    [
                        InlineKeyboardButton("⏸️ Пауза", callback_data="pause_timer"),
                        InlineKeyboardButton("⏹️ Стоп", callback_data="stop_timer")
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)

                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"🔄 *Перерыв окончен!*\n\n"
                    f"Возвращаемся к работе над предметом *{session.subject}*.\n\n"
                    f"Небольшая статистика:\n"
                    f"• Выполнено интервалов: {session.total_work_sessions}\n"
                    f"• Общее время работы: {format_time_duration(session.total_work_time)}",
                    parse_mode='Markdown',
                    reply_markup=reply_markup)
            else:
                # Break period (already handled above in the new implementation)
                # The break period is now handled with progress updates
                await asyncio.sleep(1)
                
    except asyncio.CancelledError:
        # Task was cancelled, clean up
        if user_id in active_timers:
            # Update statistics before deleting
            await update_statistics(user_id, session)
            del active_timers[user_id]
    except Exception as e:
        logger.error(f"Error in timer task: {e}")
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"❌ Произошла ошибка: {str(e)}\n\nПопробуйте перезапустить таймер с помощью /start")
        if user_id in active_timers:
            del active_timers[user_id]


def create_progress_bar(elapsed_minutes, total_minutes, width=20):
    """Create a visual progress bar."""
    progress = min(1.0, elapsed_minutes / total_minutes)
    filled_width = int(width * progress)
    empty_width = width - filled_width

    bar = "▓" * filled_width + "░" * empty_width
    percentage = int(progress * 100)

    return f"[{bar}] {percentage}%"


async def update_statistics(user_id, session):
    """Update user statistics at the end of a session."""
    try:
        user_str_id = str(user_id)
        user_data = load_user_data()

        if user_str_id not in user_data:
            user_data[user_str_id] = {"stats": {}, "custom_subjects": []}

        if "stats" not in user_data[user_str_id]:
            user_data[user_str_id]["stats"] = {}

        subject = session.subject
        if subject not in user_data[user_str_id]["stats"]:
            user_data[user_str_id]["stats"][subject] = {
                "total_sessions": 0,
                "total_work_time": 0,
                "total_work_intervals": 0,
                "last_session": None
            }

        # Update statistics
        stats = user_data[user_str_id]["stats"][subject]
        stats["total_sessions"] += 1
        stats["total_work_time"] += session.total_work_time
        stats["total_work_intervals"] += session.total_work_sessions
        stats["last_session"] = datetime.now().strftime("%Y-%m-%d %H:%M")

        save_user_data(user_data)
    except Exception as e:
        logger.error(f"Error updating statistics: {e}")


def format_time_duration(seconds):
    """Format seconds into a readable time duration."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    seconds = int(seconds % 60)

    if hours > 0:
        return f"{hours} ч {minutes} мин {seconds} сек"
    elif minutes > 0:
        return f"{minutes} мин {seconds} сек"
    else:
        return f"{seconds} сек"


async def get_stats(update: Update,
                  context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display user statistics."""
    user_id = str(update.effective_user.id)
    user_data = load_user_data()

    if user_id not in user_data or "stats" not in user_data[user_id] or not user_data[user_id]["stats"]:
        await update.message.reply_text(
            "📊 *Статистика*\n\n"
            "У вас пока нет статистики. Начните сессию, чтобы собрать данные.",
            parse_mode='Markdown')
        return

    stats = user_data[user_id]["stats"]

    # Create a formatted statistics message
    stats_text = "📊 *Статистика по предметам*\n\n"

    # Sort subjects by total work time (descending)
    sorted_subjects = sorted(
        stats.items(), 
        key=lambda x: x[1]["total_work_time"], 
        reverse=True
    )

    for subject, subject_stats in sorted_subjects:
        total_time = format_time_duration(subject_stats["total_work_time"])
        avg_session_time = format_time_duration(
            subject_stats["total_work_time"] / subject_stats["total_sessions"] 
            if subject_stats["total_sessions"] > 0 else 0
        )
        
        stats_text += f"*{subject}*\n"
        stats_text += f"• Всего сессий: {subject_stats['total_sessions']}\n"
        stats_text += f"• Рабочих интервалов: {subject_stats['total_work_intervals']}\n"
        stats_text += f"• Общее время работы: {total_time}\n"
        stats_text += f"• Среднее время сессии: {avg_session_time}\n"

        last_session = subject_stats.get("last_session")
        if last_session:
            stats_text += f"• Последняя сессия: {last_session}\n"

        stats_text += "\n"

    # Calculate overall statistics
    total_work_time = sum(subject_stats["total_work_time"] for subject_stats in stats.values())
    total_sessions = sum(subject_stats["total_sessions"] for subject_stats in stats.values())
    total_intervals = sum(subject_stats["total_work_intervals"] for subject_stats in stats.values())
    
    stats_text += f"*Общая статистика*\n"
    stats_text += f"• Всего сессий: {total_sessions}\n"
    stats_text += f"• Всего рабочих интервалов: {total_intervals}\n"
    stats_text += f"• Общее время работы: {format_time_duration(total_work_time)}\n\n"
    
    stats_text += "🏆 Продолжайте в том же духе! 💪"

    # Create keyboard for statistics interactions
    keyboard = [
        [InlineKeyboardButton("📝 Очистить статистику", callback_data="clear_stats")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_from_stats")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        stats_text,
        parse_mode='Markdown',
        reply_markup=reply_markup)


async def clear_stats(update: Update,
                    context: ContextTypes.DEFAULT_TYPE) -> None:
    """Clear user statistics."""
    query = update.callback_query
    await query.answer()

    user_id = str(update.effective_user.id)
    user_data = load_user_data()

    if user_id in user_data and "stats" in user_data[user_id]:
        # Confirm clearing stats
        keyboard = [
            [InlineKeyboardButton("✅ Да, очистить", callback_data="confirm_clear_stats")],
            [InlineKeyboardButton("❌ Нет, отмена", callback_data="cancel_clear_stats")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.message.reply_text(
            "⚠️ *Подтверждение действия*\n\n"
            "Вы уверены, что хотите очистить всю статистику? Это действие нельзя отменить.",
            parse_mode='Markdown',
            reply_markup=reply_markup)


async def confirm_clear_stats(update: Update,
                           context: ContextTypes.DEFAULT_TYPE) -> None:
    """Confirm clearing user statistics."""
    query = update.callback_query
    await query.answer()

    user_id = str(update.effective_user.id)
    user_data = load_user_data()

    if user_id in user_data and "stats" in user_data[user_id]:
        user_data[user_id]["stats"] = {}
        save_user_data(user_data)

        await query.message.reply_text(
            "✅ Статистика успешно очищена.\n\n"
            "Теперь можно начать с чистого листа! Используйте /start, чтобы начать новую сессию.")


async def cancel_clear_stats(update: Update,
                          context: ContextTypes.DEFAULT_TYPE) -> None:
    """Cancel clearing user statistics."""
    query = update.callback_query
    await query.answer()

    await query.message.reply_text(
        "❌ Очистка статистики отменена.\n\n"
        "Ваши данные сохранены!")


async def back_from_stats(update: Update,
                        context: ContextTypes.DEFAULT_TYPE) -> None:
    """Return from statistics view."""
    query = update.callback_query
    await query.answer()

    # Create default keyboard
    keyboard = [
        [KeyboardButton("🚀 Старт"), KeyboardButton("📊 Статистика")],
        [KeyboardButton("❓ Помощь")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await query.message.reply_text(
        "Выберите действие:", 
        reply_markup=reply_markup)


async def toggle_pause(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Toggle pause/resume state for the timer."""
    user_id = update.effective_user.id
    
    if user_id in active_timers:
        session = active_timers[user_id]
        
        if session.is_paused:
            # Resume the timer
            session.is_paused = False
            keyboard = [
                [InlineKeyboardButton("⏸️ Пауза", callback_data="pause_timer")],
                [InlineKeyboardButton("⏹️ Стоп", callback_data="stop_timer")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "▶️ *Таймер возобновлен*\n\nПродолжаем отсчет!",
                parse_mode='Markdown',
                reply_markup=reply_markup)
        else:
            # Pause the timer
            session.is_paused = True
            session.pause_start_time = datetime.now()
            
            keyboard = [
                [InlineKeyboardButton("▶️ Продолжить", callback_data="resume_timer")],
                [InlineKeyboardButton("⏹️ Стоп", callback_data="stop_timer")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "⏸️ *Таймер приостановлен*\n\nНажми 'Продолжить', чтобы возобновить отсчет.",
                parse_mode='Markdown',
                reply_markup=reply_markup)
    else:
        # No active timer
        keyboard = [[KeyboardButton("🚀 Старт"), KeyboardButton("📊 Статистика")]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        await update.message.reply_text(
            "Нет активных таймеров. Чтобы начать новую сессию, нажми /start.",
            reply_markup=reply_markup)
    
    return RUNNING


async def stop_timer(update: Update,
                   context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stop the timer and end the conversation."""
    user_id = update.effective_user.id

    # Handle callback query (button press)
    if update.callback_query:
        query = update.callback_query
        await query.answer()

        if query.data == "force_stop":
            # Force stop existing timer
            if user_id in active_timers:
                session = active_timers[user_id]

                # Cancel the timer task
                if session.task and not session.task.done():
                    session.task.cancel()

                # Update statistics before removing
                await update_statistics(user_id, session)

                # Remove from active timers
                del active_timers[user_id]

                # Start a new session
                return await start(update, context)

        if query.data == "return_to_timer":
            # Return to existing timer
            keyboard = [
                [KeyboardButton("❌ Остановить таймер")],
                [KeyboardButton("📊 Статистика"), KeyboardButton("⏸️ Пауза/▶️ Продолжить")]
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

            await query.message.reply_text(
                "Возвращаемся к текущему таймеру.",
                reply_markup=reply_markup)
            return RUNNING

        if user_id in active_timers:
            session = active_timers[user_id]

            # Cancel the timer task
            if session.task and not session.task.done():
                session.task.cancel()

            # Update statistics before removing
            await update_statistics(user_id, session)

            # Remove from active timers
            del active_timers[user_id]

            # Return to start keyboard
            keyboard = [
                [KeyboardButton("🔄 Начать новую сессию")],
                [KeyboardButton("📊 Статистика"), KeyboardButton("❓ Помощь")]
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

            await query.message.reply_text(
                "⏹ *Таймер остановлен!*\n\n"
                f"📊 *Статистика сессии:*\n"
                f"• Выполнено рабочих интервалов: *{session.total_work_sessions}*\n"
                f"• Общее время работы: *{format_time_duration(session.total_work_time)}*\n\n"
                "Молодец! Для начала новой сессии нажми кнопку 'Начать новую сессию' или /start.",
                parse_mode='Markdown',
                reply_markup=reply_markup)
        else:
            # Default keyboard with quick access buttons
            keyboard = [
                [KeyboardButton("🚀 Старт"), KeyboardButton("📊 Статистика")],
                [KeyboardButton("❓ Помощь")]
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

            await query.message.reply_text(
                "Нет активных таймеров. Чтобы начать новую сессию, нажми /start.",
                reply_markup=reply_markup)

    # Handle text message (quick stop button)
    elif update.message and (update.message.text == "❌ Остановить таймер"
                          or update.message.text == "/stop"
                          or update.message.text == "⏹ Стоп"):
        if user_id in active_timers:
            session = active_timers[user_id]

            # Cancel the timer task
            if session.task and not session.task.done():
                session.task.cancel()

            # Update statistics before removing
            await update_statistics(user_id, session)

            # Remove from active timers
            del active_timers[user_id]

            # Return to start keyboard
            keyboard = [
                [KeyboardButton("🔄 Начать новую сессию")],
                [KeyboardButton("📊 Статистика"), KeyboardButton("❓ Помощь")]
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

            await update.message.reply_text(
                "⏹ *Таймер остановлен!*\n\n"
                f"📊 *Статистика сессии:*\n"
                f"• Выполнено рабочих интервалов: *{session.total_work_sessions}*\n"
                f"• Общее время работы: *{format_time_duration(session.total_work_time)}*\n\n"
                "Молодец! Для начала новой сессии нажми кнопку 'Начать новую сессию' или /start.",
                parse_mode='Markdown',
                reply_markup=reply_markup)
        else:
            # Default keyboard with quick access buttons
            keyboard = [
                [KeyboardButton("🚀 Старт"), KeyboardButton("📊 Статистика")],
                [KeyboardButton("❓ Помощь")]
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

            await update.message.reply_text(
                "Нет активных таймеров. Чтобы начать новую сессию, нажми /start.",
                reply_markup=reply_markup)

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the conversation."""
    # Return to default keyboard with quick access buttons
    keyboard = [
        [KeyboardButton("🚀 Старт"), KeyboardButton("📊 Статистика")],
        [KeyboardButton("❓ Помощь")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    if update.message:
        await update.message.reply_text(
            "❌ *Настройка отменена*\n\nЧтобы начать заново, нажми /start.",
            parse_mode='Markdown',
            reply_markup=reply_markup)
    elif update.callback_query:
        await update.callback_query.message.reply_text(
            "❌ *Настройка отменена*\n\nЧтобы начать заново, нажми /start.",
            parse_mode='Markdown',
            reply_markup=reply_markup)

    user_id = update.effective_user.id

    # Clean up any active timer
    if user_id in active_timers:
        session = active_timers[user_id]

        # Cancel the timer task
        if session.task and not session.task.done():
            session.task.cancel()

        # Remove from active timers
        del active_timers[user_id]

    return ConversationHandler.END


async def pause_timer(update: Update,
                    context: ContextTypes.DEFAULT_TYPE) -> int:
    """Pause the timer."""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id

    if user_id in active_timers:
        session = active_timers[user_id]
        session.is_paused = True
        session.pause_start_time = datetime.now()

        # Update keyboard to show resume option
        keyboard = [
            [InlineKeyboardButton("▶️ Продолжить", callback_data="resume_timer")],
            [InlineKeyboardButton("⏹️ Стоп", callback_data="stop_timer")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.message.reply_text(
            "⏸️ *Таймер приостановлен*\n\nНажми 'Продолжить', чтобы возобновить отсчет.",
            parse_mode='Markdown',
            reply_markup=reply_markup)
    else:
        # Default keyboard with quick access buttons
        keyboard = [
            [KeyboardButton("🚀 Старт"), KeyboardButton("📊 Статистика")],
            [KeyboardButton("❓ Помощь")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

        await query.message.reply_text(
            "Нет активных таймеров. Чтобы начать новую сессию, нажми /start.",
            reply_markup=reply_markup)

    return RUNNING


async def resume_timer(update: Update,
                     context: ContextTypes.DEFAULT_TYPE) -> int:
    """Resume the timer."""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id

    if user_id in active_timers:
        session = active_timers[user_id]
        session.is_paused = False

        # Update keyboard to show pause option
        keyboard = [
            [InlineKeyboardButton("⏸️ Пауза", callback_data="pause_timer")],
            [InlineKeyboardButton("⏹️ Стоп", callback_data="stop_timer")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.message.reply_text(
            "▶️ *Таймер возобновлен*\n\nПродолжаем отсчет!",
            parse_mode='Markdown',
            reply_markup=reply_markup)
    else:
        # Default keyboard with quick access buttons
        keyboard = [
            [KeyboardButton("🚀 Старт"), KeyboardButton("📊 Статистика")],
            [KeyboardButton("❓ Помощь")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

        await query.message.reply_text(
            "Нет активных таймеров. Чтобы начать новую сессию, нажми /start.",
            reply_markup=reply_markup)

    return RUNNING


async def skip_break(update: Update,
                   context: ContextTypes.DEFAULT_TYPE) -> int:
    """Skip the break period."""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id

    if user_id in active_timers:
        session = active_timers[user_id]

        if not session.is_working:
            # If in break mode, switch to work mode
            session.is_working = True

            # Create keyboard for work period
            keyboard = [
                [InlineKeyboardButton("⏸️ Пауза", callback_data="pause_timer")],
                [InlineKeyboardButton("⏹️ Стоп", callback_data="stop_timer")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.message.reply_text(
                f"⏭️ *Перерыв пропущен!*\n\nВозвращаемся к работе над предметом *{session.subject}*.",
                parse_mode='Markdown',
                reply_markup=reply_markup)
    else:
        await query.message.reply_text(
            "Нет активных таймеров. Чтобы начать новую сессию, нажми /start.")

    return RUNNING


async def help_command(update: Update,
                     context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a help message."""
    await update.message.reply_text(
        HELP_MESSAGES["main"], 
        parse_mode='Markdown')


async def force_stop_handler(update: Update,
                           context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handler for force stopping a timer and starting a new one."""
    return await stop_timer(update, context)


async def return_to_timer_handler(update: Update,
                                context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handler for returning to an active timer."""
    query = update.callback_query
    await query.answer()

    # Create keyboard for timer control
    keyboard = [
        [KeyboardButton("❌ Остановить таймер")],
        [KeyboardButton("📊 Статистика"), KeyboardButton("⏸️ Пауза/▶️ Продолжить")],
        [KeyboardButton("❓ Помощь")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await query.message.reply_text(
        "Возвращаемся к текущему таймеру.", 
        reply_markup=reply_markup)

    return RUNNING


async def error_handler(update: Update,
                      context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle errors in the telegram bot."""
    logger.error(f"Update {update} caused error {context.error}")

    # Send a friendly message to the user
    if update.effective_chat:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=
            "⚠️ Произошла ошибка при обработке вашего запроса. Пожалуйста, попробуйте еще раз.\n\n"
            "Если проблема повторяется, попробуйте перезапустить бота с помощью команды /start."
        )


def main() -> None:
    """Start the bot."""
    # Load the bot token from environment variable for better security
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        print("Ошибка: Не найден токен бота. Проверьте переменную TELEGRAM_BOT_TOKEN")
        return

    # Create the Application and pass it your bot's token
    application = Application.builder().token(token).build()

    # Add conversation handler with enhanced state handling
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            MessageHandler(filters.Regex("🔄 Начать новую сессию"), start),
            MessageHandler(filters.Regex("🚀 Старт"), start)
        ],
        states={
            SUBJECT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, subject),
                CommandHandler("cancel", cancel)
            ],
            WORK_TIME: [
                CallbackQueryHandler(work_time, pattern=r"^work_"),
                CallbackQueryHandler(show_help, pattern=r"^help_"),
                CallbackQueryHandler(cancel, pattern=r"^cancel$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, work_time),
                CommandHandler("cancel", cancel)
            ],
            BREAK_TIME: [
                CallbackQueryHandler(break_time, pattern=r"^break_"),
                CallbackQueryHandler(show_help, pattern=r"^help_"),
                CallbackQueryHandler(cancel, pattern=r"^cancel$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, break_time),
                CommandHandler("cancel", cancel)
            ],
            START_TIME: [
                CallbackQueryHandler(start_time, pattern=r"^time_"),
                CallbackQueryHandler(show_help, pattern=r"^help_"),
                CallbackQueryHandler(cancel, pattern=r"^cancel$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, start_time),
                CommandHandler("cancel", cancel)
            ],
            END_TIME: [
                CallbackQueryHandler(end_time, pattern=r"^end_"),
                CallbackQueryHandler(show_help, pattern=r"^help_"),
                CallbackQueryHandler(cancel, pattern=r"^cancel$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, end_time),
                CommandHandler("cancel", cancel)
            ],
            RUNNING: [
                CallbackQueryHandler(stop_timer, pattern=r"^stop_timer$"),
                CallbackQueryHandler(pause_timer, pattern=r"^pause_timer$"),
                CallbackQueryHandler(resume_timer, pattern=r"^resume_timer$"),
                CallbackQueryHandler(skip_break, pattern=r"^skip_break$"),
                CallbackQueryHandler(force_stop_handler, pattern=r"^force_stop$"),
                CallbackQueryHandler(return_to_timer_handler, pattern=r"^return_to_timer$"),
                CallbackQueryHandler(show_help, pattern=r"^help$"),
                MessageHandler(filters.Regex("❌ Остановить таймер"), stop_timer),
                MessageHandler(filters.Regex("⏹ Стоп"), stop_timer),
                MessageHandler(filters.Regex("⏸️ Пауза/▶️ Продолжить"), toggle_pause),
                MessageHandler(filters.Regex("❓ Помощь"), help_command),
                CommandHandler("stop", stop_timer)
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CommandHandler("stop", stop_timer)
        ],
        per_message=False,
        name="study_timer_bot")

    # Additional handlers
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("stats", get_stats))
    application.add_handler(MessageHandler(filters.Regex("📊 Статистика"), get_stats))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.Regex("❓ Помощь"), help_command))
    application.add_handler(CallbackQueryHandler(clear_stats, pattern=r"^clear_stats$"))
    application.add_handler(CallbackQueryHandler(confirm_clear_stats, pattern=r"^confirm_clear_stats$"))
    application.add_handler(CallbackQueryHandler(cancel_clear_stats, pattern=r"^cancel_clear_stats$"))
    application.add_handler(CallbackQueryHandler(back_from_stats, pattern=r"^back_from_stats$"))
    application.add_handler(CallbackQueryHandler(show_help, pattern=r"^help"))

    # Add error handler
    application.add_error_handler(error_handler)

    # Start the Bot with better error handling
    try:
        logger.info("Starting bot...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
        print(f"Error starting bot: {e}")


if __name__ == "__main__":
    main()