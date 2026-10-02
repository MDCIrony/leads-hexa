# Its own image on purpose: this app is the customer's side of the contract,
# and building it from the product's image would hide a dependency on the
# product that the contract says does not exist.
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py api_client.py ./
COPY static/ ./static/

# The inbox is a volume, not part of the image: what this office has written on
# a lead has to survive a rebuild.
VOLUME /data
ENV INBOX_DB=/data/inbox.db

EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
