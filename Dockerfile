FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt pyproject.toml ./
COPY src ./src
RUN pip install -r requirements.txt && pip install -e .
COPY web ./web
EXPOSE 8000
CMD ["uvicorn", "healthvalue.api:app", "--host", "0.0.0.0", "--port", "8000"]
