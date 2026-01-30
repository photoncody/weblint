FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

COPY . .

# Create directory for data mount
RUN mkdir /data

EXPOSE 5000

# Use Gunicorn for production-grade server
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app:app"]