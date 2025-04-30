#!/bin/bash

# Build the Docker image
echo "Building Docker image..."
docker build -t datahub-glossary-manager:latest .

# Check if data directory exists, create if not
if [ ! -d "./data" ]; then
  mkdir -p ./data
  echo "Created data directory"
fi

# Check if example.csv exists in data directory, copy if not
if [ ! -f "./data/glossary.csv" ]; then
  cp example.csv ./data/glossary.csv
  echo "Copied example.csv to data/glossary.csv"
fi

# Check if DATAHUB_GMS_URL and DATAHUB_TOKEN are set
if [ -z "$DATAHUB_GMS_URL" ] || [ -z "$DATAHUB_TOKEN" ]; then
  echo "Warning: DATAHUB_GMS_URL and/or DATAHUB_TOKEN environment variables are not set."
  echo "You can set them using:"
  echo "export DATAHUB_GMS_URL=http://your-datahub-instance:8080"
  echo "export DATAHUB_TOKEN=your-token-here"

  # Check if ~/.datahub exists
  if [ ! -f ~/.datahub ]; then
    echo "~/.datahub configuration file not found either."
    echo "Please set up your DataHub credentials before running."
    exit 1
  else
    echo "Using credentials from ~/.datahub file."
  fi
fi

# Run the Docker container
echo "Running DataHub Glossary Manager..."
docker run --rm \
  -v $(pwd)/data:/data \
  -v ${HOME}/.datahub:/root/.datahub \
  -e DATAHUB_GMS_URL=${DATAHUB_GMS_URL} \
  -e DATAHUB_TOKEN=${DATAHUB_TOKEN} \
  datahub-glossary-manager:latest

echo "Done!"