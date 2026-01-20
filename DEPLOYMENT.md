# Rahti Deployment Guide

This guide will help you deploy the AI Consultancy Report Writing Tool to Rahti (OpenShift) through GitHub.

## Files Created

All necessary deployment files have been created:

### Docker Configuration
- ✅ `fullstack-app/backend/Dockerfile` - Backend container configuration
- ✅ `fullstack-app/frontend/Dockerfile` - Frontend container configuration
- ✅ `fullstack-app/frontend/nginx.conf` - Nginx web server configuration

### OpenShift Configuration
- ✅ `.openshift/deployment.yaml` - Deployment, services, and routes
- ✅ `.openshift/buildconfig.yaml` - Build configurations and image streams

### Application Configuration
- ✅ `fullstack-app/frontend/.env.production` - Production environment variables
- ✅ `fullstack-app/frontend/src/App.jsx` - Updated with dynamic API URL

### CI/CD
- ✅ `.github/workflows/deploy-rahti.yml` - Automated deployment workflow

## Prerequisites

1. **Rahti Account**: Access to https://rahti.csc.fi
2. **GitHub Account**: Repository with your code
3. **OpenShift CLI**: Download from https://mirror.openshift.com/pub/openshift-v4/clients/ocp/

## Deployment Steps

### Step 1: Update Configuration Files

#### 1.1 Update BuildConfig with your GitHub repository

Edit `.openshift/buildconfig.yaml` and replace:
- `YOUR_USERNAME` with your GitHub username
- `YOUR_REPO` with your repository name

```yaml
uri: https://github.com/YOUR_USERNAME/YOUR_REPO.git
```

#### 1.2 Update Deployment with your project name

Edit `.openshift/deployment.yaml` and replace `YOUR_PROJECT` with your Rahti project name in both image references:
```yaml
image: image-registry.openshift-image-registry.svc:5000/YOUR_PROJECT/report-backend:latest
image: image-registry.openshift-image-registry.svc:5000/YOUR_PROJECT/report-frontend:latest
```

#### 1.3 Generate webhook secret

Edit `.openshift/buildconfig.yaml` and replace `CHANGE_THIS_TO_RANDOM_STRING` with a random string:
```bash
# Generate a random secret (Linux/Mac)
openssl rand -hex 20

# Or use Python
python -c "import secrets; print(secrets.token_hex(20))"
```

### Step 2: Login to Rahti

```bash
# Get your login token from https://rahti.csc.fi
oc login https://api.2.rahti.csc.fi:6443 --token=YOUR_TOKEN
```

### Step 3: Create Project (if not exists)

```bash
oc new-project your-project-name
```

Or select existing project:
```bash
oc project your-project-name
```

### Step 4: Create API Secrets

Create secrets for your API keys:

```bash
oc create secret generic api-secrets \
  --from-literal=azure-api-key=YOUR_AZURE_API_KEY \
  --from-literal=azure-endpoint=YOUR_AZURE_ENDPOINT \
  --from-literal=openai-api-key=YOUR_OPENAI_API_KEY
```

### Step 5: Deploy to Rahti

#### 5.1 Apply BuildConfig

```bash
oc apply -f .openshift/buildconfig.yaml
```

This creates:
- BuildConfigs for backend and frontend
- ImageStreams for storing built images
- GitHub webhook secret

#### 5.2 Apply Deployment

```bash
oc apply -f .openshift/deployment.yaml
```

This creates:
- Deployments for backend and frontend
- Services for internal communication
- Route for external access (HTTPS)

#### 5.3 Start Initial Builds

```bash
# Start backend build
oc start-build report-backend --follow

# Start frontend build (in a new terminal or after backend completes)
oc start-build report-frontend --follow
```

### Step 6: Set Up GitHub Webhooks

#### 6.1 Get Webhook URLs

```bash
# Backend webhook URL
oc describe bc report-backend | grep -A 1 "Webhook GitHub"

# Frontend webhook URL
oc describe bc report-frontend | grep -A 1 "Webhook GitHub"
```

#### 6.2 Add Webhooks to GitHub

1. Go to your GitHub repository
2. Navigate to **Settings** → **Webhooks** → **Add webhook**
3. Paste the webhook URL
4. Set **Content type** to `application/json`
5. Set **Secret** to the value you used in `buildconfig.yaml`
6. Select **Just the push event**
7. Click **Add webhook**
8. Repeat for the second webhook URL

### Step 7: Verify Deployment

#### 7.1 Check Build Status

```bash
# Watch builds
oc get builds -w

# View build logs
oc logs -f bc/report-backend
oc logs -f bc/report-frontend
```

#### 7.2 Check Deployments

```bash
# Check deployment status
oc get deployments

# Check pods
oc get pods

# View pod logs
oc logs -f deployment/report-backend
oc logs -f deployment/report-frontend
```

#### 7.3 Get Application URL

```bash
# Get the public URL
oc get route report-writing

# Or open in browser directly
oc get route report-writing -o jsonpath='{.spec.host}' | xargs -I {} open https://{}
```

Your application should be accessible at: `https://report-writing-YOUR_PROJECT.2.rahti.csc.fi`

## Step 8: Set Up GitHub Actions (Optional)

To enable automated deployments on every push:

### 8.1 Get Rahti API Token

1. Login to Rahti web console: https://rahti.csc.fi
2. Click your username in top right → **Copy login command**
3. Click **Display Token**
4. Copy the token value

### 8.2 Add Secrets to GitHub

1. Go to your GitHub repository
2. Navigate to **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Add two secrets:
   - Name: `OPENSHIFT_TOKEN`, Value: Your Rahti token
   - Name: `OPENSHIFT_PROJECT`, Value: Your Rahti project name

### 8.3 Test GitHub Actions

Push a commit to the `main` branch, and the workflow will automatically deploy to Rahti.

## Monitoring and Maintenance

### View Logs

```bash
# Backend logs
oc logs -f deployment/report-backend

# Frontend logs
oc logs -f deployment/report-frontend

# All logs
oc logs -f --selector app=report-writing-backend
```

### Scale Application

```bash
# Scale backend to 2 replicas
oc scale deployment/report-backend --replicas=2

# Scale frontend to 3 replicas
oc scale deployment/report-frontend --replicas=3
```

### Update Secrets

```bash
# Delete old secret
oc delete secret api-secrets

# Create new secret
oc create secret generic api-secrets \
  --from-literal=azure-api-key=NEW_KEY \
  --from-literal=azure-endpoint=NEW_ENDPOINT \
  --from-literal=openai-api-key=NEW_KEY

# Restart deployments to pick up new secrets
oc rollout restart deployment/report-backend
```

### Manual Rebuild

```bash
# Rebuild backend
oc start-build report-backend --follow

# Rebuild frontend
oc start-build report-frontend --follow
```

### Delete Deployment

```bash
# Delete everything
oc delete -f .openshift/deployment.yaml
oc delete -f .openshift/buildconfig.yaml
oc delete secret api-secrets
```

## Troubleshooting

### Build Failures

```bash
# Check build logs
oc logs -f bc/report-backend

# Common issues:
# - Missing dependencies in requirements.txt
# - Docker build errors
# - GitHub access issues
```

### Deployment Failures

```bash
# Check pod status
oc get pods
oc describe pod POD_NAME

# Check events
oc get events --sort-by='.lastTimestamp'

# Common issues:
# - Missing secrets
# - Resource limits exceeded
# - Image pull errors
```

### Application Not Accessible

```bash
# Check route
oc get route report-writing

# Check services
oc get svc

# Check if backend is responding
oc port-forward deployment/report-backend 8000:8000
# Then visit http://localhost:8000

# Common issues:
# - Route not created
# - Backend service not running
# - Nginx misconfiguration
```

### Backend Cannot Connect to APIs

```bash
# Check if secrets are loaded
oc get secret api-secrets -o yaml

# Check environment variables in pod
oc exec deployment/report-backend -- env | grep API

# Common issues:
# - Secrets not created
# - Secret keys don't match environment variables
# - Invalid API keys
```

## Resource Requirements

### Current Configuration

**Backend:**
- CPU: 250m (request) / 1000m (limit)
- Memory: 512Mi (request) / 2Gi (limit)

**Frontend:**
- CPU: 100m (request) / 200m (limit)
- Memory: 128Mi (request) / 256Mi (limit)

### Adjust Resources

Edit `.openshift/deployment.yaml` and modify the `resources` section:

```yaml
resources:
  limits:
    memory: "4Gi"    # Increase if needed
    cpu: "2000m"
  requests:
    memory: "1Gi"
    cpu: "500m"
```

Then apply:
```bash
oc apply -f .openshift/deployment.yaml
```

## Security Considerations

1. **Never commit secrets** to the repository
2. **Use strong webhook secrets** (20+ characters)
3. **Regularly rotate API keys**
4. **Use TLS/HTTPS** (enabled by default via Route)
5. **Limit GitHub webhook to specific events** (push only)
6. **Review resource quotas** to prevent resource exhaustion

## Support

For Rahti-specific issues:
- Documentation: https://docs.csc.fi/cloud/rahti/
- Support: servicedesk@csc.fi

For application issues:
- Check logs: `oc logs -f deployment/report-backend`
- Check events: `oc get events`
- Review this guide's troubleshooting section
