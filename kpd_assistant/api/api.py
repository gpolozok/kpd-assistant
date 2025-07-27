import aiohttp
import json
import logging
import re

from fastapi import FastAPI, Depends, HTTPException, status
from pydantic import BaseModel, field_validator
from typing import Optional, Dict, Any

from kpd_assistant.lib.config import Config
from kpd_assistant.api.security import validate_api_key

from kpd_assistant.faq import FAQ
from kpd_assistant.prompt import PROMPT


log = logging.getLogger("system")
app = FastAPI()


class RequestData(BaseModel):
    text: str
    email: str
    role: Optional[str] = None

    @field_validator('email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        if not re.match(r"[^@]+@[^@]+\.[^@]+", v):
            raise ValueError("Invalid email format")
        return v

    @field_validator('text')
    @classmethod
    def text_must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError('Text must not be empty')
        return v

    @field_validator('role')
    @classmethod
    def role_must_be_valid(cls, v: Optional[str]) -> Optional[str]:
        valid_roles = ['заказчик', 'гип', 'инженер', 'наблюдатель',]
        if v is not None and v not in valid_roles:
            raise ValueError(
                'Role must be one of: заказчик, гип, инженер, наблюдатель'
            )
        return v

class ResponseModel(BaseModel):
    status: str
    data: Dict[str, Any]
    message: Optional[str] = None

@app.post(
    "/process",
    response_model=ResponseModel,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"description": "Invalid API key"},
        422: {"description": "Validation error"},
        500: {"description": "Internal server error"}
    }
)
async def process_data(
    data: RequestData,
    api_key: str = Depends(validate_api_key)
) -> Dict[str, Any]:
    """
    - **text**: required text field
    - **email**: valid email address
    - **role**: optional role (заказчик/гип/инженер/наблюдатель)
    """
    try:
        processed_data = {
            "processed_text": data.text,
            "email": data.email,
            "role": data.role or "default"
        }

        return {
            "status": "success",
            "data": processed_data,
            "message": await _form_answer(data.text)
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "data": None,
                "message": f"Internal server error: {str(e)}"
            }
        )

async def _form_answer(text: str) -> str:
    no_answer_reply = (
        "Благодарим за ваш вопрос! "
        "К сожалению, я не нашел подходящего ответа на ваш вопрос. "
        "Пожалуйста, напишите подробнее о вашей проблеме на почту "
        "mail@kpd.ru, и наши специалисты обязательно вам помогут."
    )

    questions_to_id = {v["question"]: k for k, v in FAQ.items()}
    prompt = PROMPT.format(
        user_question=text,
        db_questions=list(questions_to_id.keys())
    )
    
    if (ya_answer := await _ya_query_handler(prompt)) == "нет ответа":
        answer = no_answer_reply
    else:
        question = FAQ[questions_to_id[ya_answer]]
        answer = question["answer"]
        if question.get("url"):
            answer += f"\n\nБолее подробно: {question["url"]}"

    return answer

async def _ya_query_handler(prompt: str) -> str:
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
        async with aiohttp.ClientSession() as session:
            async with session.post(
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
