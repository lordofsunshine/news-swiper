from quart import Quart, render_template, jsonify, request, session, redirect, url_for
from newsapi import NewsApiClient
import os
from dotenv import load_dotenv
import logging
from datetime import datetime, timedelta
import json
import random
from colorama import init, Fore, Style
import asyncio
import aiohttp
from functools import partial

init()

class ColoredFormatter(logging.Formatter):
    
    COLORS = {
        'WARNING': Fore.YELLOW,
        'ERROR': Fore.RED,
        'CRITICAL': Fore.RED + Style.BRIGHT,
        'INFO': Fore.GREEN
    }

    def format(self, record):
        if record.levelname in self.COLORS:
            record.levelname = f"{self.COLORS[record.levelname]}{record.levelname}{Style.RESET_ALL}"
            record.msg = f"{self.COLORS.get(record.levelname, '')}{record.msg}{Style.RESET_ALL}"
        return super().format(record)

logger = logging.getLogger('news_app')
logger.setLevel(logging.INFO)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

formatter = ColoredFormatter('%(asctime)s - %(levelname)s - %(message)s', 
                           datefmt='%Y-%m-%d %H:%M:%S')
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

load_dotenv()

app = Quart(__name__)
app.secret_key = os.urandom(24)
newsapi = NewsApiClient(api_key=os.getenv('NEWS_API_KEY'))

news_cache = {
    'articles': {},
    'last_update': {},
    'page': {},
    'all_urls': {'en': set(), 'ru': set()}
}

DEFAULT_ICONS = [
    '''<svg viewBox="0 0 24 24" class="default-news-icon" fill="currentColor"><path d="M19 5v14H5V5h14m0-2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-5 14H7v-2h7v2zm3-4H7v-2h10v2zm0-4H7V7h10v2z"/></svg>''',
    '''<svg viewBox="0 0 24 24" class="default-news-icon" fill="currentColor"><path d="M20 2H4c-1.1 0-1.99.9-1.99 2L2 22l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm-7 9h-2V5h2v6zm0 4h-2v-2h2v2z"/></svg>''',
    '''<svg viewBox="0 0 24 24" class="default-news-icon" fill="currentColor"><path d="M21 5c-1.11-.35-2.33-.5-3.5-.5-1.95 0-4.05.4-5.5 1.5-1.45-1.1-3.55-1.5-5.5-1.5S2.45 4.9 1 6v14.65c0 .25.25.5.5.5.1 0 .15-.05.25-.05C3.1 20.45 5.05 20 6.5 20c1.95 0 4.05.4 5.5 1.5 1.35-.85 3.8-1.5 5.5-1.5 1.65 0 3.35.3 4.75 1.05.1.05.15.05.25.05.25 0 .5-.25.5-.5V6c-.6-.45-1.25-.75-2-1zm0 13.5c-1.1-.35-2.3-.5-3.5-.5-1.7 0-4.15.65-5.5 1.5V8c1.35-.85 3.8-1.5 5.5-1.5 1.2 0 2.4.15 3.5.5v11.5z"/></svg>''',
    '''<svg viewBox="0 0 24 24" class="default-news-icon" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z"/></svg>''',
    '''<svg viewBox="0 0 24 24" class="default-news-icon" fill="currentColor"><path d="M22 3H2C.9 3 0 3.9 0 5v14c0 1.1.9 2 2 2h20c1.1 0 1.99-.9 1.99-2L24 5c0-1.1-.9-2-2-2zM8 6c1.66 0 3 1.34 3 3s-1.34 3-3 3-3-1.34-3-3 1.34-3 3-3zm6 12H2v-1c0-2 4-3.1 6-3.1s6 1.1 6 3.1v1zm3.85-4h1.64L21 16l-1.99 1.99c-1.31-.98-2.28-2.38-2.73-3.99-.18-.64-.28-1.31-.28-2s.1-1.36.28-2c.45-1.62 1.42-3.01 2.73-3.99L21 8l-1.51 2h-1.64c-.22.63-.35 1.3-.35 2s.13 1.37.35 2z"/></svg>'''
]

TRANSLATIONS = {
    'ru': {
        'read_more': 'Читать далее',
        'no_news': 'Нет доступных новостей',
        'check_connection': 'Пожалуйста, проверьте подключение к интернету или попробуйте позже.',
        'switch_language': 'Switch to English',
        'reload_prompt': 'Для применения изменений перезагрузите страницу',
        'source': 'Источник'
    },
    'en': {
        'read_more': 'Read more',
        'no_news': 'No news available',
        'check_connection': 'Please check your internet connection or try again later.',
        'switch_language': 'Переключить на русский',
        'reload_prompt': 'Reload the page to apply changes',
        'source': 'Source'
    }
}

def process_article(article, lang):
    if not article:
        return None
        
    source = article.get('source', {})
    if isinstance(source, str):
        source_name = source
    elif isinstance(source, dict):
        source_name = source.get('name', TRANSLATIONS[lang]['source'])
    else:
        source_name = TRANSLATIONS[lang]['source']
    
    if not all([article.get('title'), article.get('description'), article.get('url')]):
        return None
        
    image_url = article.get('urlToImage')
    default_icon = None
    if not image_url or 'None' in str(image_url):
        default_icon = random.choice(DEFAULT_ICONS)
        image_url = None
    
    return {
        'title': article['title'],
        'description': article['description'],
        'url': article['url'],
        'urlToImage': image_url,
        'default_icon': default_icon,
        'source': source_name
    }

async def fetch_news(page=1, lang='ru'):
    global news_cache
    
    now = datetime.now()
    try:
        if (news_cache['articles'].get(lang) and 
            news_cache['last_update'].get(lang) and 
            (now - news_cache['last_update'][lang]).seconds <= 300 and 
            page == news_cache['page'].get(lang, 1)):
            logger.info(f"Возвращаем новости из кэша для языка {lang}")
            return news_cache['articles'].get(lang, [])
        
        from_date = (now - timedelta(days=1)).strftime('%Y-%m-%d')
        query = '(Russia OR USA OR World OR Europe)' if lang == 'en' else '(Россия OR Russia OR Мир)'
        
        news = newsapi.get_everything(
            q=query,
            language=lang,
            from_param=from_date,
            sort_by='publishedAt',
            page=page,
            page_size=15 
        )
        
        if not news:
            logger.error("API вернул пустой ответ")
            return news_cache['articles'].get(lang, [])
        
        if news.get('status') != 'ok':
            logger.error(f"API вернул ошибку: {news.get('message', 'Неизвестная ошибка')}")
            return news_cache['articles'].get(lang, [])
        
        articles = news.get('articles', [])
        if not articles:
            logger.warning(f"API вернул пустой список статей для языка {lang}")
            return news_cache['articles'].get(lang, [])
        
        processed_articles = []
        for article in articles:
            if article['url'] not in news_cache['all_urls'][lang]:
                processed = process_article(article, lang)
                if processed:
                    news_cache['all_urls'][lang].add(article['url'])
                    processed_articles.append(processed)
        
        if processed_articles:
            if not news_cache['articles'].get(lang):
                news_cache['articles'][lang] = []
                news_cache['page'][lang] = 1
                news_cache['last_update'][lang] = now
            
            news_cache['articles'][lang] = processed_articles
            news_cache['last_update'][lang] = now
            news_cache['page'][lang] = page
            
            logger.info(f"Загружено {len(processed_articles)} новых статей на языке {lang}")
        else:
            logger.warning(f"Не удалось получить новые статьи для языка {lang}")
            if news_cache['articles'].get(lang):
                logger.info("Используем кэшированные статьи")
                return news_cache['articles'][lang]
        
    except Exception as e:
        logger.error(f"Ошибка при загрузке новостей: {str(e)}")
        if news_cache['articles'].get(lang):
            logger.info("Используем кэшированные статьи после ошибки")
            return news_cache['articles'][lang]
        return []
    
    return news_cache['articles'].get(lang, [])

async def refresh_news_api():
    while True:
        try:
            logger.info("Начало планового обновления новостей")
            
            news_cache['articles'] = {}
            news_cache['last_update'] = {}
            news_cache['page'] = {}
            news_cache['all_urls'] = {'en': set(), 'ru': set()}
            
            await fetch_news(lang='ru')
            await fetch_news(lang='en')
            
            logger.info("Плановое обновление новостей завершено")
            
            await asyncio.sleep(1800)  # 30 минут = 1800 секунд
            
        except Exception as e:
            logger.error(f"Ошибка при плановом обновлении новостей: {str(e)}")
            await asyncio.sleep(60)  # При ошибке ждем минуту перед повторной попыткой

@app.before_serving
async def startup():
    app.background_tasks = set()
    task = asyncio.create_task(refresh_news_api())
    app.background_tasks.add(task)
    task.add_done_callback(app.background_tasks.discard)
    logger.info("Запущена задача периодического обновления новостей")

@app.after_serving
async def cleanup():
    for task in app.background_tasks:
        task.cancel()
    await asyncio.gather(*app.background_tasks, return_exceptions=True)
    logger.info("Фоновые задачи остановлены")

@app.route('/')
async def index():
    try:
        lang = session.get('language', 'ru')
        viewed_articles = session.get('viewed_articles', [])
        
        if len(viewed_articles) > 100:
            viewed_articles = viewed_articles[-50:] 
            session['viewed_articles'] = viewed_articles
        
        articles = await fetch_news(lang=lang)
        fresh_articles = [
            article for article in articles 
            if article['url'] not in viewed_articles
        ]
        
        if not fresh_articles and articles:
            current_page = news_cache['page'].get(lang, 1)
            articles = await fetch_news(page=current_page + 1, lang=lang)
            fresh_articles = [
                article for article in articles 
                if article['url'] not in viewed_articles
            ]
        
        return await render_template('index.html', 
                                   articles=fresh_articles,
                                   translations=TRANSLATIONS[lang],
                                   current_lang=lang)
    
    except Exception as e:
        logger.error(f"Ошибка при отображении главной страницы: {str(e)}")
        return await render_template('index.html', 
                                   articles=[],
                                   translations=TRANSLATIONS[lang],
                                   current_lang=lang)

@app.route('/api/switch-language', methods=['POST'])
async def switch_language():
    try:
        data = await request.get_json()
        new_lang = data.get('language', 'ru')
        if new_lang in ['ru', 'en']:
            session['language'] = new_lang
            logger.info(f"Язык изменен на: {new_lang}")
            return jsonify({'success': True})
        return jsonify({'success': False, 'error': 'Invalid language'}), 400
    except Exception as e:
        logger.error(f"Ошибка при переключении языка: {str(e)}")
        return jsonify({'success': False}), 500

@app.route('/api/mark-viewed', methods=['POST'])
async def mark_viewed():
    try:
        data = await request.get_json()
        url = data.get('url')
        
        if url:
            viewed_articles = session.get('viewed_articles', [])
            if url not in viewed_articles:
                viewed_articles.append(url)
                session['viewed_articles'] = viewed_articles
                logger.info(f"Статья отмечена как просмотренная: {url}")
        
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Ошибка при отметке статьи как просмотренной: {str(e)}")
        return jsonify({'success': False}), 500

@app.route('/api/load-more', methods=['POST'])
async def load_more():
    try:
        data = await request.get_json()
        page = data.get('page', 1)
        lang = session.get('language', 'ru')
        viewed_articles = session.get('viewed_articles', [])
        articles = await fetch_news(page, lang)
        
        fresh_articles = [
            article for article in articles 
            if article['url'] not in viewed_articles
        ]
        
        logger.info(f"Загружено {len(fresh_articles)} дополнительных статей на языке {lang}")
        return jsonify({
            'articles': fresh_articles,
            'hasMore': len(fresh_articles) > 0
        })
    
    except Exception as e:
        logger.error(f"Ошибка при загрузке дополнительных статей: {str(e)}")
        return jsonify({'articles': [], 'hasMore': False}), 500

if __name__ == '__main__':
    logger.info("Запуск новостного приложения")
    app.run(debug=False) 