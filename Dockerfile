FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/

# data Ordner erstellen aber keine PDFs kopieren
# PDFs werden über Upload hinzugefügt
RUN mkdir -p data/pdfs

# Nicht als root laufen – falls der Container ausgebrochen wird,
# hat der Angreifer keine root-Rechte.
RUN groupadd --system app && useradd --system --gid app --home /app app \
    && chown -R app:app /app
USER app

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
