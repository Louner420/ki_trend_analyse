import time
import pandas as pd
import sys
import os

# Pfad anpassen, falls Module nicht gefunden werden (für Raspy wichtig)
# Füge Parent-Verzeichnis (ai/) hinzu, um database_manager etc zu importieren
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database_manager import load_recent_data, save_niche_results, init_dbs
from feature_pipeline import SocialTrendAnalyzer
from clustering_model import TrendClusterer
from trend_scoring import TrendScorer
from main import NICHES 


def filter_trends_by_niche(df, niche_key):
    """Filtert Trends nach Nischen-Keywords; 'general' bekommt alle Trends."""
    if df is None or df.empty:
        return pd.DataFrame()
    if niche_key == "general":
        return df.copy()

    keywords = NICHES.get(niche_key, [])
    if not keywords:
        return pd.DataFrame()

    captions = df["caption"].fillna("").astype(str) if "caption" in df.columns else pd.Series([""] * len(df), index=df.index)
    hashtags = df["hashtags"].fillna("").astype(str) if "hashtags" in df.columns else pd.Series([""] * len(df), index=df.index)
    search_text = (captions + " " + hashtags).str.lower()
    pattern = "|".join([k.lower() for k in keywords])
    mask = search_text.str.contains(pattern, na=False, regex=True)
    return df.loc[mask].copy()

def run_ai_loop():
    print("[AI-Daemon] Starte KI-Service...")
    init_dbs() # Datenbank-Struktur sicherstellen
    run_once = os.getenv("AI_RUN_ONCE", "0") == "1"
    
    analyzer = SocialTrendAnalyzer()
    
    while True:
        print("\n[AI] --- Neuer Zyklus ---")
        
        # 1. Daten laden (letzte 24h)
        raw_data_list = load_recent_data(hours=6)
        print(f"[AI] Geladene Datensätze: {len(raw_data_list)}")
        
        # Wenn zu wenig Daten, kurz warten und neu prüfen
        if len(raw_data_list) < 5:
            print("[AI] Zu wenig Daten. Warte auf Scraper...")
            time.sleep(60) 
            continue

        try:
            # 2. KI Pipeline
            df_raw = pd.DataFrame(raw_data_list)

            # Laufzeit auf dem Raspberry stabil halten: auf die neuesten Datensätze begrenzen.
            if len(df_raw) > 600:
                if 'upload_date' in df_raw.columns:
                    df_raw['upload_date'] = pd.to_datetime(df_raw['upload_date'], errors='coerce')
                    df_raw = df_raw.sort_values('upload_date', ascending=False).head(600)
                else:
                    df_raw = df_raw.head(600)
            
            # Datums-Handling
            for col in ['scraped_at', 'upload_date']:
                if col in df_raw.columns:
                    df_raw[col] = pd.to_datetime(df_raw[col], errors='coerce')

            # Features & Embeddings
            print("[AI] Feature Engineering...")
            df_engineered = analyzer.feature_engineering(df_raw)
            if df_engineered.empty: continue
            
            embeddings = analyzer.generate_embeddings(df_engineered)
            X_train = analyzer.prepare_training_data(df_engineered, embeddings)

            # Clustering
            print("[AI] Clustering...")
            cluster_model = TrendClusterer()
            X_reduced = cluster_model.reduce_dimensions(X_train)
            labels = cluster_model.apply_hdbscan(X_reduced)
            df_engineered['cluster_id'] = labels

            # Scoring
            print("[AI] Scoring...")
            scorer = TrendScorer()
            cluster_stats = scorer.aggregate_cluster_metrics(df_engineered)
            scored_trends = scorer.calculate_scores(cluster_stats)
            
            if scored_trends.empty:
                print("[AI] Keine Cluster gefunden.")
                if run_once:
                    print("[AI] Einmalmodus aktiv. Beende ohne Wartezeit.")
                    break
                time.sleep(60)
                continue

            final_report = scorer.classify_lifecycle(scored_trends)

            # 3. Speichern für ALLE Nischen (inkl. General)
            print("[AI] Speichere Ergebnisse...")
            for niche_key in ["general", *NICHES.keys()]:
                # Filterung (mit Fix für "General")
                niche_trends = filter_trends_by_niche(final_report, niche_key)
                
                # Threshold Filter: Nur gute Trends speichern (Score > 30)
                top_trends = niche_trends[niche_trends['trend_score'] > 30].head(10)
                
                if not top_trends.empty:
                    save_niche_results(niche_key, top_trends)
                    print(f"   -> Gespeichert: {niche_key} ({len(top_trends)} Trends)")
                else:
                    # Leere Liste speichern (um alte Daten zu löschen, falls keine Trends mehr da sind)
                    save_niche_results(niche_key, pd.DataFrame())

        except Exception as e:
            print(f"[AI Critical Error] {e}")
            import traceback
            traceback.print_exc()

            if run_once:
                print("[AI] Einmalmodus aktiv. Beende nach Fehler ohne Wartezeit.")
                break
        
        if run_once:
            print("[AI] Einmalmodus aktiv. Zyklus abgeschlossen, beende jetzt.")
            break

        print("[AI] Zyklus beendet. Schlafe 5 Minuten...")
        time.sleep(300) 

if __name__ == "__main__":
    run_ai_loop()