# syntax=docker/dockerfile:1
# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies for WeasyPrint
# Update package lists, install libraries (-y confirms, --no-install-recommends avoids extra packages), then clean up
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libglib2.0-0 \
    shared-mime-info \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy only the requirements file first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --trusted-host pypi.python.org -r requirements.txt

# Copy the rest of the application code into the container
# This includes app.py, models.py, config.py, templates/, static/, etc.
# Ensure .dockerignore is set up correctly to exclude venv, .git, instance, .env etc.
COPY . .

# Make port 5000 available to services outside this container
EXPOSE 5000

# Define environment variables (can be overridden by docker-compose)
ENV FLASK_APP=app.py
ENV FLASK_RUN_HOST=0.0.0.0
# Default to non-debug mode in container (Set FLASK_DEBUG=1 in compose for dev)
ENV FLASK_DEBUG=0
# Command to run the application when the container launches
# Uses Flask's built-in server. For production, switch to Gunicorn.
# Example Gunicorn command (install gunicorn via requirements.txt first):
# CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]
CMD ["flask", "run"]
