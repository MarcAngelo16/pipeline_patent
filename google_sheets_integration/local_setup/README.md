# OAuth Token Setup - Run on Your Local Laptop

This folder contains scripts to generate OAuth tokens on your **LOCAL MACHINE** (not in Docker).

## 📁 Files You Need

1. **oauth_client_secret.json** - Download from Google Cloud Console
2. **generate_oauth_token.py** - This script (already here)

## 🚀 Step-by-Step Instructions

### Step 1: Download oauth_client_secret.json

1. Go to: https://console.cloud.google.com/apis/credentials
2. Select project: **patent-pipeline-475109**
3. Find your **OAuth 2.0 Client ID**
4. Click the **download button** (⬇) on the right
5. Save as: `oauth_client_secret.json`
6. Put it in **THIS folder** (local_setup/)

**Your oauth_client_secret.json should look like:**
```json
{
  "installed": {
    "client_id": "449125622211-...",
    "client_secret": "GOCSPX-...",
    "redirect_uris": ["http://localhost"]
  }
}
```

### Step 2: Copy Files to Your Laptop

Copy these files to your laptop:
```bash
# On your laptop, create a folder
mkdir ~/patent-oauth-setup
cd ~/patent-oauth-setup

# Copy from container
docker cp patent-pipeline:/app/patent_pipeline/google_sheets_integration/local_setup/generate_oauth_token.py .

# Put your oauth_client_secret.json here too
# Now you should have:
# - generate_oauth_token.py
# - oauth_client_secret.json
```

### Step 3: Install Dependencies (if needed)

```bash
pip install google-auth google-auth-oauthlib google-auth-httplib2
```

### Step 4: Run the Script

```bash
python3 generate_oauth_token.py
```

**What happens:**
- Browser opens automatically
- Log in with your **personal email**
- Approve permissions
- Script generates `oauth_token.json`

### Step 5: Copy Token to Container

```bash
# From your laptop
docker cp oauth_token.json patent-pipeline:/app/patent_pipeline/google_sheets_integration/

# Verify it's there
docker exec patent-pipeline ls -la /app/patent_pipeline/google_sheets_integration/oauth_token.json
```

## ✅ Done!

Your container now has OAuth credentials and can create Google Sheets!

## 🔧 Troubleshooting

**Browser says "Site can't be reached"?**
- Make sure the script is RUNNING when you approve in browser
- Don't close the terminal

**"Port 8080 busy"?**
- Script will automatically try 8081, 8082, or random port

**Token expires?**
- If your app is in "Production" mode: token never expires (auto-refreshes)
- If in "Testing" mode: expires in 7 days

## 📞 Need Help?

Check if your app is published:
https://console.cloud.google.com/apis/credentials/consent

Should show: **"In production"** ✅
