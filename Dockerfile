# Python 3.12 als Basis
FROM python:3.12-slim

# Arbeitsverzeichnis
WORKDIR /app

# Dependencies zuerst installieren
# (eigene Schicht → wird gecacht wenn sich Code ändert)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Code kopieren
COPY backend/ ./backend/
COPY data/ ./data/

# Port freigeben
EXPOSE 8000

# Server starten
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
