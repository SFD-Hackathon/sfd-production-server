# Railway Environment Variables Setup

Set these environment variables in your Railway project dashboard:

## Required Variables

```bash
ENVIRONMENT=production
GPT_MODEL=gpt-5
R2_BUCKET=sfd-production
```

## Sensitive Variables (Set in Railway Dashboard)

Go to your Railway project → Variables tab and add:

1. **OPENAI_API_KEY**
   - Get from your OpenAI account
   - Format: `sk-proj-...`

2. **R2_ACCOUNT_ID**
   - Get from Cloudflare R2 dashboard
   - Your account ID

3. **R2_ACCESS_KEY_ID**
   - Generated from Cloudflare R2 API tokens
   - Your R2 access key ID

4. **R2_SECRET_ACCESS_KEY**
   - Generated from Cloudflare R2 API tokens
   - Your R2 secret access key

## Quick Setup via Railway CLI

If you have the Railway CLI installed:

```bash
# Set public variables
railway variables set ENVIRONMENT=production
railway variables set GPT_MODEL=gpt-5
railway variables set R2_BUCKET=sfd-production

# Set sensitive variables (replace with your actual values)
railway variables set OPENAI_API_KEY=<your-openai-key>
railway variables set R2_ACCOUNT_ID=<your-r2-account-id>
railway variables set R2_ACCESS_KEY_ID=<your-r2-access-key>
railway variables set R2_SECRET_ACCESS_KEY=<your-r2-secret-key>
```

## Verify

After setting variables, redeploy your application:

```bash
railway up
```

Check the logs:

```bash
railway logs
```

You should see:
```
🚀 Drama API Server v1.0.0 starting...
📦 R2 Bucket: sfd-production
🤖 GPT Model: gpt-5
```
