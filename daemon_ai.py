import pandas as pd
import sys
import os

# Pfad anpassen, damit er die anderen Dateien im Ordner findet
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database_manager import load_recent_data, save_niche_results, init_dbs
from feature_pipeline import SocialTrendAnalyzer
from clustering_model import TrendClusterer
from trend_scoring import TrendScorer
# FIX: Nur noch das NICHES-Dictionary importieren, nicht die fehlende Funktion
from main import NICHES 

def filter_trends(df, niche_key):
    """Eigene, robuste Filterfunktion für die Heavy-AI"""
    if df.empty or 'caption' not in df.columns:
        return df
    
    keywords = NICHES.get(niche_key, [])
    if not keywords:
        return df
        
    pattern = "|".join([k.lower() for k in keywords])
    # Filtert die Cluster anhand der Caption
    return df[df['caption'].fillna("").str.lower().str.contains(pattern, na=False, regex=True)].copy()

def run_ai_once():
    print("[AI-Daemon] 🚀 Starte EINMALIGE KI-Analyse (One-Shot-Modus)...")
    init_dbs() 
    
    analyzer = SocialTrendAnalyzer()
    
    raw_data_list = load_recent_data(hours=48)
    print(f"[AI] Geladene Datensätze vom Raspi: {len(raw_data_list)}")
    
    if len(raw_data_list) < 5:
        print("[AI] ⚠️ Zu wenig Daten für ein sinnvolles Clustering. Abbruch.")
        return

    try:
        df_raw = pd.DataFrame(raw_data_list)
        
        # --- DER FIX: Fehlende 'scraped_at' Spalte mit JETZT auffüllen ---
        if 'scraped_at' not in df_raw.columns:
            df_raw['scraped_at'] = pd.Timestamp.now()
            
        # Datums-Handling absichern
        for col in ['scraped_at', 'upload_date']:
            if col in df_raw.columns:
                df_raw[col] = pd.to_datetime(df_raw[col], errors='coerce', utc=True).dt.tz_localize(None)

        print("[AI] Führe Feature Engineering durch...")
        df_engineered = analyzer.feature_engineering(df_raw)
        if df_engineered.empty: 
            print("[AI] ⚠️ Fehler im Feature Engineering. Abbruch.")
            return
        
        print("[AI] Generiere NLP-Embeddings (Sentence-BERT)...")
        embeddings = analyzer.generate_embeddings(df_engineered)
        X_train = analyzer.prepare_training_data(df_engineered, embeddings)

        print("[AI] Clustere Daten (UMAP + HDBSCAN)...")
        cluster_model = TrendClusterer()
        X_reduced = cluster_model.reduce_dimensions(X_train)
        labels = cluster_model.apply_hdbscan(X_reduced)
        df_engineered['cluster_id'] = labels

        print("[AI] Berechne Trend-Scores...")
        scorer = TrendScorer()
        cluster_stats = scorer.aggregate_cluster_metrics(df_engineered)
        scored_trends = scorer.calculate_scores(cluster_stats)
        
        if scored_trends.empty:
            print("[AI] ⚠️ Keine validen Cluster gefunden.")
            return

        final_report = scorer.classify_lifecycle(scored_trends)

        print("[AI] Speichere Ergebnisse...")
        
        # --- GENERAL TRENDS ---
        top_general = final_report[final_report['trend_score'] > 30].head(10)
        save_niche_results("general", top_general)
        print(f"   -> ✅ Gespeichert: general ({len(top_general)} Trends)")

        # --- NISCHEN TRENDS ---
        for niche_key in NICHES.keys():
            niche_trends = filter_trends(final_report, niche_key)
            top_trends = niche_trends[niche_trends['trend_score'] > 30].head(10)
            
            if not top_trends.empty:
                save_niche_results(niche_key, top_trends)
                print(f"   -> ✅ Gespeichert: {niche_key} ({len(top_trends)} Trends)")
            else:
                save_niche_results(niche_key, pd.DataFrame())

        print("\n🏁 KI-Analyse erfolgreich abgeschlossen! Server ist bereit für DeepSeek.")

    except Exception as e:
        print(f"[AI Critical Error] {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_ai_once()