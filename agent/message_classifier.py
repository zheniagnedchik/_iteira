#!/usr/bin/env python3
"""
Модуль для классификации сообщений и извлечения переменных классификации
"""

import re
import logging
from typing import Dict, Tuple, Optional
from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from .prompts import IRRELEVANT_CLASSIFICATION_PROMPT

logger = logging.getLogger(__name__)

class MessageClassifier:
    """Класс для классификации сообщений пользователей"""
    
    def __init__(self, llm: ChatOpenAI):
        self.llm = llm
    
    def extract_classification_variables(self, llm_response: str) -> Dict[str, int]:
        """
        Извлекает переменные классификации из ответа LLM
        
        Args:
            llm_response: Ответ от LLM с переменными классификации
            
        Returns:
            Словарь с переменными классификации
        """
        try:
            # Ищем строку с переменными классификации
            pattern_line_with_vars = r'.*query_classification_variables.*\n?'
            match_result = re.search(pattern_line_with_vars, llm_response)
            
            if not match_result:
                logger.warning("[CLASSIFIER] Переменные классификации не найдены в ответе LLM")
                return {
                    "is_client_question_irrelevant_to_context": 0,
                    "does_client_asks_human_support": 0
                }
            
            extracted_variables_line = llm_response[match_result.start():match_result.end()]
            logger.info(f"[CLASSIFIER] Извлеченная строка переменных: {extracted_variables_line}")
            
            # Извлекаем переменные
            variables = {
                "is_client_question_irrelevant_to_context": 0,
                "does_client_asks_human_support": 0
            }
            
            # Проверяем нерелевантность вопроса
            pattern_irrelevant = r'is_client_question_irrelevant_to_context=(\d)'
            irrelevant_match = re.search(pattern_irrelevant, extracted_variables_line)
            if irrelevant_match:
                variables["is_client_question_irrelevant_to_context"] = int(irrelevant_match.group(1))
            
            # Проверяем запрос поддержки человека
            pattern_human_support = r'does_client_asks_human_support=(\d)'
            human_support_match = re.search(pattern_human_support, extracted_variables_line)
            if human_support_match:
                variables["does_client_asks_human_support"] = int(human_support_match.group(1))
            
            logger.info(f"[CLASSIFIER] Извлеченные переменные: {variables}")
            return variables
            
        except Exception as e:
            logger.error(f"[CLASSIFIER] Ошибка извлечения переменных классификации: {e}")
            return {
                "is_client_question_irrelevant_to_context": 0,
                "does_client_asks_human_support": 0
            }
    
    def extract_clean_response(self, llm_response: str) -> str:
        """
        Извлекает чистый ответ без переменных классификации
        
        Args:
            llm_response: Полный ответ от LLM
            
        Returns:
            Чистый ответ для пользователя
        """
        try:
            # Ищем все до строки с переменными классификации
            pattern = r'[\s\S]*?(?=\n.*?query_classification_variables|$)'
            match_result = re.search(pattern, llm_response)
            
            if match_result:
                clean_response = llm_response[:match_result.end()]
                # Убираем строку с переменными если она попала
                clean_response = re.sub(r'\n.*?query_classification_variables.*', '', clean_response)
                return clean_response.strip()
            
            return llm_response.strip()
            
        except Exception as e:
            logger.error(f"[CLASSIFIER] Ошибка извлечения чистого ответа: {e}")
            return llm_response.strip()
    
    def classify_message(self, user_message: str, client_name: str = "клиент", gender: str = "неизвестен") -> Tuple[str, Dict[str, int]]:
        """
        Классифицирует сообщение пользователя и возвращает ответ с переменными
        
        Args:
            user_message: Сообщение пользователя
            client_name: Имя клиента
            gender: Пол клиента
            
        Returns:
            Кортеж (чистый_ответ, переменные_классификации)
        """
        try:
            # Создаем промпт для классификации
            prompt = ChatPromptTemplate.from_messages([
                ("system", IRRELEVANT_CLASSIFICATION_PROMPT.format(client_name=client_name, gender=gender)),
                ("human", "{query}")
            ])
            
            # Получаем ответ от LLM
            chain = prompt | self.llm
            response = chain.invoke({"query": user_message})
            
            if not isinstance(response, AIMessage):
                logger.error(f"[CLASSIFIER] Неожиданный тип ответа: {type(response)}")
                return user_message, {
                    "is_client_question_irrelevant_to_context": 0,
                    "does_client_asks_human_support": 0
                }
            
            llm_response = response.content
            logger.info(f"[CLASSIFIER] Полный ответ LLM: {llm_response}")
            
            # Извлекаем переменные классификации
            classification_vars = self.extract_classification_variables(llm_response)
            
            # Извлекаем чистый ответ
            clean_response = self.extract_clean_response(llm_response)
            
            return clean_response, classification_vars
            
        except Exception as e:
            logger.error(f"[CLASSIFIER] Ошибка классификации сообщения: {e}")
            return "Извините, произошла ошибка при обработке вашего сообщения.", {
                "is_client_question_irrelevant_to_context": 0,
                "does_client_asks_human_support": 0
            }



