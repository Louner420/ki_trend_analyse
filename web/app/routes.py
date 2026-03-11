from flask import Blueprint, render_template, request, redirect, url_for, session, current_app, jsonify
import sqlite3
import re
import time
import traceback
import os
import json
import urllib.request
import urllib.error
from flask import Flask, request, g
from flask_socketio import emit
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.exceptions import HTTPException

# Alle DBs im Projektordner (funktioniert auf Mac und Windows)
_APP_DIR = os.path.dirname(os.path.abspath(__file__))
_WEB_DIR = os.path.dirname(_APP_DIR)
_PROJECT_ROOT = os.path.dirname(_WEB_DIR)
BASE_DIR = os.getenv('DATA_PATH', os.path.join(_PROJECT_ROOT, 'database'))
LOGS_DB = os.path.join(BASE_DIR, "logs.db")
ERROR_DB = os.path.join(BASE_DIR, "error.db")
USERS_DB = os.path.join(BASE_DIR, "users.db")
AI_API_BASE_URL = os.getenv('AI_API_BASE_URL', 'http://127.0.0.1:5000').rstrip('/')
AI_API_TIMEOUT_SECONDS = int(os.getenv('AI_API_TIMEOUT_SECONDS', '60'))


def _ensure_users_table(conn):
    """Users-Tabelle anlegen, falls noch nicht vorhanden."""
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)
    conn.commit()


def _ensure_onboarding_table(conn):
    """Onboarding-Profil pro User (einmal ausgefüllt, für KI-Ideengenerierung abrufbar)."""
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_onboarding_profile (
            user_id INTEGER PRIMARY KEY,
            industry TEXT,
            target_audience_type TEXT,
            target_age_group TEXT,
            audience_problem TEXT,
            audience_description TEXT,
            product_description TEXT,
            unique_value TEXT,
            customer_problem TEXT,
            trust_factor TEXT,
            competitors TEXT,
            competitor_strengths TEXT,
            competitive_advantage TEXT,
            industry_content_patterns TEXT,
            posts_per_week INTEGER,
            team_size TEXT,
            content_production_type TEXT,
            brand_tone TEXT,
            no_go_topics TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()


def _get_user_id_from_session():
    """User-ID aus Session (user_email) aus users.db holen. Für Onboarding-Speicherung."""
    email = session.get("user_email")
    if not email:
        return None
    try:
        conn = sqlite3.connect(USERS_DB)
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE email = ?", (email,))
        row = cur.fetchone()
        conn.close()
        return row[0] if row else None
    except Exception:
        return None


def _ensure_request_logs_table(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS request_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip TEXT, method TEXT, path TEXT,
            status_code INTEGER, response_time REAL, error TEXT
        )
    """)


def write_log(ip, method, path, status_code, response_time, error=None):
    try:
        conn = sqlite3.connect(LOGS_DB)
        cur = conn.cursor()
        _ensure_request_logs_table(cur)
        cur.execute("""
            INSERT INTO request_logs (ip, method, path, status_code, response_time, error)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (ip, method, path, status_code, response_time, error))
        conn.commit()
        conn.close()
    except Exception:
        pass


def write_log_error(ip, method, path, status_code, response_time, error=None):
    try:
        conn = sqlite3.connect(ERROR_DB)
        cur = conn.cursor()
        _ensure_request_logs_table(cur)
        cur.execute("""
            INSERT INTO request_logs (ip, method, path, status_code, response_time, error)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (ip, method, path, status_code, response_time, error))
        conn.commit()
        conn.close()
    except Exception:
        pass
    
class DB_table_result():
    def __init__(self,db_path):
        self.conn=sqlite3.connect(db_path, check_same_thread=False)
        self.cursor=self.conn.cursor()

    def caption(self, rank):
        rank = int(rank)
        query = "SELECT caption FROM top10_general WHERE rank = ?"
        self.cursor.execute(query, (rank,))
        result = self.cursor.fetchone()
        return result

    def trend_score(self, rank):
        rank = int(rank)
        query = "SELECT trend_score FROM top10_general WHERE rank = ?"
        self.cursor.execute(query, (rank,))
        result = self.cursor.fetchone()
        rounded_result = float(result[0]) if result else None
        rounded_result = round(rounded_result, 2) if rounded_result else None
        return rounded_result

    def lifecycle_phase(self, rank):
        rank = int(rank)
        query = "SELECT lifecycle_phase FROM top10_general WHERE rank = ?"
        self.cursor.execute(query, (rank,))
        result = self.cursor.fetchone()
        return result[0] if result else None

    def avg_velocity(self, rank):
        rank = int(rank)
        query = "SELECT avg_velocity FROM top10_general WHERE rank = ?"
        self.cursor.execute(query, (rank,))
        result = self.cursor.fetchone()
        try:
            velocity_val = float(result[0]) if result and result[0] is not None else 0.0
        except (TypeError, ValueError):
            velocity_val = 0.0
        return round(velocity_val, 2)

    def cluster_size(self, rank):
        rank = int(rank)
        query = "SELECT cluster_size FROM top10_general WHERE rank = ?"
        self.cursor.execute(query, (rank,))
        result = self.cursor.fetchone()
        return result[0] if result else None

    def niche_relevance(self, rank):
        rank = int(rank)
        query = "SELECT niche_relevance FROM top10_general WHERE rank = ?"
        self.cursor.execute(query, (rank,))
        result = self.cursor.fetchone()
        return result[0] if result else None

    # keep backwards-compatible alias
    def relevance(self, rank):
        return self.niche_relevance(rank)

    def updated_at(self, rank):
        rank = int(rank)
        query = "SELECT updated_at FROM top10_general WHERE rank = ?"
        self.cursor.execute(query, (rank,))
        result = self.cursor.fetchone()
        return result[0] if result else None
class DB_table_raw():
    def __init__(self, db_path="raw_tiktok.db"):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self._video_columns = self._load_table_columns("videos")

    def _load_table_columns(self, table_name):
        try:
            self.cursor.execute(f"PRAGMA table_info({table_name})")
            return {row[1] for row in self.cursor.fetchall()}
        except Exception:
            return set()

    def _fetch_value(self, column, rowid):
        index = max(int(rowid) - 1, 0)
        if column not in self._video_columns:
            return None
        self.cursor.execute(
            f"SELECT {column} FROM videos ORDER BY CAST(COALESCE(views, '0') AS REAL) DESC LIMIT 1 OFFSET ?",
            (index,)
        )
        result = self.cursor.fetchone()
        return result[0] if result else None

    def caption(self, rowid):
        return self._fetch_value("caption", rowid)

    def hashtags(self, rowid):
        return self._fetch_value("hashtags", rowid)

    def views(self, rowid):
        return self._fetch_value("views", rowid)

    def likes(self, rowid):
        return self._fetch_value("likes", rowid)

    def comments(self, rowid):
        return self._fetch_value("comments", rowid)

    def shares(self, rowid):
        return self._fetch_value("shares", rowid)

    def trend_score(self, rowid):
        result = self._fetch_value("trend_score", rowid)
        if result is None:
            views = self.views(rowid)
            likes = self.likes(rowid)
            comments = self.comments(rowid)
            shares = self.shares(rowid)
            try:
                score = (float(views or 0) * 0.4) + (float(likes or 0) * 0.2) + (float(comments or 0) * 0.2) + (float(shares or 0) * 0.2)
                result = score
            except (TypeError, ValueError):
                result = None
        result = float(result) if result is not None else None
        result = result//1000 if result else None
        result = str(result).strip("()") if result else None
        return result if result else None

    def velocity(self, rowid):
        result = None
        views = self.views(rowid)
        upload_date = self.upload_date(rowid)
        try:
            upload_ts = pd.to_datetime(upload_date, errors='coerce')
            if pd.notna(upload_ts):
                age_hours = max((pd.Timestamp.now() - upload_ts).total_seconds() / 3600, 0.1)
                result = float(views or 0) / age_hours
        except Exception:
            result = None
        result = float(result) if result is not None else None
        result = round(result, 2) if result else None
        return result if result else None

    def sentiment(self, rowid):
        return None

    def creator(self, rowid):
        return self._fetch_value("creator", rowid)

    def upload_date(self, rowid):
        return self._fetch_value("upload_date", rowid)


Num_res=DB_table_result(os.path.join(BASE_DIR, "trend_results.db"))
Num_raw=DB_table_raw(os.path.join(BASE_DIR, "raw_tiktok.db"))

Cap=Num_res.caption   
trend=Num_res.trend_score
rel=Num_res.relevance
update=Num_res.updated_at
nich=Num_res.niche_relevance
clus=Num_res.cluster_size
avgvel=Num_res.avg_velocity

Cap_raw=Num_raw.caption
hashtag=Num_raw.hashtags
view=Num_raw.views
like=Num_raw.likes
comment=Num_raw.comments
share=Num_raw.shares
trend_raw=Num_raw.trend_score
velocity=Num_raw.velocity
sentiment=Num_raw.sentiment
creator=Num_raw.creator
upload=Num_raw.upload_date


limiter=Limiter(get_remote_address)  # Limiter für die gesamte App
bp = Blueprint("main", __name__)

@bp.before_request
@limiter.limit("50 per minute")
@limiter.limit("1000 per day")
def start_timer():
    g.start_time = time.time()
def require_login():
    allowed_routes = [
        "main.login",
        "main.login_post",
        "main.register",        # 👈 hinzufügen
        "main.register_post",   # 👈 hinzufügen
        "static"
    ]
    if request.endpoint not in allowed_routes and not session.get("logged_in"):
        return redirect(url_for("main.login"))

@bp.after_request
def log_request(response):
    start = getattr(g, "start_time", None)
    duration = round(time.time() - start, 4) if start is not None else 0

    write_log(
        request.remote_addr,
        request.method,
        request.path,
        response.status_code,
        duration
    )

    return response
    
@bp.errorhandler(Exception)
def handle_exception(e):
    if isinstance(e, HTTPException):
        return e

    start = getattr(g, "start_time", None)
    duration = round(time.time() - start, 4) if start is not None else 0
    try:
        write_log_error(
            ip=request.remote_addr,
            method=request.method,
            path=request.path,
            status_code=500,
            response_time=duration,
            error=traceback.format_exc()
        )
    except Exception:
        pass
    # Im Debug-Modus echte Fehlermeldung anzeigen, damit man die Ursache sieht
    if current_app.debug:
        return "<pre>" + traceback.format_exc() + "</pre>", 500
    return "Internal Server Error", 500
def thema(i):
    thema=Cap(i)
    thema=thema[0]
    hashtags = re.findall(r"#\w+", thema, re.UNICODE)
    hashtags = [tag.strip("#") for tag in hashtags]
    if hashtags is None:
        return "No Hashtags"
    else:
        for i in hashtags:
            if i=="foryou" or i=="fyp" or i=="foryoupage" or i=="xyzbca" or i=="viral" or i=="trending":
                hashtags.remove(i)   
            return hashtags[0] if True else "No Hashtags"
def engament(i):
    try:
        likes_val = float(like(i) or 0)
        views_val = float(view(i) or 0)
        if views_val <= 0:
            return 0
        eng = likes_val / views_val
        eng = eng - 0.0000000001
        eng = round(eng, 4)
        return eng * 1000
    except (TypeError, ValueError, ZeroDivisionError):
        return 0


def _safe_text(value):
    if value is None:
        return ""
    return str(value).strip()


def _short_text(value, limit=140):
    text = _safe_text(value)
    if len(text) <= limit:
        return text
    return text[: max(limit - 1, 0)].rstrip() + "..."


def _parse_ai_guide(guide_text):
    sections = {
        "title": "",
        "videoformat": "",
        "hook": "",
        "idee": "",
        "drehablauf": "",
        "drehhinweise": "",
        "cta": "",
    }
    current_key = ""
    aliases = {
        "titel": "title",
        "title": "title",
        "videoformat": "videoformat",
        "format": "videoformat",
        "hook": "hook",
        "idee": "idee",
        "drehablauf": "drehablauf",
        "dreh-leitfaden": "drehablauf",
        "drehleitfaden": "drehablauf",
        "drehhinweise": "drehhinweise",
        "cta": "cta",
    }

    for raw_line in _safe_text(guide_text).splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = re.match(r"^([A-Za-zÄÖÜäöüß\- ]+):\s*(.*)$", line)
        if match:
            label = match.group(1).strip().lower()
            current_key = aliases.get(label, "")
            if current_key:
                sections[current_key] = match.group(2).strip()
            continue
        if current_key:
            existing = sections[current_key]
            sections[current_key] = f"{existing}\n{line}".strip()

    return sections


def _build_ai_idea_payload(record, fallback_id):
    record = record or {}
    parsed = _parse_ai_guide(record.get("ai_guide"))
    trend_title = _safe_text(record.get("caption"))
    notes = parsed.get("drehhinweise") or parsed.get("idee") or trend_title
    script = parsed.get("drehablauf") or parsed.get("idee") or ""
    hook = parsed.get("hook") or trend_title
    title = _safe_text(record.get("ai_title")) or parsed.get("title") or trend_title or "AI-Idee"
    video_format = parsed.get("videoformat") or "Trend-Remix"
    return {
        "id": _safe_text(record.get("video_id")) or f"idea-{fallback_id}",
        "title": title,
        "hook": hook,
        "trend": video_format,
        "videoType": "talking" if "talking" in video_format.lower() else "visual",
        "script": script,
        "notes": notes,
        "cta": parsed.get("cta") or "",
        "source_caption": trend_title,
        "sentiment": record.get("ai_sentiment"),
    }


def _build_ai_ideas(payload):
    records = []
    if isinstance(payload, dict):
        records = payload.get("ai_video_ideas") or []
    ideas = []
    for idx, record in enumerate(records, start=1):
        ideas.append(_build_ai_idea_payload(record, idx))
    return ideas


def _trend_card_from_record(record, fallback_idx):
    record = record or {}
    idx = record.get("rank") or fallback_idx
    try:
        idx = int(idx)
    except (TypeError, ValueError):
        idx = fallback_idx
    return {
        "idx": idx,
        "name": _safe_text(record.get("caption")) or f"Trend {idx}",
        "hype": record.get("trend_score"),
        "velocity": record.get("avg_velocity"),
        "velocity_num": float(record.get("avg_velocity") or 0),
        "engagement": record.get("avg_engagement"),
        "engagement_num": float(record.get("avg_engagement") or 0),
        "sentiment": record.get("ai_sentiment") or "—",
        "opp_num": (float(record.get("avg_velocity") or 0) / 1000.0) + float(record.get("avg_engagement") or 0),
    }


def _legacy_trend_cards(result, raw, engaments):
    cards = []
    for idx in range(1, 11):
        cards.append({
            "idx": idx,
            "name": _safe_text(result.get(f"Caption{idx}")) or _safe_text(raw.get(f"Caption_raw{idx}")) or f"Trend {idx}",
            "hype": result.get(f"Trend_Score{idx}"),
            "velocity": result.get(f"Avg_Velocity{idx}"),
            "velocity_num": float(result.get(f"Avg_Velocity{idx}") or 0),
            "engagement": engaments.get(f"Engament{idx}"),
            "engagement_num": float(engaments.get(f"Engament{idx}") or 0),
            "sentiment": raw.get(f"Sentiment{idx}") or "—",
            "opp_num": (float(result.get(f"Avg_Velocity{idx}") or 0) / 1000.0) + float(engaments.get(f"Engament{idx}") or 0),
        })
    return cards


def _load_user_trends_payload():
    user_id = _get_user_id_from_session()
    if not user_id:
        return {}
    json_path = os.path.join(BASE_DIR, f"trends_user_{user_id}.json")
    if not os.path.exists(json_path):
        return {}
    try:
        with open(json_path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return {}


def _build_trend_sections(payload, result, raw, engaments):
    if isinstance(payload, dict) and payload.get("top_trends"):
        top_trends = [_trend_card_from_record(item, idx) for idx, item in enumerate(payload.get("top_trends") or [], start=1)]
        rising_trends = [_trend_card_from_record(item, idx) for idx, item in enumerate(payload.get("rising_trends") or [], start=1)]
        opportunities = [_trend_card_from_record(item, idx) for idx, item in enumerate(payload.get("opportunities") or [], start=1)]
        global_trends = [_trend_card_from_record(item, idx) for idx, item in enumerate(payload.get("global_trends") or [], start=1)]
        return {
            "top_trends": top_trends[:4],
            "rising_trends": rising_trends[:4],
            "opportunities": opportunities[:4],
            "global_trends": global_trends[:4],
            "details": top_trends,
        }

    legacy_cards = _legacy_trend_cards(result, raw, engaments)
    top_by_hype = sorted(legacy_cards, key=lambda item: float(item.get("hype") or 0), reverse=True)
    rising = sorted(legacy_cards, key=lambda item: float(item.get("velocity_num") or 0), reverse=True)
    opportunities = sorted(legacy_cards, key=lambda item: float(item.get("opp_num") or 0), reverse=True)
    return {
        "top_trends": top_by_hype[:4],
        "rising_trends": rising[:4],
        "opportunities": opportunities[:4],
        "global_trends": legacy_cards[4:8] if len(legacy_cards) >= 8 else legacy_cards[4:],
        "details": legacy_cards,
    }


def _build_dashboard_trends(payload, result, raw, engaments):
    sections = _build_trend_sections(payload, result, raw, engaments)
    return sections.get("top_trends", [])[:4]


def register_socket_events(socketio):
    @socketio.on("ai_generate_idea")
    def handle_ai_generate_idea(data):
        if not session.get("logged_in"):
            emit("ai_generate_error", {"error": "Nicht eingeloggt."})
            return

        topic = _safe_text((data or {}).get("topic"))
        requested_format = _safe_text((data or {}).get("format"))
        user_id = _get_user_id_from_session()
        if not user_id:
            emit("ai_generate_error", {"error": "User konnte nicht ermittelt werden."})
            return
        if not topic:
            emit("ai_generate_error", {"error": "Bitte gib zuerst ein Thema an."})
            return

        emit("ai_generate_status", {"message": "KI-Idee wird am Schulserver generiert..."})
        payload = {
            "user_id": user_id,
            "topic": f"{topic}\nGewuenschtes Format: {requested_format}" if requested_format else topic,
        }

        try:
            req = urllib.request.Request(
                f"{AI_API_BASE_URL}/api/spontaneous",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=AI_API_TIMEOUT_SECONDS) as response:
                upstream_raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            try:
                body = exc.read().decode("utf-8")
                upstream_json = json.loads(body) if body else {}
                error_message = upstream_json.get("error") or f"AI-Server Fehler ({exc.code})"
            except Exception:
                error_message = f"AI-Server Fehler ({exc.code})"
            emit("ai_generate_error", {"error": error_message})
            return
        except Exception:
            emit("ai_generate_error", {"error": "AI-Server ist aktuell nicht erreichbar."})
            return

        try:
            upstream_json = json.loads(upstream_raw)
        except Exception:
            emit("ai_generate_error", {"error": "Ungültige Antwort vom AI-Server."})
            return

        idea_text = _safe_text(upstream_json.get("idea"))
        if not idea_text:
            emit("ai_generate_error", {"error": upstream_json.get("error") or "AI-Antwort ist leer."})
            return

        emit("ai_generate_result", {"idea": idea_text, "source": upstream_json.get("source") or "llm"})


def _empty_index_data():
    """Leere Dashboard-Daten, falls Trend-DBs fehlen oder Tabellen nicht existieren."""
    result = {}
    for i in range(1, 11):
        result["Caption%d" % i] = None
        result["Trend_Score%d" % i] = None
        result["Relevance%d" % i] = None
        result["Niche_Relevance%d" % i] = None
        result["Cluster_Size%d" % i] = None
        result["Avg_Velocity%d" % i] = None
    result["Updated At1"] = None
    for i in range(2, 11):
        result["Updated_At%d" % i] = None
    raw = {}
    for i in range(1, 11):
        raw["Caption_raw%d" % i] = raw["Hashtags%d" % i] = raw["Views%d" % i] = raw["Likes%d" % i] = None
        raw["Comments%d" % i] = raw["Shares%d" % i] = raw["Trend_Score_raw%d" % i] = raw["Velocity%d" % i] = None
        raw["Sentiment%d" % i] = raw["Creator%d" % i] = None
    raw["Upload Date1"] = None
    for i in range(2, 11):
        raw["Upload_Date%d" % i] = None
    themas = {"Thema%d" % i: None for i in range(1, 11)}
    engaments = {"Engament%d" % i: None for i in range(1, 11)}
    return result, raw, themas, engaments


@bp.route("/")
@limiter.limit("50 per minute")
@limiter.limit("1000 per day")
def index():
    if not session.get("logged_in"):
        return redirect(url_for("main.login"))
    if not session.get("onboarding_done", True):
        return redirect(url_for("main.onboarding"))
    user_trends_payload = _load_user_trends_payload()
    # Bei fehlender/leerer Trend-DB leere Dashboard-Daten verwenden (kein 500)
    try:
        Cap(1)
    except Exception:
        result, raw, themas, engaments = _empty_index_data()
        ai_ideas = _build_ai_ideas(user_trends_payload)
        compact_trends = _build_dashboard_trends(user_trends_payload, result, raw, engaments)
        return render_template("index.html", title="Dashboard",
            result=result, raw=raw, themas=themas, engaments=engaments, avg_velocity10=0,
            ai_ideas=ai_ideas, compact_trends=compact_trends)
    result={
        "Caption1": Cap(1),
        "Trend_Score1": trend(1),
        "Relevance1": rel(1),
        "Updated At1": update(1),
        "Niche_Relevance1": nich(1),
        "Cluster_Size1": clus(1),
        "Avg_Velocity1": avgvel(1),
        "Caption2": Cap(2),
        "Trend_Score2": trend(2),
        "Relevance2": rel(2),
        "Updated_At2": update(2),       
        "Niche_Relevance2": nich(2),
        "Cluster_Size2": clus(2),
        "Avg_Velocity2": avgvel(2),
        "Caption3": Cap(3),
        "Trend_Score3": trend(3),
        "Relevance3": rel(3),
        "Updated_At3": update(3),
        "Niche_Relevance3": nich(3),
        "Cluster_Size3": clus(3),
        "Avg_Velocity3": avgvel(3),
        "Caption4": Cap(4),
        "Trend_Score4": trend(4),
        "Relevance4": rel(4),
        "Updated_At4": update(4),
        "Niche_Relevance4": nich(4),
        "Cluster_Size4": clus(4),
        "Avg_Velocity4": avgvel(4),
        "Caption5": Cap(5),
        "Trend_Score5": trend(5),
        "Relevance5": rel(5),
        "Updated_At5": update(5),
        "Niche_Relevance5": nich(5),
        "Cluster_Size5": clus(5),
        "Avg_Velocity5": avgvel(5),
        "Caption6": Cap(6),
        "Trend_Score6": trend(6),
        "Relevance6": rel(6),
        "Updated_At6": update(6),
        "Niche_Relevance6": nich(6),
        "Cluster_Size6": clus(6),
        "Avg_Velocity6": avgvel(6),
        "Caption7": Cap(7),
        "Trend_Score7": trend(7),
        "Relevance7": rel(7),
        "Updated_At7": update(7),
        "Niche_Relevance7": nich(7),
        "Cluster_Size7": clus(7),
        "Avg_Velocity7": avgvel(7),
        "Caption8": Cap(8),
        "Trend_Score8": trend(8),
        "Relevance8": rel(8),
        "Updated_At8": update(8),
        "Niche_Relevance8": nich(8),
        "Cluster_Size8": clus(8),
        "Avg_Velocity8": avgvel(8),
        "Caption9": Cap(9),
        "Trend_Score9": trend(9),
        "Relevance9": rel(9),
        "Updated_At9": update(9),
        "Niche_Relevance9": nich(9),
        "Cluster_Size9": clus(9),
        "Avg_Velocity9": avgvel(9),
        "Caption10": Cap(10),
        "Trend_Score10": trend(10),
        "Relevance10": rel(10),
        "Updated_At10": update(10),
        "Niche_Relevance10": nich(10),
        "Cluster_Size10": clus(10),
        "Avg_Velocity10": avgvel(10)
    }
    raw={
        "Caption_raw1": Cap_raw(1),
        "Hashtags1": hashtag(1),
        "Views1": view(1),
        "Likes1": like(1),
        "Comments1": comment(1),
        "Shares1": share(1),
        "Trend_Score_raw1": trend_raw(1),
        "Velocity1": velocity(1),
        "Sentiment1": sentiment(1),
        "Creator1": creator(1),
        "Upload Date1": upload(1),
        "Caption_raw2": Cap_raw(2),
        "Hashtags2": hashtag(2),
        "Views2": view(2),
        "Likes2": like(2),
        "Comments2": comment(2),
        "Shares2": share(2),
        "Trend_Score_raw2": trend_raw(2),
        "Velocity2": velocity(2),
        "Sentiment2": sentiment(2),
        "Creator2": creator(2),
        "Upload Date2": upload(2),
        "Caption_raw3": Cap_raw(3),
        "Hashtags3": hashtag(3),
        "Views3": view(3),
        "Likes3": like(3),
        "Comments3": comment(3),
        "Shares3": share(3),
        "Trend_Score_raw3": trend_raw(3),
        "Velocity3": velocity(3),
        "Sentiment3": sentiment(3),
        "Creator3": creator(3),
        "Upload Date3": upload(3),
        "Caption_raw4": Cap_raw(4),
        "Hashtags4": hashtag(4),
        "Views4": view(4),
        "Likes4": like(4),
        "Comments4": comment(4),
        "Shares4": share(4),
        "Trend_Score_raw4": trend_raw(4),
        "Velocity4": velocity(4),
        "Sentiment4": sentiment(4),
        "Creator4": creator(4),
        "Upload Date4": upload(4),
        "Caption_raw5": Cap_raw(5),
        "Hashtags5": hashtag(5),
        "Views5": view(5),
        "Likes5": like(5),
        "Comments5": comment(5),
        "Shares5": share(5),
        "Trend_Score_raw5": trend_raw(5),
        "Velocity5": velocity(5),
        "Sentiment5": sentiment(5),
        "Creator5": creator(5),
        "Upload_Date5": upload(5),
        "Caption_raw6": Cap_raw(6),
        "Hashtags6": hashtag(6),
        "Views6": view(6),
        "Likes6": like(6),
        "Comments6": comment(6),
        "Shares6": share(6),
        "Trend_Score_raw6": trend_raw(6),
        "Velocity6": velocity(6),
        "Sentiment6": sentiment(6),
        "Creator6": creator(6),
        "Upload_Date6": upload(6),
        "Caption_raw7": Cap_raw(7),
        "Hashtags7": hashtag(7),
        "Views7": view(7),
        "Likes7": like(7),
        "Comments7": comment(7),
        "Shares7": share(7),
        "Trend_Score_raw7": trend_raw(7),
        "Velocity7": velocity(7),
        "Sentiment7": sentiment(7),
        "Creator7": creator(7),
        "Upload_Date7": upload(7),
        "Caption_raw8": Cap_raw(8),
        "Hashtags8": hashtag(8),
        "Views8": view(8),
        "Likes8": like(8),
        "Comments8": comment(8),
        "Shares8": share(8),
        "Trend_Score_raw8": trend_raw(8),
        "Velocity8": velocity(8),
        "Sentiment8": sentiment(8),
        "Creator8": creator(8),
        "Upload_Date8": upload(8),
        "Caption_raw9": Cap_raw(9),
        "Hashtags9": hashtag(9),
        "Views9": view(9),
        "Likes9": like(9),
        "Comments9": comment(9),
        "Shares9": share(9),
        "Trend_Score_raw9": trend_raw(9),
        "Velocity9": velocity(9),
        "Sentiment9": sentiment(9),
        "Creator9": creator(9),
        "Upload_Date9": upload(9),
        "Caption_raw10": Cap_raw(10),
        "Hashtags10": hashtag(10),
        "Views10": view(10),
        "Likes10": like(10),
        "Comments10": comment(10),
        "Shares10": share(10),
        "Trend_Score_raw10": trend_raw(10),
        "Velocity10": velocity(10),
        "Sentiment10": sentiment(10),
        "Creator10": creator(10),
        "Upload_Date10": upload(10)
    }
    themas={
        "Thema1": thema(1),
        "Thema2": thema(2),
        "Thema3": thema(3),
        "Thema4": thema(4),
        "Thema5": thema(5),
        "Thema6": thema(6),
        "Thema7": thema(7),
        "Thema8": thema(8),
        "Thema9": thema(9),
        "Thema10": thema(10)
    }
    engaments={
        "Engament1": engament(1),
        "Engament2": engament(2),
        "Engament3": engament(3),
        "Engament4": engament(4),
        "Engament5": engament(5),
        "Engament6": engament(6),
        "Engament7": engament(7),
        "Engament8": engament(8),
        "Engament9": engament(9),
        "Engament10": engament(10)
    }
    avg_velocity10=avgvel(1)+avgvel(2)+avgvel(3)+avgvel(4)+avgvel(5)+avgvel(6)+avgvel(7)+avgvel(8)+avgvel(9)+avgvel(10)
    avg_velocity10=avg_velocity10/10
    avg_velocity10=round(avg_velocity10,2)
    ai_ideas = _build_ai_ideas(user_trends_payload)
    compact_trends = _build_dashboard_trends(user_trends_payload, result, raw, engaments)
    return render_template("index.html", title="Dashboard",
        result=result,
        raw=raw,
        themas=themas,
        engaments=engaments,
        avg_velocity10=avg_velocity10,
        ai_ideas=ai_ideas,
        compact_trends=compact_trends
    )

@bp.route("/planner")
@limiter.limit("50 per minute")
@limiter.limit("1000 per day")
def planner():
    if not session.get("logged_in"):
        return redirect(url_for("main.login"))
    if not session.get("onboarding_done", True):
        return redirect(url_for("main.onboarding"))
    return render_template("planner.html", title="Content Planner")


@bp.route("/planner/month")
@limiter.limit("50 per minute")
@limiter.limit("1000 per day")
def planner_month():
    if not session.get("logged_in"):
        return redirect(url_for("main.login"))
    if not session.get("onboarding_done", True):
        return redirect(url_for("main.onboarding"))
    return render_template("planner_month.html", title="Monatsansicht")


@bp.route("/tasks")
@limiter.limit("50 per minute")
@limiter.limit("1000 per day")
def tasks():
    if not session.get("logged_in"):
        return redirect(url_for("main.login"))
    if not session.get("onboarding_done", True):
        return redirect(url_for("main.onboarding"))
    return render_template("tasks.html", title="Tasks")


@bp.route("/trends")
@limiter.limit("50 per minute")
@limiter.limit("1000 per day")
def trends():
    if not session.get("logged_in"):
        return redirect(url_for("main.login"))
    if not session.get("onboarding_done", True):
        return redirect(url_for("main.onboarding"))
    user_trends_payload = _load_user_trends_payload()
    try:
        Cap(1)
    except Exception:
        result, raw, themas, engaments = _empty_index_data()
        trend_sections = _build_trend_sections(user_trends_payload, result, raw, engaments)
        ai_ideas = _build_ai_ideas(user_trends_payload)
        return render_template("trends.html", title="Trends Explorer",
            result=result, raw=raw, themas=themas, engaments=engaments, avg_velocity10=0,
            trend_sections=trend_sections, ai_ideas=ai_ideas)
    result={
        "Caption1": Cap(1),
        "Trend_Score1": trend(1),
        "Relevance1": rel(1),
        "Updated At1": update(1),
        "Niche_Relevance1": nich(1),
        "Cluster_Size1": clus(1),
        "Avg_Velocity1": avgvel(1),
        "Caption2": Cap(2),
        "Trend_Score2": trend(2),
        "Relevance2": rel(2),
        "Updated_At2": update(2),       
        "Niche_Relevance2": nich(2),
        "Cluster_Size2": clus(2),
        "Avg_Velocity2": avgvel(2),
        "Caption3": Cap(3),
        "Trend_Score3": trend(3),
        "Relevance3": rel(3),
        "Updated_At3": update(3),
        "Niche_Relevance3": nich(3),
        "Cluster_Size3": clus(3),
        "Avg_Velocity3": avgvel(3),
        "Caption4": Cap(4),
        "Trend_Score4": trend(4),
        "Relevance4": rel(4),
        "Updated_At4": update(4),
        "Niche_Relevance4": nich(4),
        "Cluster_Size4": clus(4),
        "Avg_Velocity4": avgvel(4),
        "Caption5": Cap(5),
        "Trend_Score5": trend(5),
        "Relevance5": rel(5),
        "Updated_At5": update(5),
        "Niche_Relevance5": nich(5),
        "Cluster_Size5": clus(5),
        "Avg_Velocity5": avgvel(5),
        "Caption6": Cap(6),
        "Trend_Score6": trend(6),
        "Relevance6": rel(6),
        "Updated_At6": update(6),
        "Niche_Relevance6": nich(6),
        "Cluster_Size6": clus(6),
        "Avg_Velocity6": avgvel(6),
        "Caption7": Cap(7),
        "Trend_Score7": trend(7),
        "Relevance7": rel(7),
        "Updated_At7": update(7),
        "Niche_Relevance7": nich(7),
        "Cluster_Size7": clus(7),
        "Avg_Velocity7": avgvel(7),
        "Caption8": Cap(8),
        "Trend_Score8": trend(8),
        "Relevance8": rel(8),
        "Updated_At8": update(8),
        "Niche_Relevance8": nich(8),
        "Cluster_Size8": clus(8),
        "Avg_Velocity8": avgvel(8),
        "Caption9": Cap(9),
        "Trend_Score9": trend(9),
        "Relevance9": rel(9),
        "Updated_At9": update(9),
        "Niche_Relevance9": nich(9),
        "Cluster_Size9": clus(9),
        "Avg_Velocity9": avgvel(9),
        "Caption10": Cap(10),
        "Trend_Score10": trend(10),
        "Relevance10": rel(10),
        "Updated_At10": update(10),
        "Niche_Relevance10": nich(10),
        "Cluster_Size10": clus(10),
        "Avg_Velocity10": avgvel(10)
    }
    raw={
        "Caption_raw1": Cap_raw(1),
        "Hashtags1": hashtag(1),
        "Views1": view(1),
        "Likes1": like(1),
        "Comments1": comment(1),
        "Shares1": share(1),
        "Trend_Score_raw1": trend_raw(1),
        "Velocity1": velocity(1),
        "Sentiment1": sentiment(1),
        "Creator1": creator(1),
        "Upload Date1": upload(1),
        "Caption_raw2": Cap_raw(2),
        "Hashtags2": hashtag(2),
        "Views2": view(2),
        "Likes2": like(2),
        "Comments2": comment(2),
        "Shares2": share(2),
        "Trend_Score_raw2": trend_raw(2),
        "Velocity2": velocity(2),
        "Sentiment2": sentiment(2),
        "Creator2": creator(2),
        "Upload Date2": upload(2),
        "Caption_raw3": Cap_raw(3),
        "Hashtags3": hashtag(3),
        "Views3": view(3),
        "Likes3": like(3),
        "Comments3": comment(3),
        "Shares3": share(3),
        "Trend_Score_raw3": trend_raw(3),
        "Velocity3": velocity(3),
        "Sentiment3": sentiment(3),
        "Creator3": creator(3),
        "Upload Date3": upload(3),
        "Caption_raw4": Cap_raw(4),
        "Hashtags4": hashtag(4),
        "Views4": view(4),
        "Likes4": like(4),
        "Comments4": comment(4),
        "Shares4": share(4),
        "Trend_Score_raw4": trend_raw(4),
        "Velocity4": velocity(4),
        "Sentiment4": sentiment(4),
        "Creator4": creator(4),
        "Upload Date4": upload(4),
        "Caption_raw5": Cap_raw(5),
        "Hashtags5": hashtag(5),
        "Views5": view(5),
        "Likes5": like(5),
        "Comments5": comment(5),
        "Shares5": share(5),
        "Trend_Score_raw5": trend_raw(5),
        "Velocity5": velocity(5),
        "Sentiment5": sentiment(5),
        "Creator5": creator(5),
        "Upload_Date5": upload(5),
        "Caption_raw6": Cap_raw(6),
        "Hashtags6": hashtag(6),
        "Views6": view(6),
        "Likes6": like(6),
        "Comments6": comment(6),
        "Shares6": share(6),
        "Trend_Score_raw6": trend_raw(6),
        "Velocity6": velocity(6),
        "Sentiment6": sentiment(6),
        "Creator6": creator(6),
        "Upload_Date6": upload(6),
        "Caption_raw7": Cap_raw(7),
        "Hashtags7": hashtag(7),
        "Views7": view(7),
        "Likes7": like(7),
        "Comments7": comment(7),
        "Shares7": share(7),
        "Trend_Score_raw7": trend_raw(7),
        "Velocity7": velocity(7),
        "Sentiment7": sentiment(7),
        "Creator7": creator(7),
        "Upload_Date7": upload(7),
        "Caption_raw8": Cap_raw(8),
        "Hashtags8": hashtag(8),
        "Views8": view(8),
        "Likes8": like(8),
        "Comments8": comment(8),
        "Shares8": share(8),
        "Trend_Score_raw8": trend_raw(8),
        "Velocity8": velocity(8),
        "Sentiment8": sentiment(8),
        "Creator8": creator(8),
        "Upload_Date8": upload(8),
        "Caption_raw9": Cap_raw(9),
        "Hashtags9": hashtag(9),
        "Views9": view(9),
        "Likes9": like(9),
        "Comments9": comment(9),
        "Shares9": share(9),
        "Trend_Score_raw9": trend_raw(9),
        "Velocity9": velocity(9),
        "Sentiment9": sentiment(9),
        "Creator9": creator(9),
        "Upload_Date9": upload(9),
        "Caption_raw10": Cap_raw(10),
        "Hashtags10": hashtag(10),
        "Views10": view(10),
        "Likes10": like(10),
        "Comments10": comment(10),
        "Shares10": share(10),
        "Trend_Score_raw10": trend_raw(10),
        "Velocity10": velocity(10),
        "Sentiment10": sentiment(10),   
        "Creator10": creator(10),
        "Upload_Date10": upload(10)
    }
    themas={
        "Thema1": thema(1),
        "Thema2": thema(2),
        "Thema3": thema(3),
        "Thema4": thema(4),
        "Thema5": thema(5),
        "Thema6": thema(6),
        "Thema7": thema(7),
        "Thema8": thema(8),
        "Thema9": thema(9),
        "Thema10": thema(10)
    }
    engaments={
        "Engament1": engament(1),
        "Engament2": engament(2),
        "Engament3": engament(3),
        "Engament4": engament(4),
        "Engament5": engament(5),
        "Engament6": engament(6),
        "Engament7": engament(7),
        "Engament8": engament(8),
        "Engament9": engament(9),
        "Engament10": engament(10)
    }
    avg_velocity10=avgvel(1)+avgvel(2)+avgvel(3)+avgvel(4)+avgvel(5)+avgvel(6)+avgvel(7)+avgvel(8)+avgvel(9)+avgvel(10)
    avg_velocity10=avg_velocity10/10
    avg_velocity10=round(avg_velocity10,2)
    trend_sections = _build_trend_sections(user_trends_payload, result, raw, engaments)
    ai_ideas = _build_ai_ideas(user_trends_payload)
    return render_template("trends.html", title="Trends Explorer",
        result=result,
        raw=raw,
        themas=themas,
        engaments=engaments,
        avg_velocity10=avg_velocity10,
        trend_sections=trend_sections,
        ai_ideas=ai_ideas
    )


@bp.route("/settings", methods=["GET"])
@limiter.limit("50 per minute")
@limiter.limit("1000 per day")
def settings():
    if not session.get("logged_in"):
        return redirect(url_for("main.login"))
    if not session.get("onboarding_done", True):
        return redirect(url_for("main.onboarding"))
    return render_template("settings.html", title="Workspace Settings")


@bp.route("/settings/delete-account", methods=["POST"])
@limiter.limit("10 per hour")
def settings_delete_account():
    """Account des eingeloggten Users löschen und zur Login-Seite weiterleiten."""
    if not session.get("logged_in"):
        return redirect(url_for("main.login"))
    email = session.get("user_email")
    if email:
        try:
            conn = sqlite3.connect(USERS_DB)
            _ensure_users_table(conn)
            conn.execute("DELETE FROM users WHERE email = ?", (email,))
            conn.commit()
            conn.close()
        except Exception:
            pass
    session.clear()
    return redirect(url_for("main.login"))


@bp.route("/onboarding", methods=["GET"])
@limiter.limit("50 per minute")
@limiter.limit("1000 per day")
def onboarding():
    """Onboarding-Anzeige: nur für eingeloggte User, die es noch nicht abgeschlossen haben."""
    if not session.get("logged_in"):
        return redirect(url_for("main.login"))
    if session.get("onboarding_done", True):
        return redirect(url_for("main.index"))
    return render_template("onboarding.html", title="Onboarding")


@bp.route("/onboarding", methods=["POST"])
@limiter.limit("50 per minute")
@limiter.limit("1000 per day")
def onboarding_post():
    """Onboarding abschließen: Daten in user_onboarding_profile speichern, Session-Flag setzen."""
    if not session.get("logged_in"):
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"ok": False}), 401
        return redirect(url_for("main.login"))

    user_id = _get_user_id_from_session()
    if user_id is not None:
        try:
            conn = sqlite3.connect(USERS_DB)
            _ensure_onboarding_table(conn)
            cur = conn.cursor()
            # Mehrfachauswahl Content-Produktion als kommaseparierter String
            content_production = request.form.getlist("content_production_type")
            content_production_str = ", ".join(content_production) if content_production else None
            posts_per_week = request.form.get("posts_per_week")
            try:
                posts_per_week = int(posts_per_week) if posts_per_week else None
            except (TypeError, ValueError):
                posts_per_week = None
            cur.execute("""
                INSERT OR REPLACE INTO user_onboarding_profile (
                    user_id, industry, target_audience_type, target_age_group, audience_problem,
                    audience_description, product_description, unique_value, customer_problem, trust_factor,
                    competitors, competitor_strengths, competitive_advantage, industry_content_patterns,
                    posts_per_week, team_size, content_production_type, brand_tone, no_go_topics
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id,
                request.form.get("industry") or None,
                request.form.get("target_audience_type") or None,
                request.form.get("target_age_group") or None,
                request.form.get("audience_problem") or None,
                request.form.get("audience_description") or None,
                request.form.get("product_description") or None,
                request.form.get("unique_value") or None,
                request.form.get("customer_problem") or None,
                request.form.get("trust_factor") or None,
                request.form.get("competitors") or None,
                request.form.get("competitor_strengths") or None,
                request.form.get("competitive_advantage") or None,
                request.form.get("industry_content_patterns") or None,
                posts_per_week,
                request.form.get("team_size") or None,
                content_production_str,
                request.form.get("brand_tone") or None,
                request.form.get("no_go_topics") or None,
            ))
            conn.commit()
            conn.close()
        except Exception:
            pass  # Session-Flag trotzdem setzen, Logging optional

    session["onboarding_done"] = True
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"ok": True})
    return redirect(url_for("main.index"))


@bp.route("/api/ai/refine", methods=["POST"])
@limiter.limit("20 per minute")
@limiter.limit("200 per day")
def api_ai_refine():
    """Leitet AI-Ideen-Überarbeitung an den AI-Webserver weiter."""
    if not session.get("logged_in"):
        return jsonify({"ok": False, "error": "Nicht eingeloggt."}), 401

    payload = request.get_json(silent=True) or {}
    feedback = (payload.get("feedback") or "").strip()
    original_idea = (payload.get("original_idea") or "").strip()
    if not feedback or not original_idea:
        return jsonify({"ok": False, "error": "Fehlende Daten."}), 400

    user_id = _get_user_id_from_session()
    if user_id is None:
        return jsonify({"ok": False, "error": "User konnte nicht ermittelt werden."}), 400

    body = json.dumps({
        "user_id": user_id,
        "original_idea": original_idea,
        "feedback": feedback,
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{AI_API_BASE_URL}/api/refine",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=AI_API_TIMEOUT_SECONDS) as upstream:
            raw = upstream.read().decode("utf-8")
            status_code = upstream.getcode()
    except urllib.error.HTTPError as e:
        status_code = e.code
        raw = e.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError):
        return jsonify({"ok": False, "error": "AI-Server ist aktuell nicht erreichbar."}), 502

    try:
        upstream_json = json.loads(raw)
    except ValueError:
        return jsonify({"ok": False, "error": "Ungültige Antwort vom AI-Server."}), 502

    if status_code >= 400:
        return jsonify({"ok": False, "error": upstream_json.get("error", "AI-Server-Fehler.")}), 502

    refined = (upstream_json.get("refined_idea") or "").strip()
    if not refined:
        return jsonify({"ok": False, "error": "AI-Antwort ist leer."}), 502

    return jsonify({"ok": True, "refined_idea": refined})


@bp.route("/impressum")
@limiter.limit("50 per minute")
@limiter.limit("1000 per day")
def impressum():
    return render_template("impressum.html", title="Impressum")


@bp.route("/datenschutz")
@limiter.limit("50 per minute")
@limiter.limit("1000 per day")
def datenschutz():
    return render_template("datenschutz.html", title="Datenschutz")


@bp.route("/login", methods=["GET"])
@limiter.limit("50 per minute")
@limiter.limit("1000 per day")
def login():
    if session.get("logged_in"):
        return redirect(url_for("main.index"))
    return render_template("login.html", title="Login")


@bp.route("/login", methods=["POST"])
@limiter.limit("50 per minute")
@limiter.limit("5 per minute", methods=["POST"])
@limiter.limit("1000 per day", methods=["POST"])
def login_post():
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "").strip()

    if not email or not password:
        error = "Bitte E-Mail/Benutzername und Passwort ausfüllen."
        return render_template("login.html", title="Login", error=error, email=email)

    try:
        conn = sqlite3.connect(USERS_DB)
        _ensure_users_table(conn)
        cursor = conn.cursor()
        cursor.execute("SELECT password FROM users WHERE email = ?", (email,))
        result = cursor.fetchone()
        conn.close()
    except Exception:
        return render_template("login.html", title="Login",
            error="Fehler beim Zugriff auf die Benutzerdaten. Bitte später erneut versuchen.", email=email)

    try:
        pw_ok = result and check_password_hash(result[0], password)
    except (AttributeError, ValueError):
        # scrypt o.ä. auf diesem System nicht verfügbar (z.B. hashlib ohne scrypt)
        pw_ok = False
    if not pw_ok:
        error = "Ungültige E-Mail/Benutzername oder Passwort. Falls du dich früher mit anderem System registriert hast, bitte erneut registrieren."
        return render_template("login.html", title="Login", error=error, email=email)
    session.permanent = True  # 8h Lifetime (PERMANENT_SESSION_LIFETIME in __init__.py)
    session["logged_in"] = True
    session["user_email"] = email  # für dynamische Anzeige des Namens (Teil vor @)
    return redirect(url_for("main.index"))


@bp.route("/logout")
@limiter.limit("50 per minute",)
@limiter.limit("1000 per day")
def logout():
    # Dummy-Logout, leert die Session
    session.clear()
    return redirect(url_for("main.login"))
@bp.route("/register", methods=["GET"])
@limiter.limit("50 per minute")
@limiter.limit("1000 per day")
def register():
    return render_template("register.html", title="Registrieren")

@bp.route("/register", methods=["POST"])
@limiter.limit("50 per minute")
@limiter.limit("1000 per day")
@limiter.limit("5 per minute", methods=["POST"])
def register_post():
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "").strip()

    if not email or not password:
        error = "Bitte E-Mail und Passwort ausfüllen."
        return render_template("register.html", title="Registrieren", error=error, email=email)

    # E-Mail-Format: muss @ enthalten und Punkt im Domain-Teil (z.B. name@domain.com)
    if "@" not in email or "." not in email.split("@")[-1]:
        error = "Bitte eine gültige E-Mail-Adresse eingeben (z.B. name@domain.com)."
        return render_template("register.html", title="Registrieren", error=error, email=email, email_invalid=True)

    try:
        conn = sqlite3.connect(USERS_DB)
        _ensure_users_table(conn)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
        if cursor.fetchone():
            conn.close()
            error = "Benutzer existiert bereits."
            return render_template("register.html", title="Registrieren", error=error, email=email)
        # pbkdf2:sha256 statt scrypt – funktioniert überall (scrypt fehlt z.B. auf manchen Python-Installationen)
        hashed_pw = generate_password_hash(password, method="pbkdf2:sha256")
        cursor.execute(
            "INSERT INTO users (email, password) VALUES (?, ?)",
            (email, hashed_pw)
        )
        conn.commit()
        conn.close()
    except Exception:
        return render_template("register.html", title="Registrieren",
            error="Fehler beim Speichern. Bitte später erneut versuchen.", email=email)

    # Einmaliges Onboarding nach Registrierung: User einloggen und zu Onboarding schicken
    session.permanent = True
    session["logged_in"] = True
    session["user_email"] = email
    session["onboarding_done"] = False
    return redirect(url_for("main.onboarding"))
