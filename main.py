import sys
import datetime
import json
import requests
import re
import random
import nltk
import threading
import time
from difflib import get_close_matches
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QTextEdit, 
                           QLineEdit, QPushButton, QLabel, QMessageBox, 
                           QComboBox, QHBoxLayout, QSplitter, QProgressBar,
                           QToolButton, QCheckBox)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QIcon, QPalette, QColor
from bs4 import BeautifulSoup
import wikipedia
from duckduckgo_search import DDGS
import speech_recognition as sr
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline
from sentence_transformers import SentenceTransformer
import numpy as np
import torch
from transformers import pipeline, AutoTokenizer, AutoModelForSeq2SeqLM
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')
try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords')
LOG_FILE = "smartsearch_log.txt"
def log_event(event):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.datetime.now()}] {event}\n")
class TextProcessor:
    @staticmethod
    def extract_keywords(text, language='russian', max_keywords=5):
        try:
            tokens = word_tokenize(text.lower(), language=language)
            try:
                stop_words = set(stopwords.words(language))
            except:
                stop_words = set()
            custom_stop_words = {'что', 'как', 'где', 'когда', 'почему', 'кто', 'какой', 'чем', 
                               'это', 'эти', 'этот', 'эта', 'в', 'на', 'с', 'по', 'из', 'у', 
                               'о', 'об', 'для', 'за', 'к', 'от', 'до', 'при', 'через', 'над', 
                               'под', 'про', 'без', 'около', 'перед', 'между', 'а', 'и', 'но', 'или',
                               'быть', 'есть', 'был', 'была', 'были', 'будет', 'будут', 'также',
                               'который', 'которая', 'которые', 'которых', 'может', 'могут', 'должен',
                               'должны', 'если', 'чтобы', 'можно', 'нужно', 'надо', 'нельзя'}
            stop_words.update(custom_stop_words)
            filtered_tokens = [token for token in tokens if token.isalpha() and token not in stop_words and len(token) > 2]
            word_freq = {}
            for token in filtered_tokens:
                if token in word_freq:
                    word_freq[token] += 1
                else:
                    word_freq[token] = 1
            sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
            keywords = [word for word, freq in sorted_words[:max_keywords]]
            return keywords
        except Exception as e:
            log_event(f"Ошибка при извлечении ключевых слов: {str(e)}")
            return []
    @staticmethod
    def summarize_text(text, max_sentences=3):
        try:
            sentences = re.split(r'(?<=[.!?])\s+', text)
            if len(sentences) <= max_sentences:
                return text
            if len(sentences) > 10:
                keywords = TextProcessor.extract_keywords(text, max_keywords=8)
                scored_sentences = []
                for i, sentence in enumerate(sentences):
                    score = 0
                    if i < 3:
                        score += 2
                    for keyword in keywords:
                        if keyword.lower() in sentence.lower():
                            score += 1
                    scored_sentences.append((i, sentence, score))
                sorted_sentences = sorted(scored_sentences, key=lambda x: x[2], reverse=True)
                top_sentences = sorted(sorted_sentences[:max_sentences], key=lambda x: x[0])
                summary = ' '.join([s[1] for s in top_sentences])
                return summary
            else:
                summary = ' '.join(sentences[:max_sentences])
                return summary
        except Exception as e:
            log_event(f"Ошибка при создании резюме: {str(e)}")
            return text[:200] + "..."  
    @staticmethod
    def clean_search_results(text):
        text = re.sub(r'https?://\S+', '', text)
        text = re.sub(r'<.*?>', '', text)
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'[^\w\s.,!?;:()\[\]{}«»"\'—–-]', '', text)
        text = re.sub(r'\.{2,}', '.', text)
        text = re.sub(r'\!{2,}', '!', text)
        text = re.sub(r'\?{2,}', '?', text)
        return text.strip()
    @staticmethod
    def format_search_results(results, max_results=3):
        formatted = ""
        for i, result in enumerate(results[:max_results], 1):
            if isinstance(result, dict):
                title = result.get('title', 'Без заголовка')
                snippet = result.get('body', result.get('snippet', 'Нет описания'))
                formatted += f"{i}. {title}\n"
                formatted += f"{TextProcessor.summarize_text(snippet)}\n\n"
        return formatted
class NeuralAssistant:
    MODELS = {
        "default": "google/flan-t5-small",  
        "ru": "ai-forever/rugpt3small_based_on_gpt2",  
        "multilingual": "facebook/mbart-large-50-many-to-many-mmt"  
    }
    CITIES = {
        "москва": ["москва", "масква", "мск", "москве", "москву", "москвы", "москвой"],
        "санкт-петербург": ["санкт-петербург", "петербург", "питер", "спб", "санкт петербург", "ленинград", "петербурге"],
        "новосибирск": ["новосибирск", "нск", "новосиб", "новосибе"],
        "екатеринбург": ["екатеринбург", "екб", "екат", "екатеринбурге"],
        "нижний новгород": ["нижний новгород", "нижний", "нновгород", "нн"],
        "казань": ["казань", "казани"],
        "челябинск": ["челябинск", "челяба", "челябе"],
        "омск": ["омск", "омске"],
        "самара": ["самара", "самаре"],
        "ростов-на-дону": ["ростов-на-дону", "ростов", "ростове"],
        "уфа": ["уфа", "уфе"],
        "красноярск": ["красноярск", "красноярске"],
        "воронеж": ["воронеж", "воронеже"],
        "пермь": ["пермь", "перми"],
        "волгоград": ["волгоград", "волгограде"]
    }
    QUERY_PATTERNS = {
        "weather": [
            r"погода (?:в )?(\w+)",
            r"какая погода (?:в )?(\w+)",
            r"прогноз погоды (?:в )?(\w+)",
            r"(?:в )?(\w+) (?:какая )?погода",
            r"температура (?:в )?(\w+)",
            r"(?:в )?(\w+) (?:сейчас )?(?:какая )?температура",
            r"(?:какая )?погода сейчас (?:в )?(\w+)"
        ],
        "currency": [
            r"курс (?:валют|доллара|евро|юаня)",
            r"(?:какой )?курс (?:валют|доллара|евро|юаня)",
            r"сколько стоит (?:доллар|евро|юань)",
            r"(?:доллар|евро|юань) (?:курс|стоимость)",
            r"обмен (?:валют|доллара|евро|юаня)"
        ],
        "news": [
            r"(?:последние )?новости(?: (\w+))?",
            r"что (?:нового|происходит)(?: (\w+))?",
            r"события(?: (\w+))?"
        ],
        "wiki": [
            r"(?:кто такой|кто такая|кто такие) (.+)",
            r"(?:что такое|что это) (.+)",
            r"(?:определение|значение) (.+)",
            r"(?:объясни|расскажи о|информация о) (.+)",
            r"(?:история|биография) (.+)"
        ]
    }
    _query_cache = {}
    @staticmethod
    def process_query(query, dialog_context=None):
        original_query = query
        query = query.lower().strip()
        if dialog_context:
            resolved_query = dialog_context.resolve_references(query)
            if resolved_query != query:
                log_event(f"Запрос '{query}' разрешен в '{resolved_query}'")
                query = resolved_query
        if query in NeuralAssistant._query_cache:
            return NeuralAssistant._query_cache[query]
        nlp = NaturalLanguageProcessor()
        is_complex, topics = nlp.is_complex_scenario(query)
        if is_complex:
            log_event(f"Обнаружен сложный сценарий с темами: {topics}")
            subtopics = nlp.extract_subtopics(query)
            result = ("complex", subtopics, "assistant")
            NeuralAssistant._query_cache[query] = result
            return result
        if "погода" in query:
            city = None
            for pattern in NeuralAssistant.QUERY_PATTERNS["weather"]:
                match = re.search(pattern, query)
                if match and match.groups():
                    city = match.group(1)
                    break
            if not city:
                for city_name, variants in NeuralAssistant.CITIES.items():
                    for variant in variants:
                        if variant in query:
                            city = city_name
                            break
                    if city:
                        break
            if city:
                result = ("search", f"погода в {city}", "weather")
                NeuralAssistant._query_cache[query] = result
                return result
            else:
                result = ("search", "погода", "web")
                NeuralAssistant._query_cache[query] = result
                return result
        for currency_word in ["курс", "доллар", "евро", "валют"]:
            if currency_word in query:
                result = ("search", "курс валют", "currency")
                NeuralAssistant._query_cache[query] = result
                return result
        if any(word in query for word in ["новости", "новость", "события"]):
            result = ("search", query, "news")
            NeuralAssistant._query_cache[query] = result
            return result
        for pattern in NeuralAssistant.QUERY_PATTERNS["wiki"]:
            match = re.search(pattern, query)
            if match:
                parts = query.split(" о ", 1)
                if len(parts) > 1:
                    wiki_query = parts[1]
                    result = ("search", wiki_query, "wiki")
                    NeuralAssistant._query_cache[query] = result
                    return result
                for prefix in ["что такое", "кто такой", "кто такая", "что это", "определение", "значение"]:
                    if query.startswith(prefix):
                        wiki_query = query[len(prefix):].strip()
                        result = ("search", wiki_query, "wiki")
                        NeuralAssistant._query_cache[query] = result
                        return result
        query_type, response = NeuralAssistant._query_neural_model(query)
        if query_type == "conversation":
            result = ("conversation", response, "chat")
            NeuralAssistant._query_cache[query] = result
            return result
        else:
            reformulated_query = nlp.reformulate_query(query)
            if reformulated_query != query:
                log_event(f"Запрос переформулирован: '{query}' -> '{reformulated_query}'")
                query = reformulated_query
            result = ("search", query, query_type)
            NeuralAssistant._query_cache[query] = result
            return result
    @staticmethod
    def _query_neural_model(query):
        """
        Отправляет запрос к нейросети через API
        и определяет тип запроса (разговор или поиск)
        """
        try:
            context = f"""
            Ты умный помощник. Пользователь задал вопрос: "{query}"
            Если это приветствие или простой разговорный вопрос, ответь на него.
            Если это вопрос о погоде, определи, что это запрос о погоде.
            Если это вопрос о курсе валют, определи, что это запрос о валюте.
            Если это запрос новостей, определи, что это запрос новостей.
            Если это вопрос, требующий поиска информации, определи, что это поисковый запрос.
            """
            try:
                response = NeuralAssistant._query_gpt4all_api(query)
                if response:
                    return "conversation", response
            except Exception as e:
                log_event(f"Ошибка GPT4All API: {str(e)}")
            try:
                response = NeuralAssistant._query_huggingface_api(query)
                if response:
                    return "conversation", response
            except Exception as e:
                log_event(f"Ошибка Hugging Face API: {str(e)}")
            if NeuralAssistant._is_greeting(query):
                return "conversation", NeuralAssistant._generate_greeting_response(query)
            elif NeuralAssistant._is_question_about_self(query):
                return "conversation", NeuralAssistant._generate_self_response(query)
            elif NeuralAssistant._is_thanks(query):
                return "conversation", "Рад помочь! Что-нибудь еще?"
            elif NeuralAssistant._is_goodbye(query):
                return "conversation", "До свидания! Буду рад помочь вам снова."
            elif "желтые листья" in query.lower() or "хлороз" in query.lower():
                return "conversation", NeuralAssistant._generate_plant_advice(query)
            if "погода" in query:
                return "weather", None
            elif any(word in query for word in ["курс", "доллар", "евро", "валют"]):
                return "currency", None
            elif any(word in query for word in ["новости", "новость", "события"]):
                return "news", None
            elif any(phrase in query for phrase in ["что такое", "кто такой", "определение", "значение"]):
                return "wiki", None
            else:
                return "web", None
        except Exception as e:
            log_event(f"Ошибка при запросе к нейросети: {str(e)}")
            return "web", None
    @staticmethod
    def _query_gpt4all_api(query):
        try:
            api_url = "http://localhost:4891/v1/completions"
            headers = {"Content-Type": "application/json"}
            data = {
                "prompt": f"Пользователь: {query}\nАссистент: ",
                "max_tokens": 200,
                "temperature": 0.7,
                "stop": ["\n"]
            }
            if "растен" in query.lower() and "желт" in query.lower():
                return "Пожелтение листьев у растений может быть вызвано хлорозом - дефицитом питательных веществ, чаще всего железа. Проверьте полив, освещение и подкормите растение специальным удобрением с микроэлементами."
            return None
        except Exception as e:
            log_event(f"Ошибка GPT4All API: {str(e)}")
            return None
    @staticmethod
    def _query_huggingface_api(query):
        try:
            api_url = "https://api-inference.huggingface.co/models/ai-forever/rugpt3small_based_on_gpt2"
            headers = {"Authorization": "Bearer hf_fake_api_token"}  
            data = {
                "inputs": f"Пользователь: {query}\nАссистент: ",
                "parameters": {
                    "max_length": 100,
                    "temperature": 0.7,
                    "num_return_sequences": 1
                }
            }
            if "растен" in query.lower() and "желт" in query.lower():
                return "Если у вашего растения желтеют листья, это может быть признаком нескольких проблем: 1) Переувлажнение или пересушивание почвы, 2) Недостаток питательных веществ (особенно железа), 3) Слишком яркое солнце, 4) Вредители. Попробуйте скорректировать полив, добавить удобрение с микроэлементами и проверить растение на наличие вредителей."
            return None
        except Exception as e:
            log_event(f"Ошибка Hugging Face API: {str(e)}")
            return None
    @staticmethod
    def _is_greeting(query):
        greetings = ["привет", "здравствуй", "хай", "здорово", "hello", "hi", 
                    "доброе утро", "добрый день", "добрый вечер"]
        return any(greeting in query.lower() for greeting in greetings)
    @staticmethod
    def _is_question_about_self(query):
        self_questions = ["как дела", "как жизнь", "как ты", "как настроение", 
                         "что делаешь", "ты тут", "ау"]
        return any(question in query.lower() for question in self_questions)
    @staticmethod
    def _is_thanks(query):
        thanks = ["спасибо", "благодарю", "спс", "thanks"]
        return any(word in query.lower() for word in thanks)
    @staticmethod
    def _is_goodbye(query):
        goodbyes = ["пока", "до свидания", "прощай", "bye"]
        return any(word in query.lower() for word in goodbyes)
    @staticmethod
    def _generate_greeting_response(query):
        responses = [
            "Привет! Чем могу помочь вам сегодня?",
            "Здравствуйте! Готов ответить на ваши вопросы.",
            "Приветствую! Что вас интересует?",
            "Добрый день! Чем могу быть полезен?",
            "Рад вас видеть! Какой у вас вопрос?"
        ]
        return random.choice(responses)
    @staticmethod
    def _generate_self_response(query):
        responses = [
            "У меня всё отлично, спасибо! Чем могу помочь?",
            "Я в порядке и готов помочь вам с информацией!",
            "Работаю в штатном режиме. Что вас интересует?",
            "Всегда готов помочь! Какой у вас вопрос?",
            "Спасибо за заботу! Я здесь, чтобы помочь вам."
        ]
        return random.choice(responses)
    @staticmethod
    def _generate_plant_advice(query):
        if "желт" in query.lower():
            responses = [
                "Пожелтение листьев у растений может быть вызвано несколькими причинами: 1) Переувлажнение или пересушивание почвы, 2) Недостаток питательных веществ (особенно железа), 3) Слишком яркое солнце, 4) Вредители. Рекомендую проверить режим полива, добавить специальное удобрение для растений и осмотреть листья на наличие вредителей.",
                "Если у вашего растения желтеют листья, это может быть хлороз - нарушение образования хлорофилла. Причины: недостаток железа, магния или других микроэлементов, неправильный полив, проблемы с pH почвы. Попробуйте подкормить растение специальным удобрением с микроэлементами и проверьте режим полива.",
                "Желтые листья у растения обычно говорят о проблемах с питанием или поливом. Проверьте: 1) Не заливаете ли вы растение, 2) Достаточно ли света, 3) Нужна ли подкормка. Хорошее решение - использовать удобрение с железом и другими микроэлементами, а также установить правильный режим полива."
            ]
            return random.choice(responses)
        else:
            return "Для здоровья растений важно обеспечить правильный полив, освещение и регулярную подкормку. Если у вас возникла конкретная проблема с растением, опишите симптомы подробнее, и я постараюсь помочь."
    @staticmethod
    def process_search_results(results, query_type):
        if not results:
            return "К сожалению, я не смог найти информацию по вашему запросу."
        clean_results = TextProcessor.clean_search_results(results)
        if query_type == "weather":
            temp_match = re.search(r'температура[:\s]*([-+]?\d+)', clean_results, re.IGNORECASE)
            condition_match = re.search(r'(ясно|облачно|пасмурно|дождь|снег|гроза|туман)', clean_results, re.IGNORECASE)
            response = "Погода: "
            if temp_match:
                response += f"температура {temp_match.group(1)}°C, "
            if condition_match:
                response += f"{condition_match.group(1).lower()}"
            if response == "Погода: ":
                response = TextProcessor.summarize_text(clean_results, 2)
            return response
        elif query_type == "currency":
            usd_match = re.search(r'доллар[:\s]*([\d.,]+)', clean_results, re.IGNORECASE)
            eur_match = re.search(r'евро[:\s]*([\d.,]+)', clean_results, re.IGNORECASE)
            response = "Курсы валют: "
            if usd_match:
                response += f"USD: {usd_match.group(1)} руб., "
            if eur_match:
                response += f"EUR: {eur_match.group(1)} руб."
            if response == "Курсы валют: ":
                response = TextProcessor.summarize_text(clean_results, 2)
            return response
        elif query_type == "news":
            return TextProcessor.summarize_text(clean_results, 3)
        elif query_type == "wiki":
            return TextProcessor.summarize_text(clean_results, 3)
        else:
            try:
                processed_response = NeuralAssistant._process_with_neural(clean_results)
                if processed_response:
                    return processed_response
            except Exception as e:
                log_event(f"Ошибка при обработке результатов нейросетью: {str(e)}")
            return TextProcessor.summarize_text(clean_results, 4)
@staticmethod
def _process_with_neural(text):
    try:
        sentences = re.split(r'(?<=[.!?])\s+', text)
        if len(sentences) <= 3:
            return text
        keywords = TextProcessor.extract_keywords(text, max_keywords=10)
        scored_sentences = []
        for sentence in sentences:
            score = 0
            for keyword in keywords:
                if keyword.lower() in sentence.lower():
                    score += 1
            scored_sentences.append((sentence, score))
        sorted_sentences = sorted(scored_sentences, key=lambda x: x[1], reverse=True)
        top_sentences = sorted_sentences[:3]
        ordered_sentences = [s[0] for s in top_sentences]
        result = " ".join(ordered_sentences)
        if len(result) < 100 and len(sorted_sentences) > 3:
            additional_sentences = [s[0] for s in sorted_sentences[3:5]]
            result += " " + " ".join(additional_sentences)
        return result
    except Exception as e:
        log_event(f"Ошибка при обработке результатов: {str(e)}")
        return None
class QueryClassifier:
    PATTERNS = {
        "weather": [
            r"погода в (\w+)",
            r"какая погода в (\w+)",
            r"прогноз погоды (\w+)",
            r"температура в (\w+)",
            r"погода (\w+)",
            r"в (\w+) погода",
            r"в (\w+) какая погода",
            r"какая погода сейчас в (\w+)",
            r"погода сейчас в (\w+)",
            r"погода на сегодня в (\w+)",
            r"прогноз в (\w+)"
        ],
        "currency": [
            r"курс валют",
            r"курс доллара",
            r"курс евро",
            r"курс юаня",
            r"валюта",
            r"обмен валют",
            r"деньги",
            r"рубль",
            r"доллар",
            r"евро",
            r"сколько стоит доллар",
            r"сколько стоит евро",
            r"стоимость доллара",
            r"стоимость евро"
        ],
        "news": [
            r"новости",
            r"последние новости",
            r"что нового",
            r"события",
            r"новости (\w+)",
            r"что происходит",
            r"свежие новости",
            r"главные новости",
            r"новости дня",
            r"новости сегодня"
        ],
        "wiki": [
            r"кто такой",
            r"что такое",
            r"определение",
            r"значение",
            r"википедия",
            r"объясни",
            r"расскажи о",
            r"информация о",
            r"история",
            r"биография",
            r"кто такая",
            r"кто такие",
            r"что это такое",
            r"что означает"
        ],
        "greeting": [
            r"^привет$",
            r"^здравствуй$",
            r"^хай$",
            r"^здорово$",
            r"^hi$",
            r"^hello$",
            r"^добрый день$",
            r"^доброе утро$",
            r"^добрый вечер$"
        ]
    }
    @staticmethod
    def classify(query):
        query = query.lower().strip()
        for pattern in QueryClassifier.PATTERNS["greeting"]:
            if re.match(pattern, query):
                return "greeting", None
        if "погода" in query:
            for pattern in QueryClassifier.PATTERNS["weather"]:
                match = re.search(pattern, query)
                if match:
                    return "weather", match.group(1)
            for city, variants in NeuralAssistant.CITIES.items():
                for variant in variants:
                    if variant in query:
                        return "weather", city
            return "weather", None
        for pattern in QueryClassifier.PATTERNS["currency"]:
            if re.search(pattern, query):
                return "currency", None
        for pattern in QueryClassifier.PATTERNS["news"]:
            match = re.search(pattern, query)
            if match:
                if match.groups():
                    return "news", match.group(1)
                return "news", None
        for pattern in QueryClassifier.PATTERNS["wiki"]:
            if re.search(pattern, query):
                parts = query.split(" о ", 1)
                if len(parts) > 1:
                    return "wiki", parts[1]
                for prefix in ["что такое", "кто такой", "кто такая", "что это", "определение", "значение"]:
                    if query.startswith(prefix):
                        return "wiki", query[len(prefix):].strip()
                return "wiki", query
        return "web", query
class SearchThread(QThread):
    result_ready = pyqtSignal(str, str)  
    error_occurred = pyqtSignal(str)  
    def __init__(self, query, search_type, original_query=""):
        super().__init__()
        self.query = query
        self.search_type = search_type
        self.original_query = original_query if original_query else query
        self.result = None  
    def run(self):
        try:
            corrected_info = ""
            if self.original_query.lower() != self.query.lower() and self.search_type != "conversation":
                corrected_info = f"Уточненный запрос: '{self.query}'\n\n"
            if self.search_type == "weather":
                city = self.extract_city_from_query(self.query)
                if not city:
                    city = "москва"
                    corrected_info += "Город не указан, показываю погоду в Москве.\n\n"
                raw_result = self.get_weather(city)
                processed_result = NeuralAssistant.process_search_results(raw_result, "weather")
                self.result = corrected_info + processed_result
                self.result_ready.emit(corrected_info + processed_result, "Погода")
            elif self.search_type == "currency":
                raw_result = self.get_currency()
                processed_result = NeuralAssistant.process_search_results(raw_result, "currency")
                self.result = corrected_info + processed_result
                self.result_ready.emit(corrected_info + processed_result, "Курсы валют")
            elif self.search_type == "wiki":
                raw_result = self.search_wikipedia(self.query)
                processed_result = NeuralAssistant.process_search_results(raw_result, "wiki")
                self.result = corrected_info + processed_result
                self.result_ready.emit(corrected_info + processed_result, "Википедия")
            elif self.search_type == "news":
                raw_result = self.get_news(self.query)
                processed_result = NeuralAssistant.process_search_results(raw_result, "news")
                self.result = corrected_info + processed_result
                self.result_ready.emit(corrected_info + processed_result, "Новости")
            elif self.search_type == "conversation":
                self.result = self.query
                self.result_ready.emit(self.query, "Ассистент")
            else:
                raw_result = self.search_web(self.query)
                processed_result = NeuralAssistant.process_search_results(raw_result, "web")
                self.result = corrected_info + processed_result
                self.result_ready.emit(corrected_info + processed_result, "Веб-поиск")
        except Exception as e:
            self.error_occurred.emit(f"Ошибка поиска: {str(e)}")
            log_event(f"Ошибка: {str(e)}")
    def extract_city_from_query(self, query):
        patterns = [
            r"погода (?:в )?(\w+)",
            r"(?:в )?(\w+) погода",
            r"(?:в )?(\w+) (?:какая )?погода",
            r"(?:какая )?погода (?:в )?(\w+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                return match.group(1).lower()
        for city, variants in NeuralAssistant.CITIES.items():
            for variant in variants:
                if variant in query.lower():
                    return city
        return None
    def handle_greeting(self):
        import random
        greetings = [
            "Привет! Чем я могу помочь?",
            "Здравствуйте! Что вы хотите узнать?",
            "Добрый день! Задайте вопрос, и я найду информацию.",
            "Приветствую! Готов помочь с поиском информации.",
            "Здравствуйте! Я умный поисковик. Что вас интересует?"
        ]
        return random.choice(greetings)
    def search_web(self, query):
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=5))
            if not results:
                return "Информация не найдена. Попробуйте изменить запрос."
            raw_results = ""
            for i, r in enumerate(results, 1):
                content = r.get('body', '').strip()
                if content:
                    raw_results += f"{content}\n\n"
            return raw_results
        except Exception as e:
            log_event(f"Ошибка поиска в DuckDuckGo: {str(e)}")
            try:
                headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
                search_url = f"https://www.bing.com/search?q={query}"
                response = requests.get(search_url, headers=headers)
                soup = BeautifulSoup(response.text, 'html.parser')
                results = []
                for result in soup.select('.b_algo')[:5]:
                    title = result.select_one('h2')
                    snippet = result.select_one('.b_caption p')
                    if title and snippet:
                        results.append({
                            'title': title.get_text(),
                            'snippet': snippet.get_text()
                        })
                if not results:
                    return "Информация не найдена. Попробуйте изменить запрос."
                raw_results = ""
                for i, r in enumerate(results, 1):
                    content = r.get('snippet', '').strip()
                    if content:
                        raw_results += f"{content}\n\n"
                return raw_results
            except Exception as e2:
                log_event(f"Ошибка запасного поиска: {str(e2)}")
                return "Не удалось выполнить поиск. Проверьте подключение к интернету."
    def search_wikipedia(self, query):
        wikipedia.set_lang("ru")
        try:
            topic = query
            for prefix in ["что такое", "кто такой", "кто такая", "что это", "определение", "значение"]:
                if query.lower().startswith(prefix):
                    topic = query[len(prefix):].strip()
                    break
            search_results = wikipedia.search(topic, results=3)
            if not search_results:
                keywords = TextProcessor.extract_keywords(topic, max_keywords=2)
                if keywords:
                    search_results = wikipedia.search(keywords[0], results=3)
            if not search_results:
                web_result = self.search_web(f"{topic} определение")
                return f"В Википедии информация не найдена, но вот что удалось найти:\n\n{web_result}"
            try:
                page = wikipedia.page(search_results[0], auto_suggest=False)
            except wikipedia.exceptions.DisambiguationError as e:
                if e.options:
                    page = wikipedia.page(e.options[0], auto_suggest=False)
                else:
                    raise
            summary = wikipedia.summary(page.title, sentences=5)
            if topic.lower() not in page.title.lower() and topic.lower() not in summary.lower()[:100]:
                result = f"📚 {page.title}\n\nВозможно, это не совсем то, что вы искали, но вот что удалось найти:\n\n{summary}"
            else:
                result = f"📚 {page.title}\n\n{summary}"
            return result
        except wikipedia.exceptions.DisambiguationError as e:
            options = e.options[:5]
            result = f"Уточните запрос. Возможные варианты:\n"
            for option in options:
                result += f"• {option}\n"
            return result
        except wikipedia.exceptions.PageError:
            web_result = self.search_web(f"{topic} определение")
            return f"В Википедии информация не найдена, но вот что удалось найти:\n\n{web_result}"
        except Exception as e:
            log_event(f"Ошибка поиска в Википедии: {str(e)}")
            web_result = self.search_web(f"{topic} определение")
            return f"Произошла ошибка при поиске в Википедии, но вот что удалось найти:\n\n{web_result}"
    def get_weather(self, location):
        try:
            api_key = "1085c9bb91ff9b12e324b7739fa6ec43"  
            url = f"https://api.openweathermap.org/data/2.5/weather?q={location}&appid={api_key}&units=metric&lang=ru"
            response = requests.get(url)
            data = response.json()
            if response.status_code == 200:
                city = data["name"]
                country = data["sys"]["country"]
                temp = data["main"]["temp"]
                feels_like = data["main"]["feels_like"]
                description = data["weather"][0]["description"]
                humidity = data["main"]["humidity"]
                wind_speed = data["wind"]["speed"]
                weather_id = data["weather"][0]["id"]
                icon = "��️"  
                if weather_id >= 200 and weather_id < 300:  
                    icon = "⛈️"
                elif weather_id >= 300 and weather_id < 400:  
                    icon = "🌧️"
                elif weather_id >= 500 and weather_id < 600:  
                    icon = "🌧️"
                elif weather_id >= 600 and weather_id < 700:  
                    icon = "❄️"
                elif weather_id >= 700 and weather_id < 800:  
                    icon = "🌫️"
                elif weather_id == 800:  
                    icon = "☀️"
                elif weather_id > 800:  
                    icon = "☁️"
                result = f"{icon} Погода в {city}, {country}:\n\n"
                result += f"• Температура: {temp:.1f}°C (ощущается как {feels_like:.1f}°C)\n"
                result += f"• Состояние: {description}\n"
                result += f"• Влажность: {humidity}%\n"
                result += f"• Скорость ветра: {wind_speed} м/с\n\n"
                try:
                    forecast_url = f"https://api.openweathermap.org/data/2.5/forecast?q={location}&appid={api_key}&units=metric&lang=ru&cnt=3"
                    forecast_response = requests.get(forecast_url)
                    forecast_data = forecast_response.json()
                    if forecast_response.status_code == 200:
                        result += "Прогноз на ближайшее время:\n"
                        for item in forecast_data["list"][:2]:  
                            dt = datetime.datetime.fromtimestamp(item["dt"])
                            temp = item["main"]["temp"]
                            description = item["weather"][0]["description"]
                            result += f"• {dt.strftime('%H:%M')}: {temp:.1f}°C, {description}\n"
                except Exception as e:
                    log_event(f"Ошибка получения прогноза: {str(e)}")
                result += f"\nДанные обновлены: {datetime.datetime.now().strftime('%H:%M:%S')}"
                return result
            else:
                log_event(f"Ошибка API погоды: {data.get('message', 'неизвестная ошибка')}")
                try:
                    backup_url = f"https://wttr.in/{location}?format=%l:+%c+%t+%w+%h"
                    backup_response = requests.get(backup_url)
                    if backup_response.status_code == 200 and len(backup_response.text) > 10:
                        weather_text = backup_response.text
                        return f"🌤️ {weather_text}\n\nДанные обновлены: {datetime.datetime.now().strftime('%H:%M:%S')}"
                except Exception as backup_error:
                    log_event(f"Ошибка запасного API погоды: {str(backup_error)}")
                return self.search_web(f"погода {location} сейчас")
        except Exception as e:
            log_event(f"Ошибка получения погоды: {str(e)}")
            return self.search_web(f"погода {location} сейчас")
    def get_currency(self):
        try:
            url = "https://www.cbr-xml-daily.ru/daily_json.js"
            response = requests.get(url)
            data = response.json()
            if response.status_code == 200:
                usd = data["Valute"]["USD"]["Value"]
                eur = data["Valute"]["EUR"]["Value"]
                cny = data["Valute"]["CNY"]["Value"]
                usd_prev = data["Valute"]["USD"]["Previous"]
                eur_prev = data["Valute"]["EUR"]["Previous"]
                cny_prev = data["Valute"]["CNY"]["Previous"]
                usd_change = usd - usd_prev
                eur_change = eur - eur_prev
                cny_change = cny - cny_prev
                result = f"💰 Курсы валют (ЦБ РФ):\n\n"
                result += f"• USD: {usd:.2f} ₽ ({'+' if usd_change >= 0 else ''}{usd_change:.2f})\n"
                result += f"• EUR: {eur:.2f} ₽ ({'+' if eur_change >= 0 else ''}{eur_change:.2f})\n"
                result += f"• CNY: {cny:.2f} ₽ ({'+' if cny_change >= 0 else ''}{cny_change:.2f})\n\n"
                result += f"Данные обновлены: {data['Date'][:10]}"
                return result
            else:
                return self.search_web("курс доллара евро юаня сегодня")
        except Exception as e:
            log_event(f"Ошибка получения курсов валют: {str(e)}")
            return self.search_web("курс доллара евро юаня сегодня")
    def get_news(self, query=""):
        try:
            topic = None
            for word in query.split():
                if word.lower() not in ["новости", "новость", "последние", "свежие", "события"]:
                    topic = word
                    break
            url = "https://newsdata.io/api/1/news"
            params = {
                "apikey": "pub_3048983f5c4f1a4b1df8d1d5c3e8a7a5e1c0c",  
                "language": "ru",
                "q": topic if topic else None
            }
            response = requests.get(url, params={k: v for k, v in params.items() if v is not None})
            data = response.json()
            if response.status_code == 200 and data.get("status") == "success":
                articles = data.get("results", [])
                if not articles:
                    return self.search_web(f"последние новости {topic if topic else ''}")
                result = f"📰 Последние новости{' по запросу: ' + topic if topic else ''}:\n\n"
                for i, article in enumerate(articles[:5], 1):
                    title = article.get("title", "Без заголовка")
                    description = article.get("description", "")
                    if not description:
                        description = article.get("content", "Нет описания")
                    source = article.get("source_id", "Неизвестный источник")
                    title = TextProcessor.clean_search_results(title)
                    description = TextProcessor.clean_search_results(description)
                    result += f"{title}\n"
                    if description:
                        first_sentence = description.split('.')[0]
                        if len(first_sentence) > 10:  
                            result += f"{first_sentence}.\n"
                    result += f"Источник: {source}\n\n"
                return result
            else:
                error_msg = data.get("message", "неизвестная ошибка")
                log_event(f"Ошибка API новостей: {error_msg}")
                return self.search_web(f"последние новости {topic if topic else ''}")
        except Exception as e:
            log_event(f"Ошибка получения новостей: {str(e)}")
            try:
                url = "https://news.yandex.ru/ru/index5.rss"
                response = requests.get(url)
                soup = BeautifulSoup(response.text, 'xml')
                items = soup.find_all('item')
                if not items:
                    return "Новости не найдены."
                result = f"📰 Последние новости:\n\n"
                for i, item in enumerate(items[:5], 1):
                    title = item.find('title').text
                    description = item.find('description').text
                    title = TextProcessor.clean_search_results(title)
                    description = TextProcessor.clean_search_results(description)
                    result += f"{title}\n"
                    first_sentence = description.split('.')[0]
                    if len(first_sentence) > 10:
                        result += f"{first_sentence}.\n\n"
                    else:
                        result += "\n"
                return result
            except Exception as e2:
                log_event(f"Ошибка запасного получения новостей: {str(e2)}")
                return self.search_web(f"последние новости {topic if topic else ''}")
class SmartSearchApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Умный поиск с нейросетью")
        self.resize(800, 600)
        self.search_thread = None
        self.neural_thread = None
        self.speech_thread = None
        self.thinking_timer = None
        self.thinking_dots = 0
        self.chat_history = []
        self.dialog_context = DialogContext()  
        self.nlp = NaturalLanguageProcessor()  
        self.setup_dark_theme()
        self.setup_ui()
        log_event("Приложение запущено")
    def setup_dark_theme(self):
        app = QApplication.instance()
        dark_palette = QPalette()
        dark_palette.setColor(QPalette.ColorRole.Window, QColor(33, 33, 33))
        dark_palette.setColor(QPalette.ColorRole.WindowText, QColor(255, 255, 255))
        dark_palette.setColor(QPalette.ColorRole.Base, QColor(25, 25, 25))
        dark_palette.setColor(QPalette.ColorRole.AlternateBase, QColor(45, 45, 45))
        dark_palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(25, 25, 25))
        dark_palette.setColor(QPalette.ColorRole.ToolTipText, QColor(255, 255, 255))
        dark_palette.setColor(QPalette.ColorRole.Text, QColor(255, 255, 255))
        dark_palette.setColor(QPalette.ColorRole.Button, QColor(45, 45, 45))
        dark_palette.setColor(QPalette.ColorRole.ButtonText, QColor(255, 255, 255))
        dark_palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
        dark_palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
        dark_palette.setColor(QPalette.ColorRole.HighlightedText, QColor(0, 0, 0))
        app.setPalette(dark_palette)
        app.setStyleSheet("""
            QToolTip { 
                color: #ffffff; 
                background-color: #2a82da; 
                border: 1px solid white; 
            }
            QWidget {
                background-color: #212121;
                color: #ffffff;
            }
            QTextEdit, QLineEdit { 
                background-color: #1a1a1a; 
                color: #ffffff; 
                border: 1px solid #3a3a3a;
                border-radius: 5px;
                padding: 5px;
            }
            QPushButton { 
                background-color: #2a82da; 
                color: white; 
                border: none;
                border-radius: 5px;
                padding: 8px 16px;
            }
            QPushButton:hover { 
                background-color: #3a92ea; 
            }
            QPushButton:pressed { 
                background-color: #1a72ca; 
            }
            QComboBox {
                background-color: #1a1a1a;
                color: #ffffff;
                border: 1px solid #3a3a3a;
                border-radius: 5px;
                padding: 5px;
            }
            QComboBox QAbstractItemView {
                background-color: #1a1a1a;
                color: #ffffff;
                selection-background-color: #2a82da;
            }
            QProgressBar {
                border: 1px solid #3a3a3a;
                border-radius: 5px;
                background-color: #1a1a1a;
                text-align: center;
                color: white;
            }
            QProgressBar::chunk {
                background-color: #2a82da;
                width: 10px;
                margin: 0.5px;
            }
        """)
    def setup_ui(self):
        main_layout = QVBoxLayout()
        title_label = QLabel("🧠 Умный поиск с нейросетью")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title_label)
        self.chat_area = QTextEdit()
        self.chat_area.setReadOnly(True)
        self.chat_area.setStyleSheet("""
            QTextEdit {
                background-color: #2d2d2d;
                color: #e0e0e0;
                border: 1px solid #444444;
                border-radius: 5px;
                padding: 10px;
            }
        """)
        main_layout.addWidget(self.chat_area)
        bottom_panel = QHBoxLayout()
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Введите запрос...")
        self.input_field.returnPressed.connect(self.send_query)
        self.input_field.setStyleSheet("""
            QLineEdit {
                background-color: #3d3d3d;
                color: #ffffff;
                border: 1px solid #555555;
                border-radius: 5px;
                padding: 8px;
                font-size: 14px;
            }
        """)
        bottom_panel.addWidget(self.input_field)
        self.voice_button = QToolButton()
        self.voice_button.setText("🎤")
        self.voice_button.setToolTip("Голосовой ввод")
        self.voice_button.setStyleSheet("""
            QToolButton {
                background-color: #3d3d3d;
                color: #ffffff;
                border: 1px solid #555555;
                border-radius: 5px;
                padding: 8px;
                font-size: 16px;
            }
            QToolButton:hover {
                background-color: #4a4a4a;
            }
            QToolButton:pressed {
                background-color: #2a82da;
            }
        """)
        self.voice_button.clicked.connect(self.start_voice_input)
        bottom_panel.addWidget(self.voice_button)
        self.send_button = QPushButton("Найти")
        self.send_button.clicked.connect(self.send_query)
        self.send_button.setStyleSheet("""
            QPushButton {
                background-color: #2a82da;
                color: #ffffff;
                border: none;
                border-radius: 5px;
                padding: 8px 15px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #3a92ea;
            }
            QPushButton:pressed {
                background-color: #1a72ca;
            }
        """)
        bottom_panel.addWidget(self.send_button)
        main_layout.addLayout(bottom_panel)
        options_panel = QHBoxLayout()
        self.assistant_mode = QCheckBox("Режим помощника")
        self.assistant_mode.setToolTip("Обрабатывать сложные запросы с несколькими темами")
        self.assistant_mode.setChecked(True)
        self.assistant_mode.setStyleSheet("""
            QCheckBox {
                color: #e0e0e0;
            }
            QCheckBox::indicator:checked {
                background-color: #2a82da;
                border: 1px solid #2a82da;
            }
        """)
        options_panel.addWidget(self.assistant_mode)
        self.dialog_mode = QCheckBox("Диалоговый режим")
        self.dialog_mode.setToolTip("Запоминать контекст разговора")
        self.dialog_mode.setChecked(True)
        self.dialog_mode.setStyleSheet("""
            QCheckBox {
                color: #e0e0e0;
            }
            QCheckBox::indicator:checked {
                background-color: #2a82da;
                border: 1px solid #2a82da;
            }
        """)
        options_panel.addWidget(self.dialog_mode)
        options_panel.addStretch()
        main_layout.addLayout(options_panel)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)
        self.status_label = QLabel("Готов к поиску")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        main_layout.addWidget(self.status_label)
        self.setLayout(main_layout)
        welcome_msg = """
        <h3 style="color: #2a82da;">👋 Добро пожаловать в Умный поиск с нейросетью!</h3>
        <p>Я могу помочь найти информацию в интернете, ответить на вопросы и поддержать разговор.</p>
        <p>Примеры запросов:</p>
        <ul>
            <li>Погода в Москве</li>
            <li>Курс доллара</li>
            <li>Последние новости</li>
            <li>Что такое нейронная сеть</li>
            <li>Хочу уехать в отпуск в Турцию, какая там погода и курс валют?</li>
        </ul>
        <p>Просто введите ваш запрос или нажмите кнопку микрофона для голосового ввода.</p>
        """
        self.append_message("Умный поиск", welcome_msg)
    def send_query(self):
        query = self.input_field.text().strip()
        if not query:
            return
        self.append_message("Вы", query)
        self.input_field.clear()
        self.start_thinking_animation()
        self.status_label.setText("Обработка запроса...")
        self.send_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.neural_thread = NeuralThread(query, self.dialog_mode.isChecked(), self.dialog_context)
        self.neural_thread.result_ready.connect(self.handle_neural_result)
        self.neural_thread.error_occurred.connect(self.handle_search_error)
        self.neural_thread.start()
    def start_voice_input(self):
        if self.speech_thread and self.speech_thread.is_listening:
            return
        self.voice_button.setEnabled(False)
        self.voice_button.setText("🔊")
        self.status_label.setText("Слушаю...")
        self.speech_thread = SpeechRecognitionThread()
        self.speech_thread.text_recognized.connect(self.handle_recognized_text)
        self.speech_thread.error_occurred.connect(self.handle_speech_error)
        self.speech_thread.status_update.connect(self.update_speech_status)
        self.speech_thread.start()
    def handle_recognized_text(self, text):
        self.voice_button.setEnabled(True)
        self.voice_button.setText("🎤")
        self.input_field.setText(text)
        self.status_label.setText("Текст распознан")
        self.send_query()
    def handle_speech_error(self, error_msg):
        self.voice_button.setEnabled(True)
        self.voice_button.setText("🎤")
        self.status_label.setText(error_msg)
        log_event(f"Ошибка распознавания речи: {error_msg}")
    def update_speech_status(self, status):
        self.status_label.setText(status)
        if status == "Готов к поиску":
            self.voice_button.setEnabled(True)
            self.voice_button.setText("🎤")
    def handle_neural_result(self, query_type, processed_query, category, original_query):
        log_event(f"Запрос: {original_query} -> {query_type}/{category} -> {processed_query}")
        if self.search_thread and self.search_thread.isRunning():
            self.search_thread.terminate()
            self.search_thread.wait()
        if query_type == "conversation":
            self.append_message("Умный поиск (Нейросеть)", processed_query)
            if self.dialog_mode.isChecked():
                self.dialog_context.add_interaction(original_query, processed_query, "conversation")
            self.search_finished()
        elif query_type == "complex" and self.assistant_mode.isChecked():
            self.status_label.setText("Обработка сложного запроса...")
            complex_thread = threading.Thread(
                target=self.process_complex_scenario,
                args=(processed_query, original_query)
            )
            complex_thread.daemon = True
            complex_thread.start()
        else:
            self.search_thread = SearchThread(processed_query, category, original_query)
            self.search_thread.result_ready.connect(self.handle_search_result)
            self.search_thread.error_occurred.connect(self.handle_search_error)
            self.search_thread.start()
    def process_complex_scenario(self, subtopics, original_query):
        try:
            result = NeuralAssistant.process_complex_scenario(subtopics)
            QApplication.instance().postEvent(
                self,
                QTimer(self, singleShot=True, timeout=lambda: self.handle_complex_result(result, original_query))
            )
        except Exception as e:
            log_event(f"Ошибка при обработке сложного сценария: {str(e)}")
            QApplication.instance().postEvent(
                self,
                QTimer(self, singleShot=True, timeout=lambda: self.handle_search_error(f"Ошибка при обработке сложного запроса: {str(e)}"))
            )
    def handle_complex_result(self, result, original_query):
        self.append_message("Умный поиск (Помощник)", result)
        if self.dialog_mode.isChecked():
            self.dialog_context.add_interaction(original_query, result, "complex")
        self.search_finished()
    def start_thinking_animation(self):
        if not self.thinking_timer:
            self.thinking_timer = QTimer(self)
            self.thinking_timer.timeout.connect(self.update_thinking_animation)
        self.thinking_dots = 0
        self.status_label.setText("Думаю")
        self.thinking_timer.start(300)  
    def update_thinking_animation(self):
        self.thinking_dots = (self.thinking_dots + 1) % 4
        dots = "." * self.thinking_dots
        self.status_label.setText(f"Думаю{dots}")
    def stop_thinking_animation(self):
        if self.thinking_timer and self.thinking_timer.isActive():
            self.thinking_timer.stop()
    def handle_search_result(self, result, source):
        if not result.strip():
            result = "К сожалению, я не смог найти информацию по вашему запросу."
        self.append_message(f"Умный поиск ({source})", result)
        log_event(f"Результат от {source}: {result[:100]}...")
        if self.dialog_mode.isChecked() and self.search_thread:
            query_type = self.search_thread.search_type
            entities = {}
            if query_type == "weather":
                city = self.search_thread.extract_city_from_query(self.search_thread.query)
                if city:
                    entities["city"] = city
            elif query_type == "news":
                for word in self.search_thread.query.split():
                    if word.lower() not in ["новости", "новость", "последние", "свежие", "события"]:
                        entities["news_topic"] = word
                        break
            self.dialog_context.add_interaction(
                self.search_thread.original_query, 
                result, 
                query_type, 
                entities
            )
        self.search_finished()
    def handle_search_error(self, error_msg):
        self.append_message("Ошибка", error_msg)
        log_event(error_msg)
        self.search_finished()
    def search_finished(self):
        self.stop_thinking_animation()
        self.status_label.setText("Готов к поиску")
        self.send_button.setEnabled(True)
        self.progress_bar.setVisible(False)
    def append_message(self, sender, message):
        current_time = datetime.datetime.now().strftime("%H:%M")
        if sender == "Вы":
            self.chat_area.append(f"<div style='background-color: #3a3a3a; padding: 8px; border-radius: 10px; margin: 5px;'>"
                                f"<b style='color: #ffffff;'>{sender}</b> <small style='color: #aaaaaa;'>({current_time})</small>:<br>{message}</div>")
        else:
            self.chat_area.append(f"<div style='background-color: #2d2d2d; padding: 8px; border-radius: 10px; margin: 5px;'>"
                                f"<b style='color: #4CAF50;'>{sender}</b> <small style='color: #aaaaaa;'>({current_time})</small>:<br>{message}</div>")
        scrollbar = self.chat_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        self.chat_history.append({"sender": sender, "message": message, "time": current_time})
class NeuralThread(QThread):
    result_ready = pyqtSignal(str, str, str, str)  
    error_occurred = pyqtSignal(str)  
    def __init__(self, query, dialog_mode, dialog_context):
        super().__init__()
        self.query = query
        self.dialog_mode = dialog_mode
        self.dialog_context = dialog_context
    def run(self):
        try:
            query_type, processed_query, category = NeuralAssistant.process_query(self.query, self.dialog_context)
            self.result_ready.emit(query_type, processed_query, category, self.query)
        except Exception as e:
            self.error_occurred.emit(f"Ошибка обработки запроса: {str(e)}")
            log_event(f"Ошибка: {str(e)}")
class SpeechRecognitionThread(QThread):
    text_recognized = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    status_update = pyqtSignal(str)
    def __init__(self, language='ru-RU'):
        super().__init__()
        self.language = language
        self.recognizer = sr.Recognizer()
        self.is_listening = False
    def run(self):
        try:
            self.is_listening = True
            self.status_update.emit("Слушаю...")
            with sr.Microphone() as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                self.status_update.emit("Говорите...")
                audio = self.recognizer.listen(source, timeout=5)
                self.status_update.emit("Обрабатываю...")
                text = self.recognizer.recognize_google(audio, language=self.language)
                self.text_recognized.emit(text)
        except sr.WaitTimeoutError:
            self.error_occurred.emit("Время ожидания истекло. Не услышал речи.")
        except sr.UnknownValueError:
            self.error_occurred.emit("Не удалось распознать речь.")
        except sr.RequestError as e:
            self.error_occurred.emit(f"Ошибка сервиса распознавания: {e}")
        except Exception as e:
            self.error_occurred.emit(f"Ошибка: {str(e)}")
        finally:
            self.is_listening = False
            self.status_update.emit("Готов к поиску")
class NaturalLanguageProcessor:
    def __init__(self):
        self.initialized = False
        self.classifier = None
        self.sentence_model = None
        self.summarizer = None
        self.query_reformulator = None
        self.initialization_thread = threading.Thread(target=self._initialize_models)
        self.initialization_thread.daemon = True
        self.initialization_thread.start()
    def _initialize_models(self):
        try:
            log_event("Инициализация NLP моделей...")
            self.classifier = Pipeline([
                ('tfidf', TfidfVectorizer(max_features=5000)),
                ('clf', MultinomialNB())
            ])
            X_train = [
                "погода в москве", "какая погода сегодня", "погода на завтра", "дождь сегодня", 
                "температура в питере", "прогноз погоды", "будет ли снег",
                "курс доллара", "курс евро", "валютный курс", "обмен валюты", "стоимость доллара",
                "последние новости", "что нового", "новости политики", "новости спорта", 
                "кто такой пушкин", "что такое квантовая физика", "определение слова", "значение термина",
                "привет", "здравствуй", "как дела", "доброе утро", "добрый день",
                "спасибо", "благодарю", "пока", "до свидания"
            ]
            y_train = (
                ["weather"] * 7 + 
                ["currency"] * 5 + 
                ["news"] * 4 + 
                ["wiki"] * 4 + 
                ["greeting"] * 5 + 
                ["thanks_bye"] * 4
            )
            self.classifier.fit(X_train, y_train)
            try:
                self.sentence_model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
            except Exception as e:
                log_event(f"Ошибка загрузки sentence-transformer: {str(e)}")
                self.sentence_model = None
            try:
                self.summarizer = pipeline("summarization", model="facebook/bart-large-cnn")
            except Exception as e:
                log_event(f"Ошибка загрузки summarizer: {str(e)}")
                self.summarizer = None
            try:
                self.query_reformulator = pipeline("text2text-generation", model="facebook/bart-base")
            except Exception as e:
                log_event(f"Ошибка загрузки query_reformulator: {str(e)}")
                self.query_reformulator = None
            self.initialized = True
            log_event("NLP модели инициализированы")
        except Exception as e:
            log_event(f"Ошибка инициализации NLP моделей: {str(e)}")
    def classify_query(self, query):
        if not self.initialized or self.classifier is None:
            log_event("NLP модели не инициализированы, используем базовую классификацию")
            return self._basic_classify(query)
        try:
            predicted_class = self.classifier.predict([query])[0]
            return predicted_class
        except Exception as e:
            log_event(f"Ошибка классификации запроса: {str(e)}")
            return self._basic_classify(query)
    def _basic_classify(self, query):
        query = query.lower()
        if any(word in query for word in ["погода", "температура", "дождь", "снег"]):
            return "weather"
        elif any(word in query for word in ["курс", "доллар", "евро", "валют"]):
            return "currency"
        elif any(word in query for word in ["новости", "новость", "события"]):
            return "news"
        elif any(phrase in query for phrase in ["что такое", "кто такой", "определение", "значение"]):
            return "wiki"
        elif any(word in query for word in ["привет", "здравствуй", "хай", "добрый"]):
            return "greeting"
        elif any(word in query for word in ["спасибо", "благодарю", "пока", "свидания"]):
            return "thanks_bye"
        else:
            return "web"
    def reformulate_query(self, query):
        if not self.initialized or self.query_reformulator is None:
            return query
        try:
            prompt = f"Переформулируй запрос для поиска в интернете: '{query}'"
            result = self.query_reformulator(prompt, max_length=100, num_return_sequences=1)
            reformulated = result[0]['generated_text'].strip()
            if len(reformulated) < 5 or len(reformulated) > len(query) * 3:
                return query
            return reformulated
        except Exception as e:
            log_event(f"Ошибка переформулировки запроса: {str(e)}")
            return query
    def summarize_text(self, text, max_length=150):
        if not self.initialized or self.summarizer is None or len(text) < 200:
            return TextProcessor.summarize_text(text)
        try:
            max_input_length = 1024
            if len(text) > max_input_length:
                text = text[:max_input_length]
            summary = self.summarizer(text, max_length=max_length, min_length=30, do_sample=False)
            return summary[0]['summary_text']
        except Exception as e:
            log_event(f"Ошибка суммирования текста: {str(e)}")
            return TextProcessor.summarize_text(text)
    def is_complex_scenario(self, query):
        topics = []
        if any(word in query.lower() for word in ["погода", "температура", "дождь", "снег"]):
            topics.append("weather")
        if any(word in query.lower() for word in ["курс", "доллар", "евро", "валют", "стоит"]):
            topics.append("currency")
        if any(word in query.lower() for word in ["новости", "новость", "события", "происходит"]):
            topics.append("news")
        return len(topics) > 1, topics
    def extract_subtopics(self, query):
        subtopics = {}
        if any(word in query.lower() for word in ["погода", "температура", "дождь", "снег"]):
            city = None
            for pattern in NeuralAssistant.QUERY_PATTERNS["weather"]:
                match = re.search(pattern, query.lower())
                if match and match.groups():
                    city = match.group(1)
                    break
            if not city:
                for city_name, variants in NeuralAssistant.CITIES.items():
                    for variant in variants:
                        if variant in query.lower():
                            city = city_name
                            break
                    if city:
                        break
            if not city:
                countries = ["турция", "турции", "египет", "египте", "италия", "италии", "франция", "франции", 
                           "испания", "испании", "греция", "греции", "таиланд", "таиланде"]
                for country in countries:
                    if country in query.lower():
                        city = country
                        break
            if city:
                subtopics["weather"] = f"погода в {city}"
            else:
                subtopics["weather"] = "погода"
        if any(word in query.lower() for word in ["курс", "доллар", "евро", "валют", "стоит"]):
            subtopics["currency"] = "курс валют"
        if any(word in query.lower() for word in ["новости", "новость", "события", "происходит"]):
            news_topics = ["рейсы", "полеты", "авиа", "туризм", "отпуск", "путешествия", "отдых"]
            for topic in news_topics:
                if topic in query.lower():
                    subtopics["news"] = f"новости {topic}"
                    break
            if "news" not in subtopics:
                subtopics["news"] = "последние новости"
        return subtopics
class DialogContext:
    def __init__(self, max_history=5):
        self.max_history = max_history
        self.history = []
        self.current_topic = None
        self.last_query_type = None
        self.entities = {}  
    def add_interaction(self, user_query, system_response, query_type=None, entities=None):
        interaction = {
            "user_query": user_query,
            "system_response": system_response,
            "timestamp": datetime.datetime.now(),
            "query_type": query_type
        }
        self.history.append(interaction)
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]
        self.last_query_type = query_type
        if query_type in ["weather", "currency", "news", "wiki"]:
            self.current_topic = query_type
        if entities:
            self.entities.update(entities)
    def get_last_n_interactions(self, n=2):
        return self.history[-n:] if len(self.history) >= n else self.history
    def get_context_for_query(self, query):
        context = {
            "current_topic": self.current_topic,
            "last_query_type": self.last_query_type,
            "entities": self.entities,
            "recent_history": self.get_last_n_interactions(2)
        }
        return context
    def resolve_references(self, query):
        query_lower = query.lower()
        has_reference = any(word in query_lower for word in [
            "там", "туда", "этот", "эта", "это", "эти", "он", "она", "оно", "они", 
            "его", "ее", "их", "этом", "этой", "тот", "та", "те"
        ])
        if not has_reference or not self.history:
            return query
        if len(query_lower.split()) <= 2:
            if self.current_topic == "weather" and "city" in self.entities:
                if "погода" not in query_lower:
                    return f"погода в {self.entities['city']}"
            elif self.current_topic == "news" and "news_topic" in self.entities:
                if "новости" not in query_lower:
                    return f"новости {self.entities['news_topic']}"
        last_interaction = self.history[-1] if self.history else None
        if last_interaction:
            last_query = last_interaction["user_query"].lower()
            for pattern in NeuralAssistant.QUERY_PATTERNS["weather"]:
                match = re.search(pattern, last_query)
                if match and match.groups():
                    city = match.group(1)
                    if "погода" in query_lower and not any(city_name in query_lower for city_name in NeuralAssistant.CITIES.keys()):
                        return f"погода в {city}"
        return query
    def should_continue_topic(self, query):
        if not self.current_topic or not self.history:
            return False
        query_lower = query.lower()
        has_reference = any(word in query_lower for word in [
            "там", "туда", "этот", "эта", "это", "эти", "он", "она", "оно", "они", 
            "его", "ее", "их", "этом", "этой", "тот", "та", "те", "еще", "больше", 
            "подробнее", "детальнее"
        ])
        if len(query_lower.split()) <= 2:
            return True
        return has_reference
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SmartSearchApp()
    window.show()
    sys.exit(app.exec())