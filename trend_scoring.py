import pandas as pd
import numpy as np
from sklearn.preprocessing import MinMaxScaler

class TrendScorer:
    def __init__(self, weights=None):
        """
        Initialisiert das Scoring-Modell.
        Weights können angepasst werden, um z.B. Viralität stärker zu gewichten.
        """
        if weights is None:
            self.weights = {
                'volume': 0.2,      # Wie groß ist der Cluster?
                'velocity': 0.4,    # Wie schnell wächst er? (WICHTIG!)
                'engagement': 0.3,  # Wie gut reagieren die Leute?
                'recency': 0.1      # Wie neu ist das Thema?
            }
        else:
            self.weights = weights
        
        self.scaler = MinMaxScaler()

    def aggregate_cluster_metrics(self, df_clustered):
        """
        Fasst die vielen Videos eines Clusters zu einem einzigen "Trend-Datensatz" zusammen.
        """
        # Rauschen (-1) herausfiltern
        if 'cluster_id' not in df_clustered.columns:
            return pd.DataFrame()
            
        df_clean = df_clustered[df_clustered['cluster_id'] != -1].copy()
        
        if df_clean.empty:
            return pd.DataFrame()

        # --- FIX: Creator Spalte sicherstellen ---
        if 'creator' not in df_clean.columns:
            df_clean['creator'] = 'unknown'
        if 'hashtags' not in df_clean.columns:
            df_clean['hashtags'] = ''

        # Aggregations-Regeln definieren
        agg_rules = {
            'video_id': 'count',
            'velocity_views_per_hour': 'median',
            'engagement_rate': 'mean',
            'age_hours': 'mean',
            # Nimm den häufigsten Creator im Cluster als Repräsentant
            'creator': lambda x: x.mode()[0] if not x.mode().empty else "unknown",
            # Nimm die längste Caption als Repräsentant (oft informativer)
            'caption': lambda x: max(x.astype(str), key=len) if not x.empty else "",
            # --- NEU: Hashtags retten (Nimm die längste Sammlung) ---
            'hashtags': lambda x: max(x.fillna("").astype(str), key=len) if not x.empty else ""
        }
        
        # Gruppieren
        cluster_stats = df_clean.groupby('cluster_id').agg(agg_rules)
        
        # Spalten umbenennen für Klarheit
        cluster_stats = cluster_stats.rename(columns={
            'video_id': 'cluster_size',
            'velocity_views_per_hour': 'avg_velocity',
            'engagement_rate': 'avg_engagement',
            'age_hours': 'avg_age_hours'
        })
        
        return cluster_stats

    def calculate_scores(self, cluster_stats):
        """
        Berechnet den finalen Trend-Score (0-100).
        """
        if cluster_stats.empty:
            return pd.DataFrame()
            
        df = cluster_stats.copy()

        # Logarithmische Skalierung für Größe und Velocity
        df['log_size'] = np.log1p(df['cluster_size'])
        df['log_velocity'] = np.log1p(df['avg_velocity'])

        # Features normalisieren (auf 0-1 bringen)
        features = ['log_size', 'log_velocity', 'avg_engagement', 'avg_age_hours']
        
        try:
            scaled = self.scaler.fit_transform(df[features])
            df_norm = pd.DataFrame(scaled, columns=features, index=df.index)
        except ValueError:
            # Falls zu wenig Daten für Scaling da sind
            df_norm = pd.DataFrame(0.5, columns=features, index=df.index)

        # Score berechnen (Gewichtete Summe)
        score = (
            self.weights['volume'] * df_norm['log_size'] +
            self.weights['velocity'] * df_norm['log_velocity'] +
            self.weights['engagement'] * df_norm['avg_engagement'] +
            self.weights['recency'] * (1 - df_norm['avg_age_hours'])
        )
        
        df['trend_score'] = score * 100
        
        # Sortieren: Beste zuerst
        return df.sort_values('trend_score', ascending=False)

    def classify_lifecycle(self, df_scored):
        """
        Bestimmt die Phase des Trends (Emerging, Peaking, Stagnant).
        """
        if df_scored.empty: return df_scored

        median_vel = df_scored['avg_velocity'].median()
        median_size = df_scored['cluster_size'].median()
        
        def get_phase(row):
            is_fast = row['avg_velocity'] > median_vel
            is_big = row['cluster_size'] > median_size
            
            if is_fast and not is_big: return "EMERGING 🚀"
            if is_fast and is_big: return "PEAKING 🔥"
            if not is_fast and is_big: return "STAGNANT 📉"
            return "NICHE / NOISE 💤"

        df_scored['lifecycle_phase'] = df_scored.apply(get_phase, axis=1)
        return df_scored
