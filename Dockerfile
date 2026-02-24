FROM python:3.11-slim

WORKDIR /app

# Copy minimal requirements
COPY requirements-deploy.txt requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy only necessary files
COPY app.py .
COPY web_app/ web_app/

# Set environment variables
ENV FLASK_APP=app.py
ENV FLASK_ENV=production
ENV PYTHONPATH=/app

# Expose port (Render uses $PORT)
EXPOSE 5000

# Start application with explicit command
ENTRYPOINT ["gunicorn", "app:app", "--bind", "0.0.0.0:$PORT", "--workers", "2", "--timeout", "120"]
