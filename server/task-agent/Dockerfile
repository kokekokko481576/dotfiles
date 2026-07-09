FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

RUN mkdir -p /app/data

WORKDIR /app/src

# docker-compose.ymlのtask-agent-recommend/task-agent-collectがそれぞれ
# command: で job_recommend.py / job_collect.py を指定して同一イメージを共用する。
CMD ["python", "-u", "job_recommend.py"]
