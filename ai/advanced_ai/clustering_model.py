import numpy as np
import pandas as pd
import umap
import hdbscan
from sklearn.cluster import KMeans
import matplotlib.pyplot as plt
import seaborn as sns

class TrendClusterer:
    def __init__(self):
        """
        Initialisiert die Clustering-Algorithmen.
        UMAP Parameter sollten für die Diplomarbeit ggf. getuned werden (GridSearch).
        """
        # UMAP reduziert Dimensionen, damit Clustering effizienter ist
        # n_neighbors: Balance zwischen lokaler und globaler Struktur
        # n_components=2 für einfache Visualisierung, im Modell oft besser 5-10
        self.reducer = umap.UMAP(
            n_neighbors=15,
            n_components=2, 
            min_dist=0.1,
            metric='euclidean',
            random_state=42
        )
        
        # HDBSCAN Parameter
        # min_cluster_size: Wie viele Videos brauchst du mind., um es "Trend" zu nennen?
        self.clusterer = hdbscan.HDBSCAN(
            min_cluster_size=3, # Für Testdaten klein, in Prod eher 20+
            min_samples=1,
            metric='euclidean',
            cluster_selection_method='eom' # Excess of Mass
        )

    def reduce_dimensions(self, feature_matrix):
        """
        Reduziert die hochdimensionale Matrix (Text-Embeddings + Metriken)
        auf 2D für Visualisierung und Vor-Verarbeitung.
        """
        print(f"Reduziere Dimensionen von {feature_matrix.shape[1]} auf 2...")
        embedding_2d = self.reducer.fit_transform(feature_matrix)
        return embedding_2d

    def apply_hdbscan(self, feature_matrix_reduced):
        """
        Führt das Density-Based Clustering durch.
        Return: Array mit Cluster-Labels (z.B. [0, 0, 1, -1, 1])
        Label -1 bedeutet 'Noise' (kein Trend).
        """
        print("Starte HDBSCAN Clustering...")
        labels = self.clusterer.fit_predict(feature_matrix_reduced)
        return labels

    def apply_kmeans(self, feature_matrix, k=3):
        """
        Alternativer Ansatz: K-Means (als Baseline für die Diplomarbeit nützlich).
        """
        print(f"Starte K-Means mit k={k}...")
        kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = kmeans.fit_predict(feature_matrix)
        return labels

    def visualize_clusters(self, embedding_2d, labels, titles=None):
        """
        Plottet die Ergebnisse.
        """
        plt.figure(figsize=(10, 8))
        
        # Scatter Plot erstellen
        scatter = plt.scatter(
            embedding_2d[:, 0], 
            embedding_2d[:, 1], 
            c=labels, 
            cmap='Spectral', 
            s=50,
            alpha=0.7
        )
        
        # Legende hinzufügen (ignoriert Rauschen oft in der Auto-Legende, daher manuell)
        plt.colorbar(scatter, label='Cluster ID')
        plt.title('TikTok Trend Cluster (UMAP + HDBSCAN)', fontsize=15)
        plt.xlabel('UMAP Dimension 1')
        plt.ylabel('UMAP Dimension 2')
        
        # Optional: Titel der Videos in den Plot schreiben (nur bei wenigen Daten)
        if titles is not None:
            for i, txt in enumerate(titles):
                plt.annotate(txt, (embedding_2d[i, 0], embedding_2d[i, 1]), fontsize=8)

        plt.show()

# --- Integrationstest (Simuliert den Ablauf) ---
if __name__ == "__main__":
    # 1. Importiere die Pipeline vom vorherigen Schritt
    # Angenommen, der Code von vorhin liegt in 'feature_pipeline.py'
    from feature_pipeline import SocialTrendAnalyzer
    
    # Mockup Daten (Erweitert um unterscheidbare Gruppen)
    data = {
        'video_id': ['v1', 'v2', 'v3', 'v4', 'v5', 'v6'],
        'desc': [
            'Neuer Tanz Trend', 'Tanz Tutorial', # Cluster A: Tanz
            'Aktien News', 'Börse Crash',        # Cluster B: Finanzen
            'Katze spielt', 'Hund bellt'         # Cluster C: Tiere
        ],
        'hashtags': [
            '#dance #viral', '#dance #tutorial',
            '#finance #money', '#stock #market',
            '#cat #cute', '#dog #funny'
        ],
        'play_count': [1000, 1200, 500, 600, 5000, 5100], # Ähnliche Views pro Gruppe
        'digg_count': [100, 120, 50, 60, 500, 510],
        'share_count': [10, 12, 5, 6, 50, 51],
        'comment_count': [5, 6, 2, 3, 20, 21],
        'posted_at': ['2023-10-27 10:00'] * 6,
        'scraped_at': ['2023-10-27 14:00'] * 6
    }
    
    # Datensatz vorbereiten
    raw_df = pd.DataFrame(data)
    analyzer = SocialTrendAnalyzer()
    df_clean = analyzer.load_data_from_db_connector(raw_df)
    df_engineered = analyzer.feature_engineering(df_clean)
    text_embeddings = analyzer.generate_embeddings(df_engineered)
    
    # Die Matrix X aus Schritt 1
    X_train = analyzer.prepare_training_data(df_engineered, text_embeddings)
    
    # --- Neuer Teil: Clustering ---
    cluster_model = TrendClusterer()
    
    # 1. Reduktion auf 2D (Sowohl für Clustering als auch Plotting wichtig)
    X_reduced = cluster_model.reduce_dimensions(X_train)
    
    # 2. HDBSCAN anwenden
    labels = cluster_model.apply_hdbscan(X_reduced)
    
    # Ergebnis zurück in den DataFrame schreiben, um es zu analysieren
    df_clean['cluster_id'] = labels
    
    print("\n--- Analyse Ergebnis ---")
    print(df_clean[['desc', 'cluster_id']])
    
    # 3. Visualisieren
    cluster_model.visualize_clusters(X_reduced, labels, titles=df_clean['desc'].tolist())