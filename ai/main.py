import pandas as pd
from textblob import TextBlob
from database_manager import load_recent_data, save_niche_results

# --- KONFIGURATION DER NISCHEN ---
NICHES = {
    "gastro": ["food", "essen", "recipe", "kochen", "cooking", "lecker", "delicious", "meal", "dinner", "lunch", "frühstück", "pizza", "burger", "pasta", "kitchen"],
    "fitness": ["fitness", "gym", "workout", "sport", "training", "muscle", "run", "yoga", "health", "abnehmen", "diet", "bodybuilding", "exercise"],
    "tech": ["tech", "ai", "gadget", "iphone", "android", "software", "code", "programming", "robot", "computer", "laptop", "innovation", "crypto", "bitcoin"],
    "fashion": ["fashion", "style", "outfit", "ootd", "clothes", "wear", "dress", "shoes", "sneaker", "gucci", "zara", "model", "beauty", "makeup"],
    "business": ["business", "money", "finance", "invest", "stock", "aktien", "crypto", "marketing", "job", "career", "rich", "wealth", "startup", "entrepreneur"]
}

# Diese Spalten wollen wir am Ende haben
RESULT_COLUMNS = ['video_id', 'caption', 'hashtags', 'views', 'likes', 'comments', 'shares', 'upload_date', 'creator', 'trend_score', 'velocity', 'sentiment']

def get_sentiment(text):
    if not isinstance(text, str): return 0.0
    analysis = TextBlob(text)
    return round(analysis.sentiment.polarity, 2)

def filter_data_by_keywords(df, keywords):
    if df.empty: return pd.DataFrame()
    df['search_text'] = (df['caption'] + " " + df['hashtags']).fillna("").str.lower()
    pattern = "|".join([k.lower() for k in keywords])
    filtered_df = df[df['search_text'].str.contains(pattern, na=False, regex=True)].copy()
    del filtered_df['search_text']
    return filtered_df

def run_analysis_pipeline():
    print("--- 🚀 Starte Analyse-Pipeline (Robust) ---")
    
    # 1. Daten laden
    raw_df = load_recent_data(hours=48)
    
    if raw_df.empty:
        print("[Warnung] Keine Daten gefunden.")
        return

    print(f"[Info] {len(raw_df)} Videos geladen.")
    
    # --- FEHLERTOLERANZ-FIX ---
    # Wir prüfen, ob alle Spalten da sind. Wenn nicht, erstellen wir sie mit 0.
    expected_metrics = ['views', 'likes', 'comments', 'shares']
    for col in expected_metrics:
        if col not in raw_df.columns:
            print(f"[Auto-Fix] Spalte '{col}' fehlt, wird mit 0 aufgefüllt.")
            raw_df[col] = 0

    # Datentypen fixen (alles zu Zahlen machen)
    for col in expected_metrics:
         raw_df[col] = pd.to_numeric(raw_df[col], errors='coerce').fillna(0)
    
    # Sentiment berechnen
    print("[AI] Berechne Stimmungsbild...")
    raw_df['full_text'] = raw_df['caption'].fillna("") + " " + raw_df['hashtags'].fillna("")
    raw_df['sentiment'] = raw_df['full_text'].apply(get_sentiment)

    raw_df['upload_date'] = pd.to_datetime(raw_df['upload_date'])
    now = pd.Timestamp.now()
    raw_df['age_hours'] = (now - raw_df['upload_date']).dt.total_seconds() / 3600
    raw_df['velocity'] = raw_df['views'] / (raw_df['age_hours'] + 1)
    
    # --- 2. GENERAL TRENDS ---
    print("\n--- Analysiere 'General' ---")
    try:
        df_gen = raw_df.copy()
        # Score Berechnung
        df_gen['trend_score'] = (df_gen['views'] * 0.4) + (df_gen['velocity'] * 0.4) + (df_gen['likes'] * 0.2)
        
        m = df_gen['trend_score'].max()
        if m > 0: df_gen['trend_score'] = (df_gen['trend_score'] / m) * 100
        
        top10 = df_gen.sort_values(by='trend_score', ascending=False).head(10)
        
        # Nur verfügbare Spalten speichern
        cols_to_save = [c for c in RESULT_COLUMNS if c in top10.columns]
        save_niche_results(top10[cols_to_save], "general")
        
    except Exception as e:
        print(f"[Error] General Analyse fehlgeschlagen: {e}")

    # --- 3. NISCHEN ---
    for niche, keywords in NICHES.items():
        print(f"\n--- Analysiere Nische: '{niche}' ---")
        niche_df = filter_data_by_keywords(raw_df, keywords)
        
        if len(niche_df) < 1: # Bei sehr wenig Daten trotzdem speichern (leer)
            print(f"[Info] Zu wenig Daten für {niche}. Speichere leere Tabelle.")
            empty_df = pd.DataFrame(columns=RESULT_COLUMNS)
            save_niche_results(empty_df, niche) 
            continue
            
        print(f"[Info] {len(niche_df)} Videos in {niche} gefunden.")
        
        try:
            niche_df['trend_score'] = (niche_df['views'] * 0.4) + (niche_df['velocity'] * 0.4) + (niche_df['likes'] * 0.2)
            m = niche_df['trend_score'].max()
            if m > 0: niche_df['trend_score'] = (niche_df['trend_score'] / m) * 100
            
            top10_niche = niche_df.sort_values(by='trend_score', ascending=False).head(10)
            
            cols_to_save = [c for c in RESULT_COLUMNS if c in top10_niche.columns]
            save_niche_results(top10_niche[cols_to_save], niche)
            
        except Exception as e:
            print(f"[Error] Analyse für {niche} fehlgeschlagen: {e}")

    print("\n--- ✅ Analyse abgeschlossen ---")

if __name__ == "__main__":
    run_analysis_pipeline()
