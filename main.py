from aiogram import Bot, Dispatcher
from aiogram.types import Message, BotCommand, BotCommandScopeDefault
from config import TELEGRAM_BOT_TOKEN
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from agent.consultation_agent import ConsultationAgent
from agent.state import ConsultationState
from utils.audio_transcribition import transcribe_with_whisper
from langchain_core.messages import HumanMessage
import asyncio

# Initialize the bot
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
consultation_agent = ConsultationAgent()


@dp.message(Command("start"))
async def start_cmd(message: Message, state: FSMContext):
    """
    Handle the /start command. Clear the state and send welcome message.
    """
    try:
        await state.clear()
        # Initialize consultation state with all fields reset
        consultation_state = ConsultationState(
            session_id=str(message.from_user.id),
            full_name=None,
            program_number=None,
            contract_number=None,
            gender=None,
            guarantee_data={},
            messages=[]
        )
        await state.update_data(consultation_state=consultation_state)

        await message.answer(
            "*Добро пожаловать!*\n"
            "Рады приветствовать Вас в Итейра — сети салонов премиум‑класса.\n\n"
            "Я — Ваш персональный виртуальный помощник. С удовольствием проконсультирую вас по услугам и помогу с выбором процедуры\n\n"

            "*Как я могу к Вам обращаться?*",
            parse_mode="Markdown",
            
        )
    except Exception as e:
        print(f"Error in start_cmd: {e}")
        await message.answer("⚠️ Произошла ошибка при обработке вашего запроса.\nПожалуйста, попробуйте позже.")

async def set_bot_commands():
    commands = [
        BotCommand(command="start", description="Сменить пользователя"),
    ]
    await bot.set_my_commands(commands, BotCommandScopeDefault())

@dp.message()
async def process_user_message(message: Message, state: FSMContext):
    
    try:
        await message.bot.send_chat_action(message.from_user.id, action="typing")
        
        # Check whether the message is voice or text
        if message.voice:
            # Transcribe with Whisper
            user_input = await transcribe_with_whisper(message.bot, message.voice)

            if not user_input:
                # If transcription failed (empty string)
                await message.answer("⚠️ Извините, не удалось распознать ваш голос.\nПожалуйста, попробуйте ещё раз или введите ваш запрос в текстовом виде.")
                return
        else:
            # Regular text message
            user_input = message.text

        # Get current consultation state
        user_data = await state.get_data()
        consultation_state = user_data.get("consultation_state", {
            "session_id": str(message.from_user.id),
            "need_rag": True,
            "client_name": None,
            "gender": None,
            "messages": []
        })

        # Add user message to consultation state
        consultation_state["messages"].append(HumanMessage(content=user_input))

        # Process with consultation agent
        updated_state = consultation_agent.run(
            session_id=str(message.from_user.id),
            state=consultation_state
        )

        # Save updated state
        await state.update_data(consultation_state=updated_state)

        # Send the last AI message to user
        if updated_state["messages"]:
            last_ai_message = next(
                (msg for msg in reversed(updated_state["messages"]) 
                if msg.type == "ai" and not msg.additional_kwargs.get("tool_calls")),
                None
            )
            if last_ai_message:
                # Check if this is a special case where we're asking for the procedure directly
                if (updated_state.get("client_name") == "клиент" and 
                    updated_state.get("gender") == "неизвестен" and
                    "расскажите, какая процедура вас интересует?" in last_ai_message.content):
                    # Don't send the message asking for procedure as we're already processing the procedure
                    pass
                else:
                    await message.answer(
                        last_ai_message.content,
                        parse_mode="Markdown"
                    )
            else:
                await message.answer("⚠️ Извините, не удалось сформировать ответ.")

    except Exception as e:
        print(f"Error in process_user_message: {e}")
        await message.answer("⚠️ Произошла ошибка при обработке диалога.\nПожалуйста, попробуйте позже.")


# Run a Telegram bot
async def main():
    try:
        await set_bot_commands()
        print("Telegram Bot is running")
        await dp.start_polling(bot)
    except Exception as e:
        print(f"Bot crushed with error: {e}")


if __name__ == "__main__":
    asyncio.run(main())