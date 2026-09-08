FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=8000
ENV HR_DATABASE_URL=sqlite:///data/hr.sqlite3

RUN mkdir -p data

EXPOSE 8000
ENV PYTHONPATH=/app/mcp_servers/hr_server
CMD ["uvicorn", "mcp_servers.hr_server.remote_server:app", "--host", "0.0.0.0", "--port", "8000"]
