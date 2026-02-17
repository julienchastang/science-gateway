FROM python:3.11-slim

WORKDIR /srv/nblaunch

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py ./

USER 1000:100

CMD ["python", "/srv/nblaunch/app.py"]
