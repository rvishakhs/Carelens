FROM python:3.12-slim
WORKDIR /service
COPY requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir --no-deps . && useradd --uid 10001 --create-home intelligence
USER 10001
EXPOSE 8100
CMD ["uvicorn", "intelligence.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8100", "--no-access-log"]
