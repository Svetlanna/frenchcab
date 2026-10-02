FROM python:3.14-slim
WORKDIR /app/ML
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "api_prediction:app", "--host", "0.0.0.0", "--port", "8000"]