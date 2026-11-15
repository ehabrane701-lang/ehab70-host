#!/usr/bin/env python3
"""
𝗘𝗛𝗔Б - نظام التحكم الشامل، مشغّل البوتات، ومحرك الذكاء الاصطناعي وتصحيح الملفات
طُوِّر بواسطة: ꪝ🇾🇪إأبـტּٱإڵيمـטּ🇾🇪ꪝ | @Y_20_20
"""

import os
import re
import sys
import uuid
import ast
import json
import time
import logging
import threading
import sqlite3
import subprocess
import requests
from bs4 import BeautifulSoup
from flask import Flask, session, redirect, send_from_directory, render_template_string, request, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)

# ========== إعداد تطبيق Flask (لوحة التحكم والويب) ==========
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "ehab_super_secure_secret_key_2026")

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

@app.route('/dashboard')
def dashboard():
    """مسار لوحة التحكم مع التحقق من الجلسة وإرسال واجهة الملفات/المحرر"""
    if 'email' not in session:
        return redirect('/login')
    
    index_path = os.path.join(BASE_DIR, 'index.html')
    if os.path.exists(index_path):
        return send_from_directory(BASE_DIR, 'index.html')
    
    return render_template_string("""
        <!DOCTYPE html>
        <html lang="ar" dir="rtl">
        <head><meta charset="UTF-8"><title>DARK CODE - Dashboard</title></head>
        <body style="background:#090909;color:#fff;font-family:sans-serif;text-align:center;padding-top:50px;">
            <h2>⚠️ واجهة المحرر (index.html) غير موجودة في المجلد الحالي</h2>
            <p>يرجى التأكد من رفع ملف واجهة المحرر بجانب ملف السيرفر.</p>
        </body>
        </html>
    """)

@app.route('/login')
def login_page():
    return "صفحة تسجيل الدخول - يرجى تسجيل الدخول عبر البوت أو الموقع."

RUNNING_DIR = os.path.join(BASE_DIR, "active_bots")
LOGS_DIR = os.path.join(BASE_DIR, "bot_logs")
DB_DIR = os.path.join(BASE_DIR, "database")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
STORE_DIR = os.path.join(BASE_DIR, "store_files")
THUMBS_DIR = os.path.join(ASSETS_DIR, "thumbs")
MARKET_DIR = os.path.join(BASE_DIR, "market")
ENV_DIR = os.path.join(BASE_DIR, "bot_environments")
ENCRYPTED_DIR = os.path.join(BASE_DIR, "encrypted_files")
DOWNLOAD_DIR = os.path.join(BASE_DIR, "downloads")
UPLOAD_DIR = os.path.abspath("upload_bots")
SUSPICIOUS_DIR = os.path.join(BASE_DIR, "suspicious_files")
BACKUPS_DIR = os.path.join(BASE_DIR, "backups")

MAX_LOG_SIZE_KB = 512
_ipinfo = {'t': 0, 'data': None}
bot_scripts = {}

for d in [RUNNING_DIR, LOGS_DIR, DB_DIR, ASSETS_DIR, STORE_DIR, THUMBS_DIR, MARKET_DIR, ENV_DIR, ENCRYPTED_DIR, DOWNLOAD_DIR, UPLOAD_DIR, SUSPICIOUS_DIR, BACKUPS_DIR]:
    if not os.path.exists(d):
        os.makedirs(d, exist_ok=True)

USERS_DB = os.path.join(DB_DIR, "users.json")
FILES_DB = os.path.join(DB_DIR, "files.json")
SETTINGS_DB = os.path.join(DB_DIR, "settings.json")
STORE_DB = os.path.join(DB_DIR, "store.json")
ADMINS_DB = os.path.join(DB_DIR, "admins.json")
MARKET_DB = os.path.join(DB_DIR, "market.json")
SECURITY_DB = os.path.join(DB_DIR, "security.json")
PURCHASES_DB_PATH = os.path.join(DB_DIR, "purchases.db")

# ==========================================================
#  نظام التخزين الموحد والآمن (Persistence & Storage Engine)
# ==========================================================
db_lock = threading.Lock()

def init_storage_files():
    """تهيئة ملفات التخزين JSON و SQLite وضمان سلامتها"""
    with db_lock:
        default_files = {
            USERS_DB: {"users": {}},
            FILES_DB: {"files": {}},
            SETTINGS_DB: {"settings": {"maintenance_mode": False}},
            STORE_DB: {"items": []},
            ADMINS_DB: {"admins": [1002670694]},
            MARKET_DB: {"bots": []},
            SECURITY_DB: {"blocked_ips": [], "banned_users": []}
        }
        for path, default_data in default_files.items():
            if not os.path.exists(path) or os.path.getsize(path) == 0:
                try:
                    with open(path, "w", encoding="utf-8") as f:
                        json.dump(default_data, f, ensure_ascii=False, indent=4)
                except Exception as e:
                    logging.error(f"Error initializing storage file {path}: {e}")

        try:
            conn = sqlite3.connect(PURCHASES_DB_PATH)
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS purchases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    item_name TEXT,
                    price REAL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
            conn.close()
        except Exception as e:
            logging.error(f"Error initializing SQLite purchases DB: {e}")

init_storage_files()

def load_json_db(file_path):
    """قراءة آمنة لملفات قواعد البيانات مع قفل حماية التزامن"""
    with db_lock:
        if not os.path.exists(file_path):
            return {}
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    return {}
                return json.loads(content)
        except Exception as e:
            logging.error(f"Error loading JSON DB {file_path}: {e}")
            return {}

def save_json_db(file_path, data):
    """حفظ آمن ومستقر لملفات قواعد البيانات JSON"""
    with db_lock:
        try:
            temp_path = file_path + ".tmp"
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            os.replace(temp_path, file_path)
            return True
        except Exception as e:
            logging.error(f"Error saving JSON DB {file_path}: {e}")
            return False

cancel_states = {}
last_bot_messages = {}
active_processes = {}
admin_steps = {}
PENDING = {}
USER_STEPS = {}

# ========== إعدادات وتكامل محرك الذكاء الاصطناعي Ptero.pro المحدث ==========
HOME_URL = "https://ptero.pro"
CHAT_URL = f"{HOME_URL}/wp-json/mlp/v1/chat-stream"

AI_MODELS = {
    "1": {"id": "ling-3.0-flash",               "name": "Ling 3.0 Flash"},
    "2": {"id": "deepseek-v4.1-flash:free",     "name": "DeepSeek v4.1 Flash"},
    "3": {"id": "minimax-m3.1-flash:runware",   "name": "MiniMax M3.1 Flash"},
    "4": {"id": "glm-5.3-flash",                "name": "GLM 5.3 Flash"},
    "5": {"id": "qwen3.7-flash:minirouter",     "name": "Qwen 3.7 Flash"},
}

DEFAULT_MODEL_ID = "ling-3.0-flash"
FALLBACK_MODELS = [
    "deepseek-v4.1-flash:free",
    "minimax-m3.1-flash:runware",
    "glm-5.3-flash",
    "qwen3.7-flash:minirouter",
    "ling-3.0-flash:free",
]

MAX_SOURCE_BYTES = 20 * 1024 * 1024
MAX_OUTPUT_BYTES = 20 * 1024 * 1024

_USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
)

class RepairServiceError(RuntimeError):
    """Raised when the selected external AI service cannot process a file."""

def fetch_real_session(retries=2):
    for attempt in range(retries):
        session = requests.Session()
        headers = {
            "User-Agent": _USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ar-EG,ar;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
        try:
            response = session.get(HOME_URL, headers=headers, timeout=25)
            if response.status_code != 200:
                if attempt < retries - 1:
                    time.sleep(1)
                    continue
                return None

            html = response.text
            nonce = None
            patterns = [
                r"var\s+nonce\s*=\s*[\"\']([a-f0-9]{8,64})[\"\']",
                r"[\"\']nonce[\"\']\s*:\s*[\"\']([a-f0-9]{8,64})[\"\']",
                r"data-referral-nonce=[\"\']([a-f0-9]{8,64})[\"\']",
                r"x-wp-nonce[\"\']?\s*[:=]\s*[\"\']([a-f0-9]{8,64})[\"\']",
                r"wp_nonce[\"\']?\s*[:=]\s*[\"\']([a-f0-9]{8,64})[\"\']",
                r"mlp_nonce[\"\']?\s*[:=]\s*[\"\']([a-f0-9]{8,64})[\"\']",
                r"data-nonce=[\"\']([a-f0-9]{8,64})[\"\']",
            ]

            for pattern in patterns:
                match = re.search(pattern, html, re.IGNORECASE)
                if match:
                    nonce = match.group(1)
                    break

            if not nonce and BeautifulSoup:
                soup = BeautifulSoup(html, "html.parser")
                for script in soup.find_all("script"):
                    text = script.get_text() or ""
                    if "nonce" in text:
                        match = re.search(r"[\"\']([a-f0-9]{10})[\"\']", text)
                        if match:
                            nonce = match.group(1)
                            break

            if not nonce:
                for script in re.findall(r"<script\b[^>]*>(.*?)</script\s*>", html, re.I | re.S):
                    if "nonce" in script.lower():
                        match = re.search(r"""["']([a-f0-9]{10})["']""", script, re.I)
                        if match:
                            nonce = match.group(1)
                            break

            if not nonce:
                if attempt < retries - 1:
                    time.sleep(1)
                    continue
                return None

            guest_token = None
            for cookie in session.cookies:
                if any(k in cookie.name.lower() for k in ["mlp", "guest", "token"]):
                    guest_token = cookie.value
                    break

            if not guest_token:
                match = re.search(r"guest[_-]?token[\"\']?\s*[:=]\s*[\"\']([a-f0-9]+)[\"\']", html, re.IGNORECASE)
                guest_token = match.group(1) if match else uuid.uuid4().hex

            return {
                "session": session,
                "nonce": nonce,
                "guest_token": guest_token,
                "conversation_id": str(uuid.uuid4()),
            }
        except Exception as ex:
            logging.warning(f"fetch_real_session error (attempt {attempt + 1}): {ex}")
            if attempt < retries - 1:
                time.sleep(1)

    return None

def chat_with_model(model_id, user_message, session_data, model_display_name="AI", stream_print=False):
    payload = {
        "message": user_message,
        "model": model_id,
        "conversation_id": session_data["conversation_id"],
        "attachments": [],
        "history": [],
        "lang": "ar",
        "github_repo": "",
        "mode": "quick"
    }

    headers = {
        "User-Agent": _USER_AGENT,
        "Accept-Encoding": "gzip, deflate",
        "Content-Type": "application/json",
        "sec-ch-ua-platform": "\"Android\"",
        "sec-ch-ua": "\"Chromium\";v=\"120\", \"Google Chrome\";v=\"120\"",
        "sec-ch-ua-mobile": "?1",
        "x-wp-nonce": session_data["nonce"],
        "x-mlp-guest-token": session_data["guest_token"],
        "x-mlp-guest-username": f"user_{session_data['conversation_id'][:6]}",
        "origin": HOME_URL,
        "sec-fetch-site": "same-origin",
        "sec-fetch-mode": "cors",
        "sec-fetch-dest": "empty",
        "referer": f"{HOME_URL}/",
        "accept-language": "ar-EG,ar;q=0.9,en-US;q=0.8,en;q=0.7",
        "priority": "u=1, i",
    }

    try:
        response = session_data["session"].post(
            CHAT_URL, json=payload, headers=headers, stream=True, timeout=(30, 240)
        )

        if response.status_code != 200:
            return None, None

        full_reply = ""
        for line in response.iter_lines():
            if not line:
                continue
            line = line.decode("utf-8", errors="replace")
            if not line.startswith("data:"):
                continue
            data_str = line[5:].strip()
            if not data_str or data_str == "keepalive":
                continue
            try:
                data = json.loads(data_str)
            except json.JSONDecodeError:
                continue

            if "token" in data and isinstance(data["token"], str):
                full_reply += data["token"]
                if stream_print:
                    print(data["token"], end="", flush=True)
            elif data.get("done"):
                if data.get("conversation_id"):
                    session_data["conversation_id"] = data["conversation_id"]
                return full_reply, data

        return full_reply, None

    except requests.exceptions.RequestException as ex:
        logging.warning(f"chat_with_model request error ({model_id}): {ex}")
        return None, None

def extract_code_from_ai_response(raw_text):
    if not raw_text:
        return ""
    text = raw_text.strip()
    blocks = re.findall(r"```(?:[a-zA-Z0-9_\-\.\+]*\n)?(.*?)(?:```|$)", text, flags=re.DOTALL)
    if blocks:
        clean_blocks = [b.strip() for b in blocks if b.strip()]
        if clean_blocks:
            best_block = max(clean_blocks, key=len)
            if len(best_block) >= 15:
                return best_block
    if text.startswith("```"):
        text = re.sub(r"^```[^\n]*\n", "", text)
        text = re.sub(r"\n```$", "", text)
        return text.strip()
    return text

def repair_source(source, instructions, file_name, model_id=None):
    source_bytes_len = len(source.encode("utf-8"))
    if source_bytes_len > MAX_SOURCE_BYTES:
        raise RepairServiceError(
            f"الملف أكبر من الحد المسموح لإرساله للخدمة ({int(MAX_SOURCE_BYTES / (1024 * 1024))} ميجابايت)."
        )

    session_data = fetch_real_session()
    if not session_data:
        raise RepairServiceError("تعذّر الاتصال بخدمة الذكاء الاصطناعي (فشل تهيئة الجلسة مع الخادم).")

    extra_rules = ""
    _stem, ext = os.path.splitext(file_name)
    ext_lower = ext.lower()

    if ext_lower == ".js":
        extra_rules = (
            "\nتوجيهات لملفات JavaScript / Node.js:\n"
            "- إذا كان الكود يستخدم مكتبة node-telegram-bot-api بالصيغة الشائعة: const TelegramBot = require('node-telegram-bot-api'); new TelegramBot(...); فلا تقم بتغييرها ولا تضع دوال فحص تنهي البرنامج بـ process.exit.\n"
            "- حافظ على بناء الجمل البرمجية الصحيحة في Node.js وتأكد من إغلاق الأقواس.\n"
        )
    elif ext_lower == ".php":
        extra_rules = (
            "\nتوجيهات لملفات PHP:\n"
            "- حافظ على علامة البداية <?php واحرص على كتابة كود PHP سليم برمجياً وإغلاق الأقواس والفواصل المنقوطة.\n"
        )
    elif ext_lower == ".py":
        extra_rules = (
            "\nتوجيهات لملفات Python:\n"
            "- تأكد من صحة الصياغة النحوية (Syntax) والمسافات البادئة (Indentation) بدقة.\n"
            "- لا تغير أسماء الدوال أو المتغيرات الأساسية غير المرتبطة بالطلب.\n"
        )

    prompt = (
        "أنت مبرمج محترف متخصص في تصحيح وإصلاح وتعديل ملفات الأكواد البرمجية. "
        "مهمتك: إصلاح الأخطاء وتنفيذ طلب المستخدم بأعلى دقة وبأقل تغييرات ممكنة.\n"
        "شروط صارمة:\n"
        "1. أعد محتوى الملف كاملاً وجاهزاً للتشغيل داخل كتلة كود واحدة فقط: ``` ... ```\n"
        "2. لا تكتب أي شرح أو مقدمات أو كلام بشري قبل أو بعد الكود نهائياً.\n"
        "3. حافظ على التوكنات والمتغيرات الأساسية ومنطق البوت الأصلي.\n"
        "4. لا تضف أي أكواد ضارة أو برمجيات خبيثة.\n\n"
        f"اسم الملف: {file_name}\n"
        f"طلب المستخدم: {instructions}\n"
        f"{extra_rules}\n"
        "محتوى الملف الحالي:\n"
        f"```text\n{source}\n```"
    )

    candidate_models = []
    if model_id:
        candidate_models.append(model_id)
    if DEFAULT_MODEL_ID not in candidate_models:
        candidate_models.append(DEFAULT_MODEL_ID)
    for fm in FALLBACK_MODELS:
        if fm not in candidate_models:
            candidate_models.append(fm)

    for candidate in candidate_models:
        try:
            reply, meta = chat_with_model(candidate, prompt, session_data)
            if not reply or not reply.strip():
                session_data = fetch_real_session() or session_data
                continue

            extracted = extract_code_from_ai_response(reply)
            if not extracted or len(extracted.strip()) < 10:
                continue

            if ext_lower == ".py":
                try:
                    ast.parse(extracted, filename=file_name)
                except SyntaxError as syn_err:
                    logging.warning(f"النموذج {candidate} أنتج كود Python به خطأ صياغة ({syn_err})؛ تجربة نموذج بديل...")
                    continue
            elif ext_lower == ".php":
                try:
                    chk = subprocess.run(["php", "-l"], input=extracted.encode("utf-8"), capture_output=True, timeout=5)
                    if chk.returncode != 0:
                        logging.warning(f"النموذج {candidate} أنتج كود PHP به خطأ صياغة؛ تجربة نموذج بديل...")
                        continue
                except Exception:
                    pass

            return extracted

        except Exception as ex:
            logging.warning(f"فشل النموذج {candidate}: {ex}")
            continue

    raise RepairServiceError("تعذّر الحصول على نسخة صالحة وخالية من الأخطاء من خدمة الذكاء الاصطناعي بعد تجربة كافة النماذج.")

# ========== إعدادات السجل (Logging) ==========
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("ehab_system")

# ========== إعدادات النظام الأساسية ==========
BOT_TOKEN = os.environ.get("BOT_TOKEN", "9090360556:AAFU2etPnCt5DpJsEtcnEVps3B_izACOwSk")
API_BASE_URL = os.environ.get("API_BASE_URL", "[https://ehab70-host.onrender.com](https://ehab70-host.onrender.com)")

ADMIN_TELEGRAM_IDS = [1002670694]

DEVELOPER_INFO = "🛠 طُوِّر بواسطة: *ꪝ🇾🇪إأبـტּٱإڵيمـטּ🇾🇪ꪝ*\n📬 تواصل: @Y_20_20"

# ========== حالات المحادثة للتحكم والذكاء الاصطناعي ==========
(
    WAITING_FOR_API_KEY,
    WAITING_FOR_NEW_SERVER_NAME,
    WAITING_FOR_SERVER_TYPE,
    WAITING_FOR_DELETE_USERNAME,
    WAITING_FOR_AI_PROMPT,
) = range(5)


# ─────────────────────────────────────────────────
#  وظائف الأمان والحماية والتنقية (Sanitization)
# ─────────────────────────────────────────────────
def sanitize_input(text: str, max_length: int = 500) -> str:
    """تنقية النصوص ومدخلات المستخدمين لمنع هجمات الحقن أو XSS"""
    if not isinstance(text, str):
        return ""
    clean_text = re.sub(r'[^\w\s\-_@\.:/\?\!\،\?\ء-ي]', '', text)
    return clean_text[:max_length].strip()


def api_request(endpoint, method="GET", data=None, params=None, api_key=None):
    """إرسال طلبات آمنة لخادم التحكم مع معالجة كاملة للأخطاء"""
    url = f"{API_BASE_URL}{endpoint}"
    headers = {"User-Agent": "EhabBot-SecureClient/2.0"}
    try:
        if method == "GET":
            p = dict(params or {})
            if api_key:
                p["api_key"] = sanitize_input(api_key, 256)
            resp = requests.get(url, params=p, headers=headers, timeout=20)
        else:
            d = dict(data or {})
            if api_key and "api_key" not in d:
                d["api_key"] = sanitize_input(api_key, 256)
            resp = requests.post(url, json=d, headers=headers, timeout=20)
            
        if resp.ok:
            return resp.json()
        return {"success": False, "message": f"HTTP Error: {resp.status_code}"}
    except requests.exceptions.Timeout:
        logger.error(f"API Timeout on {endpoint}")
        return {"success": False, "message": "انتهت مهلة الاتصال بالخادم الرئيسي."}
    except requests.exceptions.RequestException as e:
        logger.error(f"API Request Exception: {e}")
        return {"success": False, "message": "فشل الاتصال بخادم النظام الأساسي."}
    except Exception as e:
        logger.error(f"Unexpected error in api_request: {e}")
        return {"success": False, "message": "حدث خطأ غير متوقع."}


def is_admin_tg(update: Update) -> bool:
    """التحقق الآمن والصارم من صلاحيات الأدمن"""
    try:
        user_id = update.effective_user.id if update.effective_user else 0
        return user_id in ADMIN_TELEGRAM_IDS
    except Exception:
        return False


# ─────────────────────────────────────────────────
#  القائمة الرئيسية وواجهة التليجرام
# ─────────────────────────────────────────────────
async def runner_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [
        [InlineKeyboardButton("🤖 التحدث مع الذكاء الاصطناعي", callback_data="ai_menu")],
        [InlineKeyboardButton("⚙️ لوحة تحكم السيرفرات", callback_data="main_menu")],
    ]
    await update.message.reply_text(
        "👋 مرحباً بك في نظام 𝗘𝗛𝗔Б المتطور والشامل!\n\n"
        "يمكنك إدارة سيرفراتك أو الاستعانة بأقوى نماذج الذكاء الاصطناعي.\n\n"
        f"{DEVELOPER_INFO}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def runner_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "📚 مركز المساعدة والإرشادات:\n\n"
        "• `/start` - القائمة الرئيسية ولوحة التحكم\n"
        "• `/ai` - اختيار نموذج ذكاء اصطناعي والتحدث معه\n"
        "• إدارة وتشغيل سيرفرات PHP و Python وتليجرام بنجاح.\n\n"
        f"{DEVELOPER_INFO}"
    )

async def runner_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "ℹ️ معلومات النظام:\n\n"
        "🤖 الخدمة: 𝗘𝗛𝗔Б Host & AI Engine\n"
        "✅ الحالة: نشط، مستمر وآمن 100%\n"
        f"{DEVELOPER_INFO}"
    )


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, edit=False):
    api_key = context.user_data.get("api_key")
    username = context.user_data.get("username", "")
    is_adm = is_admin_tg(update)

    keyboard = []

    if api_key or is_adm:
        keyboard.append([
            InlineKeyboardButton("📁 سيرفراتي", callback_data="my_servers"),
            InlineKeyboardButton("➕ إنشاء سيرفر", callback_data="create_server"),
        ])
        keyboard.append([
            InlineKeyboardButton("🔑 تغيير API Key", callback_data="change_api"),
            InlineKeyboardButton("🚪 تسجيل خروج", callback_data="logout"),
        ])
    else:
        keyboard.append([InlineKeyboardButton("🔑 ربط اشتراك API Key", callback_data="enter_api")])

    keyboard.append([InlineKeyboardButton("🤖 نماذج الذكاء الاصطناعي", callback_data="ai_menu")])

    if is_adm:
        pending_count = 0
        result = api_request("/api/admin/pending", api_key=api_key)
        if result and result.get("success"):
            pending_count = len(result.get("requests", []))
        bell = f"🔔 إشعارات ({pending_count})" if pending_count > 0 else "🔕 إشعارات"
        keyboard.append([
            InlineKeyboardButton("👑 لوحة الإدارة", callback_data="admin_panel"),
            InlineKeyboardButton(bell, callback_data="admin_notifications"),
        ])

    keyboard.append([InlineKeyboardButton("💬 تواصل للاشتراك مع المطور @Y_20_20", url="[https://t.me/Y_20_20](https://t.me/Y_20_20)")])

    text = (
        "━━━━━━━━━━━━━━━━━━━━\n"
        "      𝗘𝗛𝗔𝗕 🚀\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
    )
    if is_adm:
        text += "👑 أهلاً بك يا أدمن (صلاحية مجانية مطلقة)\n"
    elif username:
        text += f"👤 أهلاً، *{sanitize_input(username, 30)}*!\n"
        
    text += "✅ متصل بالنظام\n" if (api_key or is_adm) else "⚠️ يجب ربط اشتراكك أو مفتاح API أولاً\n"
    text += f"\n{DEVELOPER_INFO}"

    markup = InlineKeyboardMarkup(keyboard)
    try:
        query = update.callback_query
        if edit and query:
            if query.message.text != text:
                await query.edit_message_text(text, parse_mode="Markdown", reply_markup=markup)
            else:
                await query.answer()
        elif update.message:
            await update.message.reply_text(text, parse_mode="Markdown", reply_markup=markup)
        elif query:
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=markup)
    except Exception as e:
        logger.error(f"Error in show_main_menu: {e}")


async def show_servers_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    api_key = context.user_data.get("api_key")
    is_adm = is_admin_tg(update)

    if not api_key and not is_adm:
        await query.edit_message_text("❌ يجب ربط اشتراكك أو API Key أولاً.")
        return

    result = api_request("/api/bot/servers", api_key=api_key)
    if not result or not result.get("success"):
        if is_adm and not api_key:
            servers = []
        else:
            await query.edit_message_text(
                "━━━━━━━━━━━━━━━━━━━━\n"
                "❌ فشل جلب السيرفرات\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "تحقق من صحة الاشتراك أو API Key.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")]]),
            )
            return
    else:
        servers = result.get("servers", [])

    if not servers:
        await query.edit_message_text(
            "━━━━━━━━━━━━━━━━━━━━\n"
            "📭 لا توجد سيرفرات\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "أنشئ سيرفرك الأول الآن!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ إنشاء سيرفر", callback_data="create_server")],
                [InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")],
            ]),
        )
        return

    await query.edit_message_text(f"📋 لديك *{len(servers)}* سيرفر:", parse_mode="Markdown")

    for srv in servers:
        status_emoji = "🟢" if srv.get("status") == "Running" else "⚫"
        srv_type = srv.get("type", "Python")
        type_icon = "🐍" if srv_type == "Python" else "🟨"
        srv_title = sanitize_input(srv.get('title', 'Server'), 30)
        folder = sanitize_input(srv.get('folder', ''), 50)

        text = (
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{status_emoji} *{srv_title}*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{type_icon} النوع: `{srv_type}`\n"
            f"📊 الحالة: `{sanitize_input(srv.get('status', 'Unknown'), 20)}`\n"
            f"🔌 المنفذ: `{sanitize_input(str(srv.get('port', 'N/A')), 10)}`\n"
            f"⏱ وقت التشغيل: {sanitize_input(str(srv.get('uptime', 'N/A')), 30)}"
        )
        keyboard = [
            [
                InlineKeyboardButton("▶️ تشغيل", callback_data=f"srv_start|{folder}"),
                InlineKeyboardButton("⏹ إيقاف", callback_data=f"srv_stop|{folder}"),
                InlineKeyboardButton("🔄 إعادة", callback_data=f"srv_restart|{folder}"),
            ],
            [
                InlineKeyboardButton("🖥 كونسول", callback_data=f"console|{folder}"),
                InlineKeyboardButton("⚠️ أخطاء", callback_data=f"errors|{folder}"),
                InlineKeyboardButton("🗑 حذف", callback_data=f"srv_delete|{folder}"),
            ],
            [InlineKeyboardButton("📦 تثبيت مكتبات تلقائياً", callback_data=f"install|{folder}")],
        ]
        await query.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    await query.message.reply_text(
        "━━━━━━━━━━━━━━━━━━━━",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]]),
    )


async def show_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not is_admin_tg(update):
        await query.edit_message_text("❌ غير مصرح لك بالدخول (للأدمن فقط).")
        return

    api_key = context.user_data.get("api_key")
    result = api_request("/api/admin/users", api_key=api_key)
    users = result.get("users", []) if result and result.get("success") else []

    pending_result = api_request("/api/admin/pending", api_key=api_key)
    pending_count = len(pending_result.get("requests", [])) if pending_result and pending_result.get("success") else 0

    text = (
        "━━━━━━━━━━━━━━━━━━━━\n"
        "  👑 لوحة إدارة 𝗘𝗛𝗔Б\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 المستخدمين: *{len(users)}*\n"
        f"🔔 طلبات اشتراك معلقة: *{pending_count}*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
    )
    for u in users[:10]:
        uname = sanitize_input(u.get('username', 'User'), 25)
        text += f"• `{uname}` | {u.get('max_servers', 1)} سيرفر\n"
    if len(users) > 10:
        text += f"... و {len(users) - 10} آخرين\n"

    bell = f"🔔 طلبات ({pending_count})" if pending_count > 0 else "🔕 لا طلبات"
    keyboard = [
        [
            InlineKeyboardButton(bell, callback_data="admin_notifications"),
            InlineKeyboardButton("📊 إحصائيات", callback_data="admin_stats"),
        ],
        [InlineKeyboardButton("🗑 حذف مستخدم", callback_data="admin_delete_user")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")],
    ]
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))


async def show_admin_notifications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not is_admin_tg(update):
        await query.edit_message_text("❌ غير مصرح.")
        return

    api_key = context.user_data.get("api_key")
    result = api_request("/api/admin/pending", api_key=api_key)

    if not result or not result.get("success"):
        await query.edit_message_text("❌ فشل جلب طلبات الاشتراكات.")
        return

    requests_list = result.get("requests", [])

    if not requests_list:
        await query.edit_message_text(
            "━━━━━━━━━━━━━━━━━━━━\n"
            "🔕 لا توجد طلبات اشتراك معلقة\n"
            "━━━━━━━━━━━━━━━━━━━━",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")]]),
        )
        return

    await query.edit_message_text(
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🔔 طلبات اشتراكات جديدة ({len(requests_list)})\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )
    for req in requests_list:
        uname = sanitize_input(req.get('username', 'N/A'), 30)
        text = (
            f"👤 المستخدم: `{uname}`\n"
            f"📅 التاريخ: {str(req.get('created_at', ''))[:19]}"
        )
        keyboard = [[
            InlineKeyboardButton("✅ قبول", callback_data=f"approve|{uname}"),
            InlineKeyboardButton("❌ رفض", callback_data=f"reject|{uname}"),
        ]]
        await query.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    await query.message.reply_text(
        "━━━━━━━━━━━━━━━━━━━━",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")]]),
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    is_adm = is_admin_tg(update)
    
    if is_adm:
        context.user_data["is_admin"] = True

    api_key = context.user_data.get("api_key")
    if api_key:
        result = api_request("/api/bot/verify", method="POST", data={"api_key": api_key})
        if result and result.get("success"):
            context.user_data["username"] = result.get("username")
            await show_main_menu(update, context)
            return ConversationHandler.END
        context.user_data.clear()

    if is_adm:
        await show_main_menu(update, context)
        return ConversationHandler.END

    keyboard = [
        [InlineKeyboardButton("🔑 إدخال API Key (تفعيل الاشتراك)", callback_data="enter_api")],
        [InlineKeyboardButton("🤖 نماذج الذكاء الاصطناعي", callback_data="ai_menu")],
        [InlineKeyboardButton("💬 تواصل للاشتراك مع المطور @Y_20_20", url="[https://t.me/Y_20_20](https://t.me/Y_20_20)")],
    ]
    await update.message.reply_text(
        "━━━━━━━━━━━━━━━━━━━━\n"
        "      𝗘𝗛𝗔Б 🚀\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "📌 نظام استضافة بوتات تيليجرام ومحرك الذكاء الاصطناعي والتصحيح\n\n"
        "للاشتراك والحصول على حساب:\n"
        "📬 تواصل مع المطور: @Y_20_20\n\n"
        f"{DEVELOPER_INFO}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return WAITING_FOR_API_KEY


async def handle_api_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    api_key = sanitize_input(update.message.text.strip(), 256)
    if not api_key:
        await update.message.reply_text("❌ مفتاح API غير صالح. أعد الإرسال:")
        return WAITING_FOR_API_KEY

    result = api_request("/api/bot/verify", method="POST", data={"api_key": api_key})
    if not result or not result.get("success"):
        keyboard = [[InlineKeyboardButton("💬 تواصل مع المطور للاشتراك", url="[https://t.me/Y_20_20](https://t.me/Y_20_20)")]]
        await update.message.reply_text(
            "❌ *مفتاح الاشتراك أو API غير صالح!*\n\n"
            "تأكد من الكود وحاول مرة أخرى\n"
            "أو تواصل مع المطور للحصول على اشتراك: @Y_20_20",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return WAITING_FOR_API_KEY

    context.user_data["api_key"] = api_key
    context.user_data["username"] = sanitize_input(result.get("username", ""), 30)
    context.user_data["is_admin"] = result.get("is_admin", False)

    await update.message.reply_text(
        f"✅ *تم تفعيل الاشتراك والربط بنجاح!*\n"
        f"👤 مرحباً *{context.user_data['username']}*!",
        parse_mode="Markdown",
    )
    await show_main_menu(update, context)
    return ConversationHandler.END


async def start_create_server(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "➕ *إنشاء سيرفر جديد*\n\n📝 أرسل اسم السيرفر الآن:",
        parse_mode="Markdown",
    )
    return WAITING_FOR_NEW_SERVER_NAME


async def receive_server_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = sanitize_input(update.message.text.strip(), 30)
    if not name:
        await update.message.reply_text("❌ اسم السيرفر لا يمكن أن يكون فارغاً. أرسل اسم السيرفر من جديد:")
        return WAITING_FOR_NEW_SERVER_NAME
        
    context.user_data["pending_server_name"] = name
    keyboard = [[
        InlineKeyboardButton("🐍 Python", callback_data="server_type_python"),
        InlineKeyboardButton("🟨 Node.js", callback_data="server_type_nodejs"),
    ]]
    await update.message.reply_text(
        f"📦 *اختر نوع السيرفر:*\n\nالاسم: `{name}`",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return WAITING_FOR_SERVER_TYPE


async def receive_server_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    srv_type = "Python" if query.data == "server_type_python" else "Node.js"
    name = context.user_data.get("pending_server_name", "Server")
    api_key = context.user_data.get("api_key", "")

    result = api_request("/api/bot/create_server", method="POST", data={
        "api_key": api_key,
        "name": name,
        "server_type": srv_type,
        "plan": "free",
        "storage": 100,
        "ram": 256,
        "cpu": 0.5,
    })

    type_icon = "🐍" if srv_type == "Python" else "🟨"
    if result and result.get("success"):
        await query.edit_message_text(
            f"✅ *تم إنشاء السيرفر بنجاح!*\n\n"
            f"📛 الاسم: `{name}`\n"
            f"{type_icon} النوع: `{srv_type}`\n\n"
            f"ارفع ملفاتك عبر الموقع الآن.",
            parse_mode="Markdown",
        )
    else:
        err_msg = sanitize_input(result.get("message", "خطأ غير معروف") if result else "خطأ غير معروف", 100)
        await query.edit_message_text(
            f"❌ *فشل الإنشاء!*\n{err_msg}",
            parse_mode="Markdown",
        )

    await show_main_menu(update, context)
    return ConversationHandler.END


async def show_console(update: Update, context: ContextTypes.DEFAULT_TYPE, folder: str):
    query = update.callback_query
    safe_folder = sanitize_input(folder, 50)
    result = api_request("/api/bot/console", params={"folder": safe_folder}, api_key=context.user_data.get("api_key"))
    if result and result.get("success"):
        logs = result.get("logs", "لا توجد مخرجات")
        if len(logs) > 3500:
            logs = "...\n" + logs[-3500:]
        keyboard = [[
            InlineKeyboardButton("🔄 تحديث", callback_data=f"console|{safe_folder}"),
            InlineKeyboardButton("🔙 رجوع", callback_data="my_servers"),
        ]]
        await query.edit_message_text(
            f"🖥 *كونسول السيرفر*\n```\n{logs}\n```",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
    else:
        await query.edit_message_text("❌ فشل جلب الكونسول")


async def show_errors(update: Update, context: ContextTypes.DEFAULT_TYPE, folder: str):
    query = update.callback_query
    safe_folder = sanitize_input(folder, 50)
    result = api_request("/api/bot/errors", params={"folder": safe_folder}, api_key=context.user_data.get("api_key"))
    if result and result.get("success"):
        errors = result.get("errors", "✅ لا توجد أخطاء")
        if len(errors) > 3500:
            errors = "...\n" + errors[-3500:]
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="my_servers")]]
        await query.edit_message_text(
            f"⚠️ *سجل الأخطاء*\n```\n{errors}\n```",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
    else:
        await query.edit_message_text("❌ فشل جلب سجل الأخطاء")


async def admin_delete_user_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin_tg(update):
        await query.edit_message_text("❌ غير مصرح.")
        return ConversationHandler.END
    await query.edit_message_text("📝 أرسل اسم المستخدم الذي تريد حذفه:")
    return WAITING_FOR_DELETE_USERNAME


async def admin_delete_user_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = sanitize_input(update.message.text.strip(), 30)
    result = api_request("/api/admin/delete-user", method="POST", data={
        "api_key": context.user_data.get("api_key"),
        "username": username,
    })
    if result and result.get("success"):
        await update.message.reply_text(f"✅ تم حذف المستخدم `{username}`", parse_mode="Markdown")
    else:
        err_msg = sanitize_input(result.get("message", "خطأ") if result else "خطأ", 100)
        await update.message.reply_text(f"❌ فشل: {err_msg}")
    await show_main_menu(update, context)
    return ConversationHandler.END


async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin_tg(update):
        await query.edit_message_text("❌ غير مصرح.")
        return
    api_key = context.user_data.get("api_key")
    metrics = api_request("/api/system/metrics", api_key=api_key)
    cpu = metrics.get("cpu", "?") if metrics else "?"
    ram = metrics.get("memory", "?") if metrics else "?"
    disk = metrics.get("disk", "?") if metrics else "?"
    await query.edit_message_text(
        "━━━━━━━━━━━━━━━━━━━━\n"
        "  📊 إحصائيات النظام\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🖥 CPU:  *{cpu}%*\n"
        f"💾 RAM:  *{ram}%*\n"
        f"💿 Disk: *{disk}%*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")]]),
    )


# ─────────────────────────────────────────────────
#  معالجات الذكاء الاصطناعي التفاعلية
# ─────────────────────────────────────────────────
async def ai_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    keyboard = []
    for key, info in AI_MODELS.items():
        keyboard.append([InlineKeyboardButton(f"🤖 {info['name']}", callback_data=f"ai_sel|{key}")])
    keyboard.append([InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")])

    text = (
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🤖 *اختر نموذج الذكاء الاصطناعي:*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "اختر النموذج الذي ترغب في التحدث معه:"
    )
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))


async def ai_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = []
    for key, info in AI_MODELS.items():
        keyboard.append([InlineKeyboardButton(f"🤖 {info['name']}", callback_data=f"ai_sel|{key}")])
    keyboard.append([InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")])

    await update.message.reply_text(
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🤖 *اختر نموذج الذكاء الاصطناعي للتحدث معه:*\n"
        "━━━━━━━━━━━━━━━━━━━━",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    if data == "main_menu":
        await show_main_menu(update, context, edit=True)
    elif data == "my_servers":
        await show_servers_list(update, context)
    elif data == "ai_menu":
        await ai_menu_handler(update, context)
    elif data in ("enter_api", "change_api"):
        context.user_data.pop("api_key", None)
        await query.edit_message_text(
            "🔑 *أدخل مفتاح الاشتراك أو API Key الخاص بك:*\n\n"
            "يمكنك الحصول عليه من لوحة التحكم بالموقع أو التواصل مع المطور @Y_20_20.",
            parse_mode="Markdown",
        )
        return WAITING_FOR_API_KEY
    elif data == "logout":
        context.user_data.clear()
        await query.edit_message_text("🚪 تم تسجيل الخروج بنجاح.\nاستخدم /start للدخول مجدداً.")
    elif data == "create_server":
        return await start_create_server(update, context)
    elif data == "admin_panel":
        await show_admin_panel(update, context)
    elif data == "admin_notifications":
        await show_admin_notifications(update, context)
    elif data == "admin_delete_user":
        return await admin_delete_user_start(update, context)
    elif data == "admin_stats":
        await admin_stats(update, context)

    elif data.startswith("ai_sel|"):
        _, model_key = data.split("|", 1)
        if model_key in AI_MODELS:
            selected_model = AI_MODELS[model_key]
            context.user_data["active_ai_model"] = selected_model
            
            ai_sess = fetch_real_session()
            if not ai_sess:
                await query.answer("❌ تعذّر الاتصال بخادم الذكاء الاصطناعي.", show_alert=True)
                return
            context.user_data["ai_session"] = ai_sess

            keyboard = [[InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]]
            await query.edit_message_text(
                f"✅ تم اختيار النموذج: *{selected_model['name']}*\n\n"
                "💬 *أرسل رسالتك أو سؤالك الآن وسيقوم النموذج بالرد عليك:*",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return WAITING_FOR_AI_PROMPT

    elif "|" in data:
        try:
            cmd, value = data.split("|", 1)
            api_key = context.user_data.get("api_key")
            safe_value = sanitize_input(value, 50)

            if cmd in ("srv_start", "srv_stop", "srv_restart", "srv_delete"):
                action = cmd.replace("srv_", "")
                result = api_request("/api/bot/server/action", method="POST", data={
                    "api_key": api_key, "folder": safe_value, "action": action,
                })
                if result and result.get("success"):
                    await query.answer(result.get("message", "✅ تم")[:200], show_alert=True)
                else:
                    err_text = result.get('message', 'فشل') if result else 'خطأ'
                    await query.answer(f"❌ {err_text}"[:200], show_alert=True)
                await show_servers_list(update, context)

            elif cmd == "console":
                await show_console(update, context, safe_value)

            elif cmd == "errors":
                await show_errors(update, context, safe_value)

            elif cmd == "install":
                result = api_request("/api/bot/install", method="POST", data={
                    "api_key": api_key, "folder": safe_value,
                })
                msg = result.get("message", "✅ جاري التثبيت") if result and result.get("success") else "❌ فشل بدء التثبيت"
                await query.edit_message_text(
                    f"📦 *تثبيت المكتبات*\n\n{msg}\n\nتابع الكونسول للتفاصيل.",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🖥 كونسول", callback_data=f"console|{safe_value}"),
                        InlineKeyboardButton("🔙 رجوع", callback_data="my_servers"),
                    ]]),
                )

            elif cmd == "approve":
                if not is_admin_tg(update):
                    await query.answer("❌ غير مسموح", show_alert=True)
                    return
                result = api_request("/api/admin/approve", method="POST", data={
                    "api_key": api_key, "username": safe_value,
                })
                msg = f"✅ تم قبول اشتراك {safe_value}" if result and result.get("success") else "❌ فشل القبول"
                await query.answer(msg, show_alert=True)
                await show_admin_notifications(update, context)

            elif cmd == "reject":
                if not is_admin_tg(update):
                    await query.answer("❌ غير مسموح", show_alert=True)
                    return
                result = api_request("/api/admin/reject", method="POST", data={
                    "api_key": api_key, "username": safe_value,
                })
                msg = f"🚫 تم رفض طلب {safe_value}" if result and result.get("success") else "❌ فشل الرفض"
                await query.answer(msg, show_alert=True)
                await show_admin_notifications(update, context)
        except Exception as e:
            logger.error(f"Error handling callback action: {e}")
            await query.answer("❌ حدث خطأ أثناء تنفيذ الطلب.", show_alert=True)

    return ConversationHandler.END


async def handle_ai_chat_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_msg = sanitize_input(update.message.text.strip(), 1000)
    if not user_msg:
        return WAITING_FOR_AI_PROMPT

    if user_msg.lower() in ['خروج', 'exit', 'quit', '/start']:
        context.user_data.pop("active_ai_model", None)
        context.user_data.pop("ai_session", None)
        await show_main_menu(update, context)
        return ConversationHandler.END

    model_info = context.user_data.get("active_ai_model")
    ai_session = context.user_data.get("ai_session")

    if not model_info or not ai_session:
        await update.message.reply_text("⚠️ يرجى اختيار نموذج ذكاء اصطناعي أولاً عبر `/ai`.")
        return ConversationHandler.END

    processing_msg = await update.message.reply_text("🤖 *جاري توليد الرد والتصحيح...*", parse_mode="Markdown")

    reply, _ = chat_with_model(model_info["id"], user_msg, ai_session)
    if not reply:
        ai_session = fetch_real_session()
        if ai_session:
            context.user_data["ai_session"] = ai_session
            reply, _ = chat_with_model(model_info["id"], user_msg, ai_session)

    if not reply:
        reply = "❌ تعذّر الاتصال بنموذج الذكاء الاصطناعي أو انتهت الجلسة. حاول مرة أخرى."

    try:
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=processing_msg.message_id,
            text=f"🤖 *{model_info['name']}:*\n\n{reply}",
            parse_mode="Markdown"
        )
    except Exception:
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=processing_msg.message_id,
            text=f"🤖 {model_info['name']}:\n\n{reply}"
        )

    return WAITING_FOR_AI_PROMPT


# ─────────────────────────────────────────────────
#  دالة التشغيل الموحدة الشاملة
# ─────────────────────────────────────────────────
def run_bot(token: str, bot_name: str) -> None:
    try:
        print("\n" + "═"*60)
        print(f" 🤖 𝗘𝗛𝗔Б - جاري تشغيل النظام: {bot_name}")
        print(" 🚀 يتم الآن الاتصال بخوادم تليجرام ومحركات الذكاء الاصطناعي...")
        print("═"*60 + "\n")
        
        application = Application.builder().token(token).build()

        conv = ConversationHandler(
            entry_points=[
                CommandHandler("start", start),
                CommandHandler("ai", ai_command),
                CommandHandler("help", runner_help),
                CommandHandler("info", runner_info),
                CallbackQueryHandler(button_callback),
            ],
            states={
                WAITING_FOR_API_KEY: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, handle_api_key)
                ],
                WAITING_FOR_NEW_SERVER_NAME: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, receive_server_name)
                ],
                WAITING_FOR_SERVER_TYPE: [
                    CallbackQueryHandler(receive_server_type, pattern="^server_type_")
                ],
                WAITING_FOR_DELETE_USERNAME: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, admin_delete_user_confirm)
                ],
                WAITING_FOR_AI_PROMPT: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, handle_ai_chat_message)
                ],
            },
            fallbacks=[
                CommandHandler("start", start),
                CommandHandler("ai", ai_command)
            ],
            per_user=True,
            per_chat=True,
        )

        application.add_handler(conv)
        application.add_handler(CallbackQueryHandler(button_callback))

        print(f" ✅ النظام {bot_name} جاهز ويعمل بكفاءة على 𝗘𝗛𝗔Б!")
        print(" 📡 الحالة: نشط وينتظر التحديثات والطلبات...\n")
        application.run_polling(drop_pending_updates=True)
    except Exception as e:
        logger.error(f"❌ خطأ في تشغيل النظام {bot_name}: {str(e)}")


if __name__ == "__main__":
    if len(sys.argv) >= 2:
        token = sys.argv[1]
        bot_name = sys.argv[2] if len(sys.argv) > 2 else "ehab_unified_bot"
        run_bot(token, bot_name)
    else:
        run_bot(BOT_TOKEN, "EHAB_Control_And_AI_Repair_System")

