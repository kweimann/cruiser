FROM python:3.7.3

RUN apt-get update && apt-get install -y libasound2-dev

COPY requirements.txt /tmp/

RUN pip install -r /tmp/requirements.txt

COPY . /app/cruiser

WORKDIR /app/cruiser

ENTRYPOINT ["python", "start_bot.py"]