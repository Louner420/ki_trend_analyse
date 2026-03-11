import pandas as pd
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.preprocessing import StandardScaler
from datetime import datetime

class SocialTrendAnalyzer:
    def __init__(self):
        """
        Initialisiert die Pipeline.
        Lädt das NLP-Modell für Text-Embeddings einmalig in den Speicher.
        """
        print("[ML] Lade NLP-Modell (Sentence-BERT)...")
        # 'all-MiniLM-L6-v2' ist schnell und effizient für Clustering-Aufgaben
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        self.scaler = StandardScaler()

    def load_data_from_scraper(self, scraper_output: dict):
        """
        NEU: Konvertiert das Dictionary deines Scrapers in einen DataFrame.
        """
        if not scraper_output or "data" not in scraper_output:
            print("[Error] Ungültiges Datenformat vom Scraper.")
            return pd.DataFrame()

        # Extrahiere die Liste der Videos
        data_list = scraper_output["data"]
        df = pd.DataFrame(data_list)
        
        # Den globalen 'fetched_at' Zeitpunkt vom Scraper holen
        fetched_at_str = scraper_output.get("fetched_at")
        
        # Zeitstempel konvertieren (Scraper liefert ISO Strings)
        # errors='coerce' verhindert Absturz bei kaputten Datumsformaten
        if 'upload_date' in df.columns:
            df['upload_date'] = pd.to_datetime(df['upload_date'], errors='coerce')
        
        # Scraped_at für alle Zeilen setzen (wichtig für Alters-Berechnung)
        if fetched_at_str:
            df['scraped_at'] = pd.to_datetime(fetched_at_str)
        else:
            df['scraped_at'] = datetime.now() # Fallback

        return df

    def feature_engineering(self, df):
        """
        Kernaufgabe: Verwandelt Rohdaten in mathematisch verwertbare Features.
        """
        print("[ML] Starte Feature Engineering...")
        
        if df.empty:
            return df

        # Datumsfelder robust normalisieren (einige Datenquellen liefern kein scraped_at).
        if 'scraped_at' in df.columns:
            df['scraped_at'] = pd.to_datetime(df['scraped_at'], errors='coerce', utc=True).dt.tz_localize(None)
        else:
            df['scraped_at'] = pd.NaT
        if 'upload_date' in df.columns:
            df['upload_date'] = pd.to_datetime(df['upload_date'], errors='coerce', utc=True).dt.tz_localize(None)
        else:
            df['upload_date'] = pd.NaT

        now_ts = pd.Timestamp.now(tz='UTC').tz_localize(None)
        df['scraped_at'] = df['scraped_at'].fillna(now_ts)
        df['upload_date'] = df['upload_date'].fillna(df['scraped_at'])

        # 1. Zeitliche Metriken berechnen
        # Alter des Videos in Stunden zum Zeitpunkt des Scrapes
        df['age_hours'] = (df['scraped_at'] - df['upload_date']).dt.total_seconds() / 3600
        # Vermeidung von Division durch Null bei brandneuen Videos (min 0.1h)
        df['age_hours'] = df['age_hours'].clip(lower=0.1)

        # 2. Engagement Normalisierung (Interaction Rate)
        # Dein Scraper liefert: likes, comments, shares, views
        # Falls Spalten fehlen, mit 0 auffüllen
        for col in ['likes', 'comments', 'shares', 'views']:
            if col not in df.columns:
                df[col] = 0
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        # Gewichtete Summe: Ein Share ist oft "wertvoller" als ein Like für Viralität
        df['total_interactions'] = df['likes'] + df['comments'] + (df['shares'] * 2.0)
        
        # Engagement Rate (Interaktionen pro View)
        # +1 im Nenner verhindert Fehler bei 0 Views
        df['engagement_rate'] = df['total_interactions'] / (df['views'] + 1)

        # 3. Viralitäts-Koeffizient (Verhältnis Shares zu Likes)
        df['viral_coefficient'] = df['shares'] / (df['likes'] + 1)

        # 4. Wachstums-Proxy (Velocity)
        # Views pro Stunde seit Upload (Durchschnittsgeschwindigkeit)
        df['velocity_views_per_hour'] = df['views'] / df['age_hours']

        return df

    def generate_embeddings(self, df):
        """
        Verwandelt Text (Captions + Hashtags) in hochdimensionale Vektoren.
        """
        print("[ML] Generiere Text-Embeddings...")
        
        if df.empty:
            return np.array([])

        # Text kombinieren: Caption + Hashtags + Sound
        # Fillna, falls Text fehlt
        caption = df['caption'].fillna('') if 'caption' in df.columns else ''
        hashtags = df['hashtags'].fillna('') if 'hashtags' in df.columns else ''
        sound = df['sound_name'].fillna('') if 'sound_name' in df.columns else ''

        df['full_text'] = caption + " " + hashtags + " " + sound
        
        # Encoding durchführen
        embeddings = self.embedding_model.encode(df['full_text'].tolist(), show_progress_bar=False)
        
        return embeddings

    def prepare_training_data(self, df, embeddings):
        """
        Führt numerische Features und Text-Embeddings zusammen 
        und normalisiert sie für das Clustering.
        """
        if df.empty:
            return np.array([])

        # Relevante numerische Features auswählen
        numerical_features = df[[
            'engagement_rate', 
            'viral_coefficient', 
            'velocity_views_per_hour',
            'views',
            'likes'
        ]].values

        # Normalisierung (Z-Score Scaling)
        numerical_scaled = self.scaler.fit_transform(numerical_features)

        # Zusammenfügen: Numerische Matrix + Embedding Matrix
        final_feature_matrix = np.hstack([numerical_scaled, embeddings])
        
        return final_feature_matrix