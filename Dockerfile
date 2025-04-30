FROM python:3.10-slim

WORKDIR /app

# Copy requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY datahub_glossary_manager.py .
COPY example.csv .
COPY README.md .

# Create directory for configuration
RUN mkdir -p /root/.datahub

# Create volume mount points
VOLUME ["/data", "/root/.datahub"]

# Set environment variables (can be overridden at runtime)
ENV DATAHUB_GMS_URL=""
ENV DATAHUB_TOKEN=""
ENV CSV_FILE="/data/glossary.csv"

# Command to run when container starts
ENTRYPOINT ["python", "datahub_glossary_manager.py"]
CMD ["--csv-file", "/data/glossary.csv"]