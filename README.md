# Study Timer Bot 

## Description
A comprehensive Telegram bot for time management and study scheduling, implementing the Pomodoro technique with customizable work/break intervals. Perfect for students and anyone who wants to improve productivity with structured study sessions.

## Features

### Time Management
- **Pomodoro Technique**: Alternates between focused work periods and short breaks to maximize productivity
- **Customizable Intervals**: Set personalized work times (5-120 minutes) and break times (1-60 minutes)
- **Flexible Scheduling**: Start immediately or schedule for later, with optional end time
- **Visual Progress Tracking**: Real-time progress bars show current status and percentage completion

### Subject Management
- **Predefined Subjects**: Common school subjects with relevant emoji icons
- **Custom Subjects**: Add your own subjects with automatic emoji assignment
- **Multi-Subject Support**: Track different subjects separately for better organization

### Interactive Controls
- **Timer Controls**: Pause, resume, stop buttons for full control of sessions
- **Skip Break**: Option to skip breaks when needed and return to work immediately
- **Keyboard Shortcuts**: Quick access buttons for common actions

### Statistics and Tracking
- **Detailed Statistics**: Track total time spent on each subject
- **Session Summary**: View completed intervals and total work time after each session
- **Historical Data**: See when you last studied each subject and how much time you've invested

### User Experience
- **Intuitive Interface**: Easy-to-use inline and reply keyboards
- **Progress Notifications**: Automatic alerts when work or break periods end
- **Comprehensive Help**: Detailed help messages and tooltips for all functions

## Technical Details
- Built with Python using the python-telegram-bot library
- Utilizes asynchronous programming for responsive user interactions
- Implements ConversationHandler for multi-step setup process
- Persistent data storage for user statistics and preferences
- Enhanced logging for troubleshooting and performance monitoring

## Commands
- `/start` - Begin a new study session
- `/stop` - End the current timer
- `/stats` - View your study statistics
- `/help` - Display help information

---

# Бот-Таймер для Учебы 

## Описание
Многофункциональный Telegram-бот для управления временем и планирования учебы, реализующий технику Помодоро с настраиваемыми интервалами работы и отдыха. Идеален для учащихся и всех, кто хочет повысить продуктивность с помощью структурированных учебных сессий.

## Возможности

### Управление временем
- **Техника Помодоро**: Чередование периодов сфокусированной работы и коротких перерывов для максимальной продуктивности
- **Настраиваемые интервалы**: Установка персонализированного времени работы (5-120 минут) и отдыха (1-60 минут)
- **Гибкое расписание**: Начало немедленно или по расписанию, с возможностью установки времени окончания
- **Визуальное отслеживание прогресса**: Индикаторы прогресса в реальном времени показывают текущий статус и процент выполнения

### Управление предметами
- **Предустановленные предметы**: Распространенные школьные предметы с соответствующими эмодзи
- **Пользовательские предметы**: Добавление собственных предметов с автоматическим назначением эмодзи
- **Поддержка нескольких предметов**: Отдельное отслеживание разных предметов для лучшей организации

### Интерактивное управление
- **Управление таймером**: Кнопки паузы, возобновления и остановки для полного контроля сессий
- **Пропуск перерыва**: Возможность пропустить перерывы при необходимости и немедленно вернуться к работе
- **Горячие клавиши**: Кнопки быстрого доступа для частых действий

### Статистика и отслеживание
- **Подробная статистика**: Отслеживание общего времени, потраченного на каждый предмет
- **Сводка сессии**: Просмотр завершенных интервалов и общего рабочего времени после каждой сессии
- **Исторические данные**: Информация о последнем изучении каждого предмета и затраченном времени

### Пользовательский опыт
- **Интуитивный интерфейс**: Удобные встроенные и быстрые клавиатуры
- **Уведомления о прогрессе**: Автоматические оповещения об окончании периодов работы или отдыха
- **Исчерпывающая помощь**: Подробные справочные сообщения и подсказки для всех функций

## Технические детали
- Разработан на Python с использованием библиотеки python-telegram-bot
- Использует асинхронное программирование для отзывчивого взаимодействия с пользователем
- Реализует ConversationHandler для многоэтапного процесса настройки
- Постоянное хранение данных для пользовательской статистики и предпочтений
- Расширенное логирование для устранения неполадок и мониторинга производительности

## Команды
- `/start` - Начать новую учебную сессию
- `/stop` - Завершить текущий таймер
- `/stats` - Посмотреть статистику обучения
- `/help` - Показать справочную информацию
