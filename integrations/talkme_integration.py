#!/usr/bin/env python3
"""
Оптимизированная интеграция с TalkMe API
Единый модуль для обработки webhook'ов и отправки сообщений
"""

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import asyncio
import logging
import json
import time
from datetime import datetime
import traceback

from agent.consultation_agent import ConsultationAgent
from agent.state import ConsultationState
from langchain_core.messages import HumanMessage, AIMessage
from services.talkme_api import (
    send_message_to_client, 
    simulate_typing, 
    finish_custom_bot,
    validate_token,
    prepare_message_for_talkme,
    get_api_status
)
import os

# Настройка логирования
logger = logging.getLogger(__name__)

class TalkMeMessage(BaseModel):
    """Модель входящего сообщения от Talk Me"""
    token: str = Field(..., description="API токен для ответа")
    session_id: str = Field(..., description="ID сессии")
    user_id: str = Field(..., description="ID пользователя")
    message: str = Field(..., description="Текст сообщения")
    phone_number: Optional[str] = Field(None, description="Номер телефона")
    message_type: str = Field(default="text", description="Тип сообщения")
    timestamp: Optional[str] = Field(None, description="Временная метка")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Дополнительные данные")

class TalkMeResponse(BaseModel):
    """Модель ответа для Talk Me"""
    success: bool = Field(default=True, description="Статус успеха")
    message: Optional[str] = Field(None, description="Ответное сообщение")
    session_id: str = Field(..., description="ID сессии")
    end_conversation: bool = Field(default=False, description="Завершить разговор")
    error: Optional[str] = Field(None, description="Сообщение об ошибке")

class TalkMeIntegration:
    """Основной класс интеграции с TalkMe"""
    
    def __init__(self):
        self.consultation_agent = ConsultationAgent()
        # В продакшене лучше использовать Redis
        self.user_states: Dict[str, Dict[str, Any]] = {}
        self.session_stats = {
            "total_sessions": 0,
            "active_sessions": 0,
            "messages_processed": 0,
            "errors": 0
        }
        # Тестовый режим - не отправляем реальные API вызовы
        self.test_mode = os.getenv("TALKME_TEST_MODE", "true").lower() == "true"
        if self.test_mode:
            logger.info("[TALKME] Запущен в тестовом режиме - API вызовы симулируются")
        
    def get_or_create_user_state(self, user_id: str, phone_number: str = None) -> Dict[str, Any]:
        """Получить или создать состояние пользователя"""
        if user_id not in self.user_states:
            self.user_states[user_id] = {
                "session_id": user_id,
                "need_rag": True,
                "client_name": None,
                "gender": None,
                "phone_number": phone_number,
                "messages": [],
                "created_at": datetime.now().isoformat(),
                "last_activity": datetime.now().isoformat()
            }
            self.session_stats["total_sessions"] += 1
            self.session_stats["active_sessions"] += 1
            logger.info(f"[TALKME] Создано новое состояние для пользователя {user_id[:10]}...")
        else:
            # Обновляем время последней активности
            self.user_states[user_id]["last_activity"] = datetime.now().isoformat()
            
        return self.user_states[user_id]
    
    def _simulate_api_call(self, action: str, token: str, data: Any = None) -> bool:
        """Симуляция API вызова в тестовом режиме"""
        if not self.test_mode:
            return False
        
        logger.info(f"[TALKME_TEST] Симуляция {action} с токеном {token[:15]}...")
        if data:
            logger.info(f"[TALKME_TEST] Данные: {str(data)[:100]}...")
        
        # Симулируем успешный вызов
        time.sleep(0.1)  # Небольшая задержка для реалистичности
        return True
    
    def parse_talkme_webhook(self, data: Dict[str, Any]) -> TalkMeMessage:
        """Парсинг webhook данных от TalkMe в унифицированный формат"""
        try:
            # Извлекаем токен
            token = data.get('token', '')
            if not token:
                raise ValueError("Отсутствует токен аутентификации")
            
            # Валидируем токен
            if not validate_token(token):
                raise ValueError("Невалидный токен аутентификации")
            
            # Извлекаем session_id
            session_id = data.get('session_id', '')
            if 'originalOnlineChatMessage' in data:
                session_id = session_id or str(data['originalOnlineChatMessage'].get('dialogId', ''))
            
            # Извлекаем user_id
            user_id = data.get('user_id', '')
            if 'client' in data:
                user_id = user_id or data['client'].get('clientId', data['client'].get('login', ''))
            
            # Извлекаем номер телефона
            phone_number = None
            if 'client' in data:
                phone_number = data['client'].get('phone', '')
            else:
                phone_number = data.get('phone_number', data.get('caller_number', data.get('from', '')))
            
            # Извлекаем текст сообщения
            message = ''
            message_data = data.get('message', {})
            if isinstance(message_data, dict):
                message = message_data.get('text', '')
            else:
                message = str(message_data) if message_data else ''
                
            # Fallback для других форматов
            if not message:
                message = data.get('text', data.get('body', ''))
            
            # Генерируем fallback ID если нужно
            if not user_id:
                user_id = session_id or f"user_{int(time.time())}"
            if not session_id:
                session_id = user_id or f"session_{int(time.time())}"
            
            if not message:
                raise ValueError("Пустое сообщение")
            
            return TalkMeMessage(
                token=token,
                session_id=session_id,
                user_id=user_id,
                message=message,
                phone_number=phone_number,
                message_type=data.get('message_type', 'text'),
                timestamp=data.get('timestamp'),
                metadata=data.get('metadata', {})
            )
            
        except Exception as e:
            logger.error(f"[TALKME] Ошибка парсинга webhook: {e}")
            logger.error(f"[TALKME] Данные: {json.dumps(data, ensure_ascii=False)[:500]}...")
            raise HTTPException(status_code=400, detail=f"Ошибка парсинга данных: {str(e)}")
    
    async def process_message(self, talkme_msg: TalkMeMessage) -> TalkMeResponse:
        """Основная логика обработки сообщения"""
        try:
            logger.info(f"[TALKME] Обработка сообщения от {talkme_msg.user_id[:10]}...: {talkme_msg.message[:50]}...")
            
            # Получаем состояние пользователя
            user_state = self.get_or_create_user_state(talkme_msg.user_id, talkme_msg.phone_number)
            
            # Показываем индикатор печати (не критично если не получится)
            if self.test_mode:
                self._simulate_api_call("simulate_typing", talkme_msg.token, {"ttl": 15})
            else:
                simulate_typing(talkme_msg.token, ttl=15)
            
            # Если это первое сообщение, отправляем приветствие
            if not user_state["messages"]:
                welcome_message = (
                    "Добро пожаловать! "
                    "Рады приветствовать Вас в Итейра — сети салонов премиум‑класса. "
                    "Я — Ваш персональный виртуальный помощник. "
                    "С удовольствием проконсультирую вас по услугам и помогу с выбором процедуры. "
                    "Как я могу к Вам обращаться?"
                )
                
                # Добавляем приветствие в историю
                user_state["messages"].append(AIMessage(content=welcome_message))
                
                # Подготавливаем и отправляем через API
                prepared_message = prepare_message_for_talkme(welcome_message)
                if self.test_mode:
                    success = self._simulate_api_call("send_message", talkme_msg.token, prepared_message)
                else:
                    success = send_message_to_client(talkme_msg.token, prepared_message)
                if not success:
                    logger.error(f"[TALKME] Не удалось отправить приветствие для {talkme_msg.user_id}")
                    raise HTTPException(status_code=500, detail="Ошибка отправки приветствия")
                
                self.session_stats["messages_processed"] += 1
                return TalkMeResponse(
                    success=True,
                    session_id=talkme_msg.session_id,
                    message="Приветствие отправлено"
                )
            
            # Добавляем сообщение пользователя в историю
            user_message = HumanMessage(content=talkme_msg.message)
            user_state["messages"].append(user_message)
            
            # Получаем ответ от агента
            logger.info(f"[TALKME] Вызов агента для пользователя {talkme_msg.user_id[:10]}...")
            try:
                response = self.consultation_agent.run(talkme_msg.user_id, user_state)
                logger.info(f"[TALKME] Получен ответ от агента, сообщений в истории: {len(response.get('messages', []))}")
            except Exception as agent_error:
                logger.error(f"[TALKME] Ошибка агента: {agent_error}")
                # Отправляем сообщение об ошибке пользователю
                error_message = "Извините, произошла техническая ошибка. Пожалуйста, повторите ваш запрос."
                if not self.test_mode:
                    send_message_to_client(talkme_msg.token, error_message)
                else:
                    self._simulate_api_call("send_message", talkme_msg.token, error_message)
                self.session_stats["errors"] += 1
                raise HTTPException(status_code=500, detail="Ошибка обработки агентом")
            
            # Проверяем специальные случаи классификации
            # Обновляем состояние пользователя
            self.user_states[talkme_msg.user_id] = response
            
            # Извлекаем ответ от AI (последнее сообщение без tool_calls)
            bot_response = "Извините, не удалось получить ответ."
            if "messages" in response and response["messages"]:
                for msg in reversed(response["messages"]):
                    if isinstance(msg, AIMessage) and msg.content:
                        # Пропускаем сообщения с tool_calls
                        has_tool_calls = (hasattr(msg, 'additional_kwargs') and 
                                        'tool_calls' in msg.additional_kwargs and 
                                        msg.additional_kwargs['tool_calls'])
                        if not has_tool_calls:
                            bot_response = msg.content
                            break
            
            # Парсим переменные классификации из ответа (как в nfkd.py)
            is_irrelevant = 0
            asks_human_support = 0
            
            # Извлекаем чистый ответ без переменных классификации
            extracted_llm_response = bot_response
            
            # Проверяем наличие переменных классификации
            import re
            pattern = r'[\s\S]*?(?=\n.*?query_classification_variables|$)'
            match_result = re.search(pattern, bot_response)
            if match_result:
                extracted_llm_response = bot_response[:match_result.end()]
                
                # Ищем строку с переменными классификации
                pattern_line_with_vars = r'.*query_classification_variables.*\n?'
                match_result = re.search(pattern_line_with_vars, bot_response)
                
                if match_result:
                    extracted_variables_line = bot_response[match_result.start():match_result.end()]
                    logger.info(f"[TALKME] Найдены переменные классификации: {extracted_variables_line}")
                    
                    # Извлекаем переменную нерелевантности
                    pattern_irrelevant = r'is_client_question_irrelevant_to_context=(\d)'
                    irrelevant_match = re.search(pattern_irrelevant, extracted_variables_line)
                    if irrelevant_match:
                        is_irrelevant = int(irrelevant_match.group(1))
                    
                    # Извлекаем переменную запроса поддержки
                    pattern_human_support = r'does_client_asks_human_support=(\d)'
                    human_support_match = re.search(pattern_human_support, extracted_variables_line)
                    if human_support_match:
                        asks_human_support = int(human_support_match.group(1))
                    
                    logger.info(f"[TALKME] Классификация: irrelevant={is_irrelevant}, human_support={asks_human_support}")
            
            # Используем чистый ответ без переменных для отправки клиенту
            bot_response = extracted_llm_response.strip()
            
            # Подготавливаем и отправляем ответ через TalkMe API
            prepared_response = prepare_message_for_talkme(bot_response)
            if self.test_mode:
                success = self._simulate_api_call("send_message", talkme_msg.token, prepared_response)
            else:
                success = send_message_to_client(talkme_msg.token, prepared_response)
            if not success:
                logger.error(f"[TALKME] Не удалось отправить ответ для {talkme_msg.user_id}")
                self.session_stats["errors"] += 1
                raise HTTPException(status_code=500, detail="Ошибка отправки ответа")
            
            # Отправляем коды классификации в TalkMe для счетчиков (БЕЗ завершения диалога)
            if is_irrelevant == 1:
                logger.info(f"[TALKME] НЕРЕЛЕВАНТНЫЙ вопрос от клиента {talkme_msg.user_id[:10]}... (отправляем код IRRELEVANT_MESSAGE)")
                # Отправляем код для инкремента счетчика, но НЕ завершаем диалог
                if self.test_mode:
                    self._simulate_api_call("finish_bot", talkme_msg.token, {"code": "IRRELEVANT_MESSAGE"})
                    logger.info(f"[TALKME] (ТЕСТ) Код IRRELEVANT_MESSAGE отправлен для счетчика")
                else:
                    success = finish_custom_bot(talkme_msg.token, "IRRELEVANT_MESSAGE")
                    if success:
                        logger.info(f"[TALKME] Код IRRELEVANT_MESSAGE отправлен для инкремента счетчика")
                    else:
                        logger.warning(f"[TALKME] Не удалось отправить код IRRELEVANT_MESSAGE")
            
            if asks_human_support == 1:
                logger.info(f"[TALKME] ЗАПРОС ПОДДЕРЖКИ от клиента {talkme_msg.user_id[:10]}... (отправляем код OPERATOR_REQUEST)")
                # Отправляем код для переключения на оператора, но НЕ завершаем диалог
                if self.test_mode:
                    self._simulate_api_call("finish_bot", talkme_msg.token, {"code": "OPERATOR_REQUEST"})
                    logger.info(f"[TALKME] (ТЕСТ) Код OPERATOR_REQUEST отправлен для переключения на оператора")
                else:
                    success = finish_custom_bot(talkme_msg.token, "OPERATOR_REQUEST")
                    if success:
                        logger.info(f"[TALKME] Код OPERATOR_REQUEST отправлен для переключения на оператора")
                    else:
                        logger.warning(f"[TALKME] Не удалось отправить код OPERATOR_REQUEST")
            
            # Проверяем, предлагает ли агент запись (по ключевым словам в ответе)
            booking_keywords = [
                "для записи на услугу вы можете",
                "оставить свой номер телефона", 
                "администратор свяжется с вами",
                "контакт передан администратору"
            ]
            
            is_booking_offer = any(keyword.lower() in bot_response.lower() for keyword in booking_keywords)
            
            if is_booking_offer:
                logger.info(f"[TALKME] ПРЕДЛОЖЕНИЕ ЗАПИСИ от агента клиенту {talkme_msg.user_id[:10]}... (отправляем код OPERATOR_REQUEST)")
                # Отправляем код для переключения на оператора при предложении записи
                if self.test_mode:
                    self._simulate_api_call("finish_bot", talkme_msg.token, {"code": "OPERATOR_REQUEST"})
                    logger.info(f"[TALKME] (ТЕСТ) Код OPERATOR_REQUEST отправлен при предложении записи")
                else:
                    success = finish_custom_bot(talkme_msg.token, "OPERATOR_REQUEST")
                    if success:
                        logger.info(f"[TALKME] Код OPERATOR_REQUEST отправлен при предложении записи")
                    else:
                        logger.warning(f"[TALKME] Не удалось отправить код OPERATOR_REQUEST при предложении записи")
            
            # Обрабатываем стандартные случаи завершения диалога
            finish_code = None
            end_conversation = False
            
            # Проверяем стандартные правила завершения разговора (НЕ связанные с классификацией)
            end_conversation = self._should_end_conversation(bot_response)
            if end_conversation:
                finish_code = "SUCCESS"
            
            # Отправляем код завершения если необходимо
            if finish_code:
                if self.test_mode:
                    self._simulate_api_call("finish_bot", talkme_msg.token, {"code": finish_code})
                    logger.info(f"[TALKME] (ТЕСТ) Код завершения '{finish_code}' отправлен")
                else:
                    success = finish_custom_bot(talkme_msg.token, finish_code)
                    if success:
                        logger.info(f"[TALKME] Код завершения '{finish_code}' отправлен успешно")
                    else:
                        logger.warning(f"[TALKME] Не удалось отправить код завершения '{finish_code}'")
                
                # Очищаем сессию при завершении
                self._cleanup_session(talkme_msg.user_id)
            
            self.session_stats["messages_processed"] += 1
            logger.info(f"[TALKME] Ответ отправлен пользователю {talkme_msg.user_id[:10]}...: {bot_response[:100]}...")
            
            return TalkMeResponse(
                success=True,
                session_id=talkme_msg.session_id,
                message="Ответ отправлен",
                end_conversation=end_conversation
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"[TALKME] Критическая ошибка при обработке сообщения: {e}")
            logger.error(f"[TALKME] Traceback: {traceback.format_exc()}")
            
            # Пытаемся отправить сообщение об ошибке пользователю
            try:
                error_message = "Извините, произошла техническая ошибка. Пожалуйста, повторите ваш запрос позже."
                send_message_to_client(talkme_msg.token, error_message)
            except:
                pass
            
            self.session_stats["errors"] += 1
            return TalkMeResponse(
                success=False,
                session_id=talkme_msg.session_id,
                error=str(e)
            )
    
    def _should_end_conversation(self, message: str) -> bool:
        """Определяем, нужно ли завершить разговор"""
        end_keywords = [
            "до свидания", "всего доброго", "спасибо за обращение",
            "хорошего дня", "всего хорошего", "до встречи",
            "обращайтесь еще", "рады были помочь"
        ]
        message_lower = message.lower()
        return any(keyword in message_lower for keyword in end_keywords)
    
    def _cleanup_session(self, user_id: str):
        """Очистка сессии при завершении разговора"""
        if user_id in self.user_states:
            del self.user_states[user_id]
            self.session_stats["active_sessions"] = max(0, self.session_stats["active_sessions"] - 1)
            logger.info(f"[TALKME] Сессия {user_id[:10]}... завершена и очищена")
    
    def get_stats(self) -> Dict[str, Any]:
        """Получить статистику работы интеграции"""
        return {
            **self.session_stats,
            "active_sessions_details": [
                {
                    "user_id": user_id[:10] + "...",
                    "messages_count": len(state.get("messages", [])),
                    "client_name": state.get("client_name"),
                    "phone_number": state.get("phone_number"),
                    "created_at": state.get("created_at"),
                    "last_activity": state.get("last_activity")
                }
                for user_id, state in self.user_states.items()
            ]
        }
    
    def clear_session(self, user_id: str) -> Dict[str, str]:
        """Очистить конкретную сессию"""
        if user_id in self.user_states:
            del self.user_states[user_id]
            self.session_stats["active_sessions"] = max(0, self.session_stats["active_sessions"] - 1)
            return {"message": f"Сессия пользователя {user_id} очищена"}
        else:
            raise HTTPException(status_code=404, detail="Сессия не найдена")
    
    def clear_all_sessions(self) -> Dict[str, Any]:
        """Очистить все сессии"""
        cleared_count = len(self.user_states)
        self.user_states.clear()
        self.session_stats["active_sessions"] = 0
        return {
            "message": f"Очищено {cleared_count} сессий",
            "cleared_sessions": cleared_count
        }

# Глобальный экземпляр интеграции
talkme_integration = TalkMeIntegration()

# Обработчики для FastAPI
async def handle_talkme_webhook(request: Request) -> JSONResponse:
    """Обработчик webhook от TalkMe"""
    try:
        # Получаем и парсим данные
        body = await request.body()
        logger.info(f"[TALKME_WEBHOOK] Получен webhook, размер: {len(body)} байт")
        logger.info(f"[TALKME_WEBHOOK] Headers: {dict(request.headers)}")
        logger.info(f"[TALKME_WEBHOOK] Raw body: {body.decode('utf-8', errors='replace')[:1000]}...")
        
        try:
            data = json.loads(body.decode('utf-8'))
            logger.info(f"[TALKME_WEBHOOK] Parsed JSON: {json.dumps(data, ensure_ascii=False, indent=2)}")
        except json.JSONDecodeError as e:
            logger.error(f"[TALKME_WEBHOOK] Ошибка парсинга JSON: {e}")
            logger.error(f"[TALKME_WEBHOOK] Проблемное тело: {body}")
            raise HTTPException(status_code=400, detail=f"Неверный JSON: {e}")
        
        # Парсим в унифицированный формат
        try:
            logger.info(f"[TALKME_WEBHOOK] Начинаем парсинг webhook данных...")
            talkme_msg = talkme_integration.parse_talkme_webhook(data)
            logger.info(f"[TALKME_WEBHOOK] Парсинг успешен: user_id={talkme_msg.user_id}, session_id={talkme_msg.session_id}")
        except Exception as parse_error:
            logger.error(f"[TALKME_WEBHOOK] Ошибка парсинга webhook: {parse_error}")
            logger.error(f"[TALKME_WEBHOOK] Traceback: {traceback.format_exc()}")
            raise HTTPException(status_code=400, detail=f"Ошибка парсинга webhook: {str(parse_error)}")
        
        # Обрабатываем сообщение
        try:
            logger.info(f"[TALKME_WEBHOOK] Начинаем обработку сообщения...")
            response = await talkme_integration.process_message(talkme_msg)
            logger.info(f"[TALKME_WEBHOOK] Обработка завершена успешно")
        except Exception as process_error:
            logger.error(f"[TALKME_WEBHOOK] Ошибка обработки сообщения: {process_error}")
            logger.error(f"[TALKME_WEBHOOK] Traceback: {traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=f"Ошибка обработки: {str(process_error)}")
        
        # Возвращаем результат
        result = response.model_dump()
        logger.info(f"[TALKME_WEBHOOK] Возвращаем результат: {result}")
        return JSONResponse(content=result)
        
    except HTTPException as http_error:
        logger.error(f"[TALKME_WEBHOOK] HTTP ошибка: {http_error.status_code} - {http_error.detail}")
        raise
    except Exception as e:
        logger.error(f"[TALKME_WEBHOOK] Критическая ошибка в webhook: {e}")
        logger.error(f"[TALKME_WEBHOOK] Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

async def get_talkme_stats() -> Dict[str, Any]:
    """Получить статистику TalkMe интеграции"""
    return talkme_integration.get_stats()

async def clear_talkme_session(user_id: str) -> Dict[str, str]:
    """Очистить сессию TalkMe"""
    return talkme_integration.clear_session(user_id)

async def clear_all_talkme_sessions() -> Dict[str, Any]:
    """Очистить все сессии TalkMe"""
    return talkme_integration.clear_all_sessions()
