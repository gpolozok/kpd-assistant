import asyncio
import json
import logging
import re

from aiohttp import ClientSession
from datetime import datetime
from typing import Dict
from telegram import Update
from telegram.ext import (Application,
                          CommandHandler,
                          ContextTypes,
                          MessageHandler,
                          filters)

from kpd_assistant.lib.config import Config

from kpd_assistant.bot.info import INFORMATION
from kpd_assistant.faq import FAQ
from kpd_assistant.prompt import PROMPT


log = logging.getLogger("system")


class Bot:
    def __init__(self) -> None:
        self.conf = Config.project
        self.user_log = {}
        self.user_tasks = {}
        self.user_last_message_time: Dict[int, datetime] = {}
        self.active_requests: Dict[int, bool] = {}

        self.app = Application.builder().token(self.conf["bot_token"]).build()
        self._setup_handlers()

    def _setup_handlers(self) -> None:
        handlers = [
            CommandHandler(
                ["help", "start"],
                self._help,
                filters=filters.ChatType.PRIVATE
            ),
            MessageHandler(
                filters.ChatType.PRIVATE,
                self._handle_message
            )
        ]
        self.app.add_handlers(handlers)

    async def _startup(self) -> None:
        self.session = ClientSession()
        self.questions_to_id = {v["question"]: k for k, v in FAQ.items()}

    async def _shutdown(self) -> None:
        if self.session:
            await self.session.close()

    def run(self) -> None:
        loop = asyncio.get_event_loop()
        try:
            loop.run_until_complete(self._startup())
            loop.create_task(self.app.run_polling())
            loop.run_forever()
        except KeyboardInterrupt:
            log.info("Shutting down bot...")
        finally:
            loop.run_until_complete(self._shutdown())
            loop.close()

    async def _help(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        await update.effective_message.reply_text(INFORMATION)

    async def _handle_message(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        user_id = update.effective_user.id
        question = update.effective_message.text

        if self.active_requests.get(user_id, False):
            await update.message.reply_text("ЗАНЯТО!")
            return
        self.active_requests[user_id] = True

        try:
            self.user_tasks[user_id] = asyncio.create_task(
                self._get_answer(update, question)
            )
        except Exception:
            log.exception("Getting answer failed")
            await update.effective_message.reply_text("Произошла ошибка")
        finally:
            self.active_requests[user_id] = False
            self.user_tasks.pop(user_id, None)

    async def _get_answer(self, update: Update, question: str) -> str:
        prompt = PROMPT.format(
            user_question=question,
            db_questions=list(self.questions_to_id.keys())
        )

        if (answer := await self._ya_query_handler(prompt)) == "нет ответа":
            answer = await self._escape_markdown_v2(
                "Благодарим за ваш вопрос! "
                "К сожалению, я не нашел подходящего ответа на ваш вопрос. "
                "Пожалуйста, напишите подробнее о вашей проблеме на почту "
                "mail@kpd.ru, и наши специалисты обязательно вам помогут."
            )
        else:
            faq = FAQ[self.questions_to_id[answer]]
            answer = await self._escape_markdown_v2(faq["answer"])
            if faq.get("url"):
                answer += f"\n\nБолее подробно: [инструкция]({faq['url']})"
            
            answer += await self._escape_markdown_v2(
                "\n───────────\n"
                "Помог ли этот ответ? Если нет — пожалуйста, "
                "напишите на mail@kpd.ru. "
                "Ваши вопросы помогают нам становиться лучше!"
            )

        await update.effective_message.reply_text(
            text=answer,
            parse_mode="MarkdownV2",
            disable_web_page_preview=True
        )

    async def _ya_query_handler(self, prompt: str) -> str:
        url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Api-Key {Config.project["ya_api_key"]}"
        }
        data = {
            "modelUri": f"gpt://{Config.project["ya_folder_id"]}/yandexgpt",
            "completionOptions": {
                "stream": False,
                "temperature": 0,
                "maxTokens": 1000
            },
            "messages": [
                {
                    "role": "user",
                    "text": prompt
                }
            ]
        }

        try:
            async with self.session.post(
                url,
                headers=headers,
                json=data
            ) as resp:
                resp.raise_for_status()
                result = json.loads(await resp.text())
            return result['result']['alternatives'][0]['message']['text']
        except Exception:
            log.exception("")
            return "нет ответа"

    async def _escape_markdown_v2(self, text: str) -> str:
        return ''.join(
            f'\\{char}' if char in r'_*[]()~`>#+-=|{}.!'
            else char for char in text
        )