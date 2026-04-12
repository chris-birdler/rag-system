FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/

# Mount-Punkte für Named-Volumes vorwegnehmen.
# Wenn /app/.chroma und /app/data im Image bereits existieren und app:app
# gehören, übernimmt Docker bei einem frischen Named-Volume den Ownership
# beim ersten Mount. Sonst wäre /app/.chroma nach einem `docker volume rm`
# + `up` wieder root:root und der nicht-root Container könnte nicht schreiben.
RUN mkdir -p data/pdfs .chroma

# Nicht als root laufen – falls der Container ausgebrochen wird,
# hat der Angreifer keine root-Rechte.
# UID/GID sind fest auf 10001 gesetzt, damit Host-Bind-Mounts reproduzierbar
# gechownt werden können (sudo chown -R 10001:10001 ./data).
RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --home /app app \
    && chown -R app:app /app
USER app

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
