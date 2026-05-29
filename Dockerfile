FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY menu_bot.py .

CMD ["python", "menu_bot.py"]
