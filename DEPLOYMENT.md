# DataHub Glossary Manager Deployment Guide

This guide explains how to deploy the DataHub Glossary Manager using either Docker or Kubernetes.

## Docker Deployment

### Prerequisites
- Docker installed on your machine
- Access to a DataHub instance
- DataHub API token

### Build and Run with Docker

1. **Clone the repository**

```bash
git clone https://github.com/yourusername/datahub-glossary-manager.git
cd datahub-glossary-manager
```

2. **Build the Docker image**

```bash
docker build -t datahub-glossary-manager:latest .
```

3. **Prepare data directory**

```bash
mkdir -p data
cp example.csv data/glossary.csv
# Edit data/glossary.csv with your glossary terms
```

4. **Run the container**

```bash
docker run --rm \
  -v $(pwd)/data:/data \
  -v ${HOME}/.datahub:/root/.datahub \
  -e DATAHUB_GMS_URL=http://your-datahub-instance:8080 \
  -e DATAHUB_TOKEN=your-token-here \
  datahub-glossary-manager:latest
```

### Using Docker Compose

1. **Create environment variables**

```bash
export DATAHUB_GMS_URL=http://your-datahub-instance:8080
export DATAHUB_TOKEN=your-token-here
```

2. **Run with Docker Compose**

```bash
docker-compose up
```

### Using the Convenience Script

We've provided a convenience script that handles building and running:

```bash
chmod +x docker-build-run.sh
./docker-build-run.sh
```

## Kubernetes Deployment

### Prerequisites
- Kubernetes cluster
- kubectl configured to access your cluster
- Container registry where you can push your image

### Deployment Steps

1. **Build and push the Docker image**

```bash
docker build -t your-registry/datahub-glossary-manager:latest .
docker push your-registry/datahub-glossary-manager:latest
```

2. **Update image name in Kubernetes files**

Edit the `k8s-deployment.yaml` file to use your image name:

```yaml
image: your-registry/datahub-glossary-manager:latest
```

3. **Update the DataHub token**

Encode your DataHub token in base64:

```bash
echo -n "your-datahub-token" | base64
```

Then update the `DATAHUB_TOKEN` field in the Secret section of the `k8s-deployment.yaml` file with this value.

4. **Update the DataHub GMS URL**

Update the `DATAHUB_GMS_URL` field in the ConfigMap section to point to your DataHub GMS service.

5. **Deploy to Kubernetes**

```bash
kubectl apply -f k8s-deployment.yaml
```

6. **Upload your CSV file**

```bash
# Create a temporary pod to access the PVC
kubectl run temp-pod --image=busybox -n datahub-tools --rm -i --tty -- sh

# Inside the pod
cp /data
# Press Ctrl+D to exit

# Copy your file to the PVC
kubectl cp glossary.csv temp-pod:/data/glossary.csv -n datahub-tools

# Delete the temporary pod
kubectl delete pod temp-pod -n datahub-tools
```

7. **Run the job manually (optional)**

```bash
kubectl create job --from=cronjob/datahub-glossary-manager-cronjob manual-run -n datahub-tools
```

8. **Check logs**

```bash
# Get the pod name
kubectl get pods -n datahub-tools

# Check logs
kubectl logs pod-name -n datahub-tools
```

## Configuration Options

### Environment Variables

- `DATAHUB_GMS_URL`: URL of your DataHub GMS instance
- `DATAHUB_TOKEN`: API token for DataHub
- `CSV_FILE`: Path to the CSV file containing glossary terms (default: `/data/glossary.csv`)

### Volume Mounts

- `/data`: Mount point for your CSV files
- `/root/.datahub`: Mount point for DataHub configuration file (optional)

## Customizing the Schedule

The CronJob is set to run daily at midnight (`0 0 * * *`). To change this schedule, edit the `schedule` field in the CronJob section of the `k8s-deployment.yaml` file.

## Troubleshooting

### Common Issues

1. **Authentication Error**: Make sure your DataHub token is valid and has the correct permissions.

2. **Volume Mount Issues**: Ensure the paths to your CSV file and DataHub configuration are correct.

3. **CSV Format**: Verify your CSV file follows the expected format as described in the README.

4. **Kubernetes Namespace**: Make sure you're operating in the correct namespace (`datahub-tools`).