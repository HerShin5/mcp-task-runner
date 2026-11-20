FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY pyproject.toml README.md README.en.md LICENSE ./
COPY mcp_task_runner ./mcp_task_runner
COPY examples ./examples
COPY model_profiles.example.json providers.example.json ./

RUN python -m pip install --no-cache-dir --upgrade pip pytest

EXPOSE 8767
CMD ["python", "-c", "from mcp_task_runner.api import serve; serve(host='0.0.0.0', port=8767)"]
