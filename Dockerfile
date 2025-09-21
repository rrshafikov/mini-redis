FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
COPY redis_tcp /app/redis_tcp
COPY README.md /app/README.md
ENV HOST=0.0.0.0
ENV PORT=6380
EXPOSE 6380
CMD ["python", "-m", "redis_tcp.server"]
