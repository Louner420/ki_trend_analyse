from main import run_analysis_pipeline
import sys
import os

# Füge Projektpfad hinzu (zur Sicherheit)
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    print("Starte manuelle KI-Analyse über Pipeline...")
    try:
        run_analysis_pipeline()
    except Exception as e:
        print(f"KRITISCHER FEHLER: {e}")
        sys.exit(1)
