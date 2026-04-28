FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY agent.py .
COPY api.py .
COPY LG-Agent.py .
COPY agent_helpers.py .

EXPOSE 3001

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "3001"]
