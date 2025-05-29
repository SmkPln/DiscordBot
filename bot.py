import discord
from discord.ext import commands
import os 
import pandas as pd
import asyncio
from config import settings
from discord import FFmpegPCMAudio
from collections import defaultdict

def load_questions():
    df = pd.read_excel("questions.xlsx")
    questions = {}

    for _, row in df.iterrows():
        category = row["Категорія"]
        points = row["Бали"]
        q_type = row["Тип"]
        q_data = row["Дані (файл/текст)"]
        question = row["Питання"]
        answer = row["Відповідь"]

        if category not in questions:
            questions[category] = {}

        questions[category][points] = (q_type, q_data, question, answer)

    return questions 


questions = load_questions()
player_scores = {} 
used_questions = set()

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.all())

    async def on_ready(self):
        guild = bot.get_guild(1171884455623925913)  # Заміна SERVER_ID на реальний ID вашого сервера
        bot_member = guild.get_member(bot.user.id)  # Отримуємо бота на сервері
        permissions = bot_member.guild_permissions  # Отримуємо всі дозволи для бота
        print(permissions)
        await self.tree.sync()  # Синхронізуємо команди
        print(f"Бот {self.user} підключився!")

bot = MyBot()

@bot.tree.command(name="show_questions", description="Показує всі доступні питання та їх статус")
async def show_questions(interaction: discord.Interaction):
    embed = discord.Embed(title="📜 Доступні питання", color=0x3498db)
    
    for category, points_dict in questions.items():
        question_list = []
        for points in sorted(points_dict.keys()):
            status = "✅" if (category, points) in used_questions else "❓"
            question_list.append(f"{status} **{points} балів**")
        
        embed.add_field(name=category, value="\n".join(question_list), inline=False)

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="choose", description="Вибрати питання")
async def choose(interaction: discord.Interaction, category: str, points: int):
    if (category, points) in used_questions:
        await interaction.response.send_message("⚠️ Це питання вже було використане!")
        return

    if category in questions and points in questions[category]:
        q_type, q_data, question_text, answer = questions[category][points]
        used_questions.add((category, points))  # Позначаємо питання як використане

        embed = discord.Embed(title=f"{category} - {points} балів", description=question_text, color=0x00ff00)

        if q_type == "image":  # 📷 Фото + Питання
            if not os.path.exists(q_data):
                await interaction.response.send_message("❌ Файл зображення не знайдено!")
                return
            file = discord.File(q_data, filename="question.jpg")
            embed.set_image(url="attachment://question.jpg")
            await interaction.response.send_message(file=file, embed=embed)

        elif q_type == "audio":  # 🔊 Звук + Питання
            if not os.path.exists(q_data):
                await interaction.response.send_message("❌ Файл аудіо не знайдено!")
                return
            file = discord.File(q_data, filename="question.mp3")
            await interaction.response.send_message(embed=embed, file=file)

        elif q_type == "text":  # 📝 Опис + Питання
            embed.add_field(name="Додаткова інформація", value=q_data, inline=False)
            await interaction.response.send_message(embed=embed)

        else:
            await interaction.response.send_message("⚠️ Невідомий тип питання!")
            return

        time_left = 60

        # Виводимо початкове повідомлення з таймером
        timer_message = await interaction.followup.send(f"⏳ Таймер: {time_left} секунд")

        async def update_timer():
            nonlocal time_left
            while time_left > 0:
                await asyncio.sleep(1)  # Затримка в 1 секунду
                time_left -= 1  # Зменшуємо таймер
                # Оновлюємо повідомлення з новим значенням таймера
                await timer_message.edit(content=f"⏳ Таймер: {time_left} секунд")

        # Запускаємо таймер в окремому асинхронному процесі
        timer_task = asyncio.create_task(update_timer())

        # Очікуємо відповідь
        def check(m):
            print(player_scores)
            return m.channel ==  interaction.channel and m.author != bot.user

        try:
            response = await bot.wait_for("message", check=check, timeout=time_left)
            if timer_task:
                timer_task.cancel()  # Скасовуємо задачу таймера
                await timer_message.delete() 
        except asyncio.TimeoutError:
            await interaction.followup.send("⏳ Час вичерпано! Ви не встигли дати відповідь.")
            return

        if response.content.strip().lower() == str(answer).strip().lower():
            player_scores[response.author.name] = player_scores.get(response.author.name, 0) + points
            await interaction.followup.send(f"✅ {response.author.mention} правильно! +{points} балів\n Зараз ти маєш {player_scores[response.author.name]} балів")
        else:
            await interaction.followup.send(f"❌ Неправильно! Відповідь: {answer}\n Зараз ти маєш {player_scores.get(response.author.name, 0)} балів")

@bot.tree.command(name="show_scores", description="Показує список балів всіх учасників")
async def show_scores(interaction: discord.Interaction):
    if not player_scores:
        await interaction.response.send_message("📊 Поки що ніхто не набрав балів!")
        return

    embed = discord.Embed(title="🏆 Турнірна таблиця", color=0xf1c40f)
    
    sorted_scores = sorted(player_scores.items(), key=lambda x: x[1], reverse=True)
    for i, (player, score) in enumerate(sorted_scores, start=1):
        embed.add_field(name=f"{i}. {player}", value=f"**{score} балів**", inline=False)

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="reset_scores", description="Скидає бали всіх учасників")
async def reset_scores(interaction: discord.Interaction):
    global player_scores
    player_scores = {}  # Очищуємо список балів
    await interaction.response.send_message("🔄 Всі бали було скинуто!")
            
# @bot.tree.command(name="check_all_questions", description="Виводить повну інформацію про всі питання для перевірки")
# async def check_all_questions(interaction: discord.Interaction):
#     await interaction.response.defer(thinking=True)  # Показати "бот друкує", якщо довго
    
#     for category, points_dict in questions.items():
#         for points, (q_type, q_data, question_text, answer) in sorted(points_dict.items()):
#             embed = discord.Embed(
#                 title=f"Категорія: {category} | {points} балів",
#                 description=f"**Тип:** {q_type}\n**Питання:** {question_text}\n**Відповідь:** {answer}",
#                 color=0x95a5a6
#             )

#             if q_type == "image" and os.path.exists(q_data):
#                 file = discord.File(q_data, filename="question.jpg")
#                 embed.set_image(url="attachment://question.jpg")
#                 await interaction.followup.send(embed=embed, file=file)
#             elif q_type == "audio" and os.path.exists(q_data):
#                 file = discord.File(q_data, filename="question.mp3")
#                 await interaction.followup.send(embed=embed, file=file)
#             elif q_type == "text":
#                 embed.add_field(name="Додаткові дані", value=q_data, inline=False)
#                 await interaction.followup.send(embed=embed)
#             else:
#                 await interaction.followup.send(embed=embed, content="⚠️ Не вдалося знайти файл або невідомий тип.")

#             await asyncio.sleep(1.5)  # Затримка, щоб уникнути rate-limit'у






# Таймери, щоб не запускати декілька разів
channel_timers = {}

@bot.event
async def on_voice_state_update(member, before, after):
    # Перевіряємо, чи користувач зайшов у канал
    if before.channel is None and after.channel is not None:
        channel = after.channel
        members = [m for m in channel.members if not m.bot]  # Тільки не-боти

        if len(members) >= 2 and channel.id not in channel_timers:
            print(f"✅ У каналі {channel.name} тепер {len(members)} учасників. Запуск таймера на 10 хв...")
            channel_timers[channel.id] = True
            await asyncio.create_task(play_after_delay(channel))

async def play_after_delay(channel):
    await asyncio.sleep(10 * 60)  # Затримка 5 хвилин

    # Перевірка: чи досі є 2+ людей в голосовому каналі
    if channel and len([m for m in channel.members if not m.bot]) >= 2:
        print(f"🎵 Відтворення в {channel.name} після 10 хвилин.")
        await join_and_play_sound(channel)
    else:
        print(f"❌ Менше ніж 2 учасники в {channel.name} після 10 хв. Пропускаємо звук.")

    # Очищаємо таймер
    channel_timers.pop(channel.id, None)


async def join_and_play_sound(channel):
    # Приєднуємо бота до голосового каналу
    voice_channel = channel
    voice_client = await voice_channel.connect()

    # Вказуємо шлях до FFmpeg, якщо він не в PATH
    ffmpeg_path = r"C:\Users\alexa\Desktop\BotDiscordGame\ffmpeg-7.1.1-essentials_build\ffmpeg-7.1.1-essentials_build\bin\ffmpeg.exe"  # Замініть на реальний шлях до вашого FFmpeg

    # Програємо звук
    audio_source = FFmpegPCMAudio("sounds/V1.mpeg", executable=ffmpeg_path)
    voice_client.play(audio_source)

    # Зачекаємо, поки звук програється, і потім від'єднаємо бота від каналу
    while voice_client.is_playing():
        await asyncio.sleep(1)

    await voice_client.disconnect()


bot.run(settings['TOKEN'])