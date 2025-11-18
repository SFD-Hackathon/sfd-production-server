# Railway Deployment Guide

Step-by-step guide to deploy the Drama API Server on Railway.

## Prerequisites

- Railway account (sign up at https://railway.com)
- OpenAI API key with GPT-5 access
- Cloudflare R2 bucket and credentials

## Deployment Steps

### Option 1: Deploy from GitHub (Recommended)

1. **Push code to GitHub**
   ```bash
   cd sfd-production-server
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin https://github.com/YOUR_USERNAME/sfd-production-server.git
   git push -u origin main
   ```

2. **Create Railway project**
   - Go to https://railway.com/dashboard
   - Click "New Project"
   - Select "Deploy from GitHub repo"
   - Select your `sfd-production-server` repository
   - Railway will auto-detect Python and start building

3. **Configure environment variables**
   - In Railway dashboard, go to your project
   - Click on "Variables" tab
   - Add the following variables:

   ```
   ENVIRONMENT=production
   OPENAI_API_KEY=sk-proj-...
   GPT_MODEL=gpt-5
   API_KEYS=your-production-key-1,your-production-key-2
   R2_ACCOUNT_ID=your-cloudflare-account-id
   R2_ACCESS_KEY_ID=your-r2-access-key-id
   R2_SECRET_ACCESS_KEY=your-r2-secret-access-key
   R2_BUCKET=sfd-production
   ```

4. **Get your deployment URL**
   - Click "Settings" → "Domains"
   - Railway will auto-generate a domain like `your-app.railway.app`
   - (Optional) Add a custom domain

5. **Test your deployment**
   ```bash
   curl https://your-app.railway.app/health
   ```

### Option 2: Deploy with Railway CLI

1. **Install Railway CLI**
   ```bash
   npm i -g @railway/cli
   ```

2. **Login to Railway**
   ```bash
   railway login
   ```

3. **Initialize project**
   ```bash
   cd sfd-production-server
   railway init
   ```

4. **Set environment variables**
   ```bash
   # OpenAI Configuration
   railway variables set OPENAI_API_KEY=sk-proj-...
   railway variables set GPT_MODEL=gpt-5

   # API Keys
   railway variables set API_KEYS=your-key-1,your-key-2

   # R2 Configuration
   railway variables set R2_ACCOUNT_ID=your-account-id
   railway variables set R2_ACCESS_KEY_ID=your-access-key-id
   railway variables set R2_SECRET_ACCESS_KEY=your-secret-access-key
   railway variables set R2_BUCKET=sfd-production

   # Environment
   railway variables set ENVIRONMENT=production
   ```

5. **Deploy**
   ```bash
   railway up
   ```

6. **Get deployment URL**
   ```bash
   railway domain
   ```

7. **View logs**
   ```bash
   railway logs
   ```

## Setting up Cloudflare R2

### 1. Create R2 Bucket

1. Go to Cloudflare Dashboard → R2
2. Click "Create bucket"
3. Name: `sfd-production`
4. Location: Choose closest to your users
5. Click "Create bucket"

### 2. Generate API Credentials

1. In R2 dashboard, click "Manage R2 API Tokens"
2. Click "Create API token"
3. Token name: `drama-api-production`
4. Permissions:
   - ✅ Object Read & Write
   - Select your bucket or use all buckets
5. Click "Create API Token"
6. **Copy the credentials immediately** (you won't see them again):
   - Access Key ID
   - Secret Access Key
   - Account ID

### 3. Configure Railway with R2 Credentials

Use the credentials from step 2 to set Railway environment variables:

```bash
railway variables set R2_ACCOUNT_ID=<your-account-id>
railway variables set R2_ACCESS_KEY_ID=<your-access-key-id>
railway variables set R2_SECRET_ACCESS_KEY=<your-secret-access-key>
railway variables set R2_BUCKET=sfd-production
```

## Post-Deployment

### 1. Test the API

```bash
# Health check
curl https://your-app.railway.app/health

# Create a drama (no API key needed for development)
curl -X POST https://your-app.railway.app/dramas \
  -H "Content-Type: application/json" \
  -d '{"premise": "A test drama about time travel"}'

# With API key (production)
curl -X POST https://your-app.railway.app/dramas \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-production-key" \
  -d '{"premise": "A test drama about time travel"}'
```

### 2. Access API Documentation

Visit `https://your-app.railway.app/docs` for interactive Swagger documentation.

### 3. Monitor Logs

```bash
railway logs --follow
```

Or view in Railway dashboard → Deployments → View logs

## Environment Variable Reference

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `ENVIRONMENT` | Yes | Environment name | `production` |
| `OPENAI_API_KEY` | Yes | OpenAI API key | `sk-proj-...` |
| `GPT_MODEL` | Yes | GPT model to use | `gpt-5` |
| `API_KEYS` | Optional* | Comma-separated API keys | `key1,key2` |
| `R2_ACCOUNT_ID` | Yes | Cloudflare account ID | `abc123...` |
| `R2_ACCESS_KEY_ID` | Yes | R2 access key | `xyz789...` |
| `R2_SECRET_ACCESS_KEY` | Yes | R2 secret key | `secret...` |
| `R2_BUCKET` | Yes | R2 bucket name | `sfd-production` |
| `OPENAI_API_BASE` | No | Custom OpenAI endpoint | `https://api.openai.com/v1` |
| `PORT` | No | Port (auto-set by Railway) | `8000` |

*Leave `API_KEYS` empty or unset to disable authentication (development only)

## Troubleshooting

### Build Fails

Check Railway build logs:
```bash
railway logs --deployment
```

Common issues:
- Python version mismatch → Check `runtime.txt`
- Missing dependencies → Check `requirements.txt`

### R2 Connection Errors

Test R2 credentials locally:
```python
import boto3
s3 = boto3.client(
    's3',
    endpoint_url=f'https://{ACCOUNT_ID}.r2.cloudflarestorage.com',
    aws_access_key_id=ACCESS_KEY,
    aws_secret_access_key=SECRET_KEY,
    region_name='auto'
)
s3.list_buckets()
```

### OpenAI API Errors

Verify GPT-5 access:
```bash
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY" | grep gpt-5
```

### Application Crashes

Check Railway logs for error messages:
```bash
railway logs --follow
```

Enable debug logging by adding:
```bash
railway variables set LOG_LEVEL=DEBUG
```

## Scaling

Railway auto-scales based on traffic. For custom scaling:

1. Go to Railway dashboard → Settings
2. Adjust "Resources" settings:
   - Memory: 512MB - 8GB
   - vCPU: 1-8 cores
3. Enable "Horizontal Scaling" for high traffic

## Cost Optimization

### Railway
- Hobby plan: $5/month
- Pro plan: $20/month + usage
- Monitor usage in dashboard

### Cloudflare R2
- Storage: $0.015/GB/month
- Class A operations: $4.50/million
- Class B operations: $0.36/million
- Free tier: 10GB storage, 1M Class A, 10M Class B per month

### OpenAI
- GPT-5: Check current pricing at https://openai.com/pricing
- Monitor usage at https://platform.openai.com/usage

## Custom Domain

1. Go to Railway dashboard → Settings → Domains
2. Click "Add Domain"
3. Enter your custom domain: `api.yourdomain.com`
4. Add DNS records as shown by Railway:
   - Type: CNAME
   - Name: api
   - Value: your-app.railway.app
5. Wait for DNS propagation (5-30 minutes)

## Security Checklist

- ✅ Set strong `API_KEYS` in production
- ✅ Use HTTPS only (Railway provides this automatically)
- ✅ Rotate R2 credentials periodically
- ✅ Monitor OpenAI API usage
- ✅ Enable Railway's WAF features
- ✅ Set up uptime monitoring

## Support

- Railway Support: https://railway.com/help
- Cloudflare R2 Docs: https://developers.cloudflare.com/r2/
- OpenAI API Docs: https://platform.openai.com/docs
