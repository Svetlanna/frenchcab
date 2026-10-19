FROM python:3.14-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

WORKDIR /app/ML

EXPOSE 3001

CMD ["uvicorn", "api_prediction:app", "--host", "0.0.0.0", "--port", "3001"]