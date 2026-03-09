from flask import Blueprint, render_template, request, redirect, url_for, session, current_app, jsonify
import sqlite3
import re
import time
import traceback
import os
from flask import Flask, request, g
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.security import generate_password_hash, check_password_hash

# Alle DBs im Projektordner (funktioniert auf Mac und Windows)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGS_DB = os.path.join(BASE_DIR, "logs.db")
ERROR_DB = os.path.join(BASE_DIR, "error.db")
USERS_DB = os.path.join(BASE_DIR, "users.db")


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
        rounded_result = float(result[0]) if result else None
        rounded_result = round(rounded_result, 2) if rounded_result else None
        return rounded_result

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

    def caption(self, rowid):
        self.cursor.execute(
            "SELECT caption FROM top10_general WHERE rowid = ?",
            (int(rowid),)
        )
        result = self.cursor.fetchone()
        return result[0] if result else None

    def hashtags(self, rowid):
        self.cursor.execute(
            "SELECT hashtags FROM top10_general WHERE rowid = ?",
            (int(rowid),)
        )
        result = self.cursor.fetchone()
        return result[0] if result else None

    def views(self, rowid):
        self.cursor.execute(
            "SELECT views FROM top10_general WHERE rowid = ?",
            (int(rowid),)
        )
        result = self.cursor.fetchone()
        return result[0] if result else None

    def likes(self, rowid):
        self.cursor.execute(
            "SELECT likes FROM top10_general WHERE rowid = ?",
            (int(rowid),)
        )
        result = self.cursor.fetchone()
        return result[0] if result else None

    def comments(self, rowid):
        self.cursor.execute(
            "SELECT comments FROM top10_general WHERE rowid = ?",
            (int(rowid),)
        )
        result = self.cursor.fetchone()
        return result[0] if result else None

    def shares(self, rowid):
        self.cursor.execute(
            "SELECT shares FROM top10_general WHERE rowid = ?",
            (int(rowid),)
        )
        result = self.cursor.fetchone()
        return result[0] if result else None

    def trend_score(self, rowid):
        self.cursor.execute(
            "SELECT trend_score FROM top10_general WHERE rowid = ?",
            (int(rowid),)
            
        )
        result = self.cursor.fetchone()
        result = float(result[0]) if result else None
        result = result//1000 if result else None
        result = str(result).strip("(",")") if result else None
        return result if result else None

    def velocity(self, rowid):
        self.cursor.execute(
            "SELECT velocity FROM top10_general WHERE rowid = ?",
            (int(rowid),)
        )
        result = self.cursor.fetchone()
        result = float(result[0]) if result else None
        result = round(result, 2) if result else None
        return result if result else None

    def sentiment(self, rowid):
        self.cursor.execute(
            "SELECT sentiment FROM top10_general WHERE rowid = ?",
            (int(rowid),)
        )
        result = self.cursor.fetchone()
        return result[0] if result else None

    def creator(self, rowid):
        self.cursor.execute(
            "SELECT creator FROM top10_general WHERE rowid = ?",
            (int(rowid),)
        )
        result = self.cursor.fetchone()
        return result[0] if result else None

    def upload_date(self, rowid):
        self.cursor.execute(
            "SELECT upload_date FROM top10_general WHERE rowid = ?",
            (int(rowid),)
        )
        result = self.cursor.fetchone()
        return result[0] if result else None


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
    duration = round(time.time() - g.start_time, 4)

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
    eng=like(i)/view(i)
    eng=eng-0.0000000001
    eng=round(eng,4)
    return eng*1000


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
    # Bei fehlender/leerer Trend-DB leere Dashboard-Daten verwenden (kein 500)
    try:
        Cap(1)
    except Exception:
        result, raw, themas, engaments = _empty_index_data()
        return render_template("index.html", title="Dashboard",
            result=result, raw=raw, themas=themas, engaments=engaments, avg_velocity10=0)
    result={
        "Caption1": Cap(1),
        "Trend_Score1": trend(1),
        "Relevance1": rel(1),
        "Updated At1": update(1),
        "Niche_Relevance1": nich(1),
        "Cluster_Size1": clus(1),
        "Avg_Velocity1": avgvel(1),
        "Caption2": Cap(12),
        "Trend_Score2": trend(12),
        "Relevance2": rel(12),
        "Updated_At2": update(12),       
        "Niche_Relevance2": nich(12),
        "Cluster_Size2": clus(12),
        "Avg_Velocity2": avgvel(12),
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
        "Thema2": thema(12),
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
    avg_velocity10=avgvel(1)+avgvel(3)+avgvel(4)+avgvel(5)+avgvel(6)+avgvel(7)+avgvel(8)+avgvel(9)+avgvel(10)
    avg_velocity10=avg_velocity10/10
    avg_velocity10=round(avg_velocity10,2)
    return render_template("index.html", title="Dashboard",
        result=result,
        raw=raw,
        themas=themas,
        engaments=engaments,
        avg_velocity10=avg_velocity10
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
    try:
        Cap(1)
    except Exception:
        result, raw, themas, engaments = _empty_index_data()
        return render_template("trends.html", title="Trends Explorer",
            result=result, raw=raw, themas=themas, engaments=engaments, avg_velocity10=0)
    result={
        "Caption1": Cap(1),
        "Trend_Score1": trend(1),
        "Relevance1": rel(1),
        "Updated At1": update(1),
        "Niche_Relevance1": nich(1),
        "Cluster_Size1": clus(1),
        "Avg_Velocity1": avgvel(12),
        "Caption2": Cap(12),
        "Trend_Score2": trend(12),
        "Relevance2": rel(12),
        "Updated_At2": update(12),       
        "Niche_Relevance2": nich(12),
        "Cluster_Size2": clus(12),
        "Avg_Velocity2": avgvel(12),
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
        "Thema2": thema(12),
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
    avg_velocity10=avgvel(1)+avgvel(3)+avgvel(4)+avgvel(5)+avgvel(6)+avgvel(7)+avgvel(8)+avgvel(9)+avgvel(10)
    avg_velocity10=avg_velocity10/10
    avg_velocity10=round(avg_velocity10,2)
    return render_template("trends.html", title="Trends Explorer",
        result=result,
        raw=raw,
        themas=themas,
        engaments=engaments,
        avg_velocity10=avg_velocity10
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
