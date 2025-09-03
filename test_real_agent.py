#!/usr/bin/env python3
"""
Тест с реальным агентом для проверки переменных классификации
"""

import sys
import os

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_real_agent():
    """Тест с реальным агентом"""
    try:
        from agent.consultation_agent import ConsultationAgent
        from langchain_core.messages import HumanMessage
        
        print("🤖 Тестирование с реальным агентом")
        print("=" * 60)
        
        agent = ConsultationAgent()
        
        # Тест 1: Нерелевантный вопрос
        print("📤 Тест 1: Отправляем нерелевантный вопрос: 'Как написать программу на Python?'")
        test_state_1 = {
            "session_id": "test_session_1",
            "need_rag": True,
            "client_name": "Тестовый клиент",
            "gender": "неизвестен",
            "messages": [HumanMessage(content="Как написать программу на Python?")]
        }
        
        response_1 = agent.run("test_session_1", test_state_1)
        analyze_response(response_1, "Нерелевантный вопрос", expected_irrelevant=1)
        
        print("\n" + "-" * 60 + "\n")
        
        # Тест 2: Релевантный вопрос
        print("📤 Тест 2: Отправляем релевантный вопрос: 'Хочу сделать маникюр'")
        test_state_2 = {
            "session_id": "test_session_2",
            "need_rag": True,
            "client_name": "Анна",
            "gender": "женщина",
            "messages": [HumanMessage(content="Хочу сделать маникюр")]
        }
        
        response_2 = agent.run("test_session_2", test_state_2)
        analyze_response(response_2, "Релевантный вопрос", expected_irrelevant=0)
        
        print("\n" + "-" * 60 + "\n")
        
        # Тест 3: Запрос поддержки
        print("📤 Тест 3: Отправляем запрос поддержки: 'Хочу поговорить с администратором'")
        test_state_3 = {
            "session_id": "test_session_3",
            "need_rag": True,
            "client_name": "Петр",
            "gender": "мужчина",
            "messages": [HumanMessage(content="Хочу поговорить с администратором")]
        }
        
        response_3 = agent.run("test_session_3", test_state_3)
        analyze_response(response_3, "Запрос поддержки", expected_human_support=1)
        
    except Exception as e:
        print(f"❌ Ошибка при тестировании с реальным агентом: {e}")
        import traceback
        traceback.print_exc()

def analyze_response(response, test_name, expected_irrelevant=0, expected_human_support=0):
    """Анализ ответа агента"""
    print(f"📥 Анализ ответа для теста: {test_name}")
    
    if "messages" in response and response["messages"]:
        from langchain_core.messages import AIMessage
        for msg in reversed(response["messages"]):
            if isinstance(msg, AIMessage) and msg.content:
                has_tool_calls = (hasattr(msg, 'additional_kwargs') and 
                                'tool_calls' in msg.additional_kwargs and 
                                msg.additional_kwargs['tool_calls'])
                if not has_tool_calls:
                    bot_response = msg.content
                    print(f"🤖 Ответ агента:\n{bot_response}")
                    print()
                    
                    # Проверяем наличие переменных классификации
                    if 'query_classification_variables' in bot_response:
                        print("✅ Переменные классификации найдены в ответе!")
                        
                        # Парсим переменные
                        import re
                        
                        is_irrelevant = 0
                        asks_human_support = 0
                        
                        # Ищем строку с переменными
                        pattern_line_with_vars = r'.*query_classification_variables.*\n?'
                        match_result = re.search(pattern_line_with_vars, bot_response)
                        
                        if match_result:
                            extracted_variables_line = bot_response[match_result.start():match_result.end()]
                            
                            # Извлекаем переменные
                            pattern_irrelevant = r'is_client_question_irrelevant_to_context=(\d)'
                            irrelevant_match = re.search(pattern_irrelevant, extracted_variables_line)
                            if irrelevant_match:
                                is_irrelevant = int(irrelevant_match.group(1))
                            
                            pattern_human_support = r'does_client_asks_human_support=(\d)'
                            human_support_match = re.search(pattern_human_support, extracted_variables_line)
                            if human_support_match:
                                asks_human_support = int(human_support_match.group(1))
                            
                            print(f"🔍 Результат парсинга:")
                            print(f"  - Нерелевантный: {is_irrelevant} (ожидаем: {expected_irrelevant})")
                            print(f"  - Запрос поддержки: {asks_human_support} (ожидаем: {expected_human_support})")
                            
                            # Проверяем соответствие ожиданиям
                            if is_irrelevant == expected_irrelevant and asks_human_support == expected_human_support:
                                print("✅ Классификация КОРРЕКТНА!")
                            else:
                                print("❌ Классификация НЕКОРРЕКТНА!")
                                
                        else:
                            print("❌ Не удалось извлечь строку с переменными")
                            
                    else:
                        print("❌ Переменные классификации НЕ найдены в ответе")
                        print("⚠️  Возможно, промпт не работает как ожидалось")
                    break
    else:
        print("❌ Не получен ответ от агента")

if __name__ == "__main__":
    test_real_agent()
