# GitHub App Setup Guide

This guide walks you through setting up a GitHub App for Makapix's content publishing flow.

## Prerequisites

- GitHub account
- Admin access to the repository where you want to publish content
- Environment variables already configured (see `.env` file)

## Step 1: Create GitHub App

1. **Go to GitHub Settings**
   - Visit: https://github.com/settings/apps
   - Click "New GitHub App"

2. **Configure Basic Information**
   - **GitHub App name**: `Makapix` (or your preferred name)
   - **Homepage URL**: `http://localhost:3000`
   - **User authorization callback URL**: `http://localhost/auth/github/callback`
   - **Setup URL**: `http://localhost/github-app-setup`
   - **Webhook URL**: Leave blank for now
   - **Webhook secret**: Leave blank for now

3. **Set Permissions**
   - **Repository permissions**:
     - `Contents`: Read and write
     - `Metadata`: Read
     - `Administration`: Read and write (required to make repository public)
     - `Pages`: Read and write (required to enable GitHub Pages)
     - `Pull requests`: Read (optional)
   - **Account permissions**:
     - `Email addresses`: Read (optional)
   - **Organization permissions** (if applicable):
     - `Members`: Read (optional)

4. **Configure Installation**
   - **Where can this GitHub App be installed?**: Any account
   - **Request user authorization (OAuth) during installation**: ✅ Check this

5. **Click "Create GitHub App"**

## Step 2: Generate Private Key

1. **After creating the app**, scroll down to "Private keys"
2. **Click "Generate a private key"**
3. **Download the `.pem` file** and save it securely
4. **Copy the entire contents** of the `.pem` file (including `-----BEGIN RSA PRIVATE KEY-----` and `-----END RSA PRIVATE KEY-----`)

## Step 3: Update Environment Variables

Add these to your `.env` file:

```bash
# GitHub App Configuration
GITHUB_APP_ID=your_app_id_here
GITHUB_APP_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----
your_private_key_content_here
-----END RSA PRIVATE KEY-----"
GITHUB_APP_SLUG=your-app-slug-here
```

**Important**: The private key must be on multiple lines with proper formatting.

### Understanding GitHub App URLs

- **Callback URL** (`/auth/github/callback`): Used for OAuth authentication flow
- **Setup URL** (`/github-app-setup`): Used when users complete GitHub App installation
- **Homepage URL**: Your main application URL

The Setup URL is crucial for capturing the installation ID when users install your GitHub App.

## Step 4: Install the App

1. **Go to your GitHub App settings**
2. **Click "Install App"** in the left sidebar
3. **Select your account** (or organization)
4. **Click "Install"**
5. **Grant the requested permissions**

## Step 5: Enable GitHub Pages (One-Time Setup)

Since GitHub Apps cannot programmatically enable GitHub Pages, you need to enable it manually once:

1. **Go to your repository**: `https://github.com/YOUR_USERNAME/makapix-user`
2. **Click "Settings"** tab
3. **Click "Pages"** in the left sidebar
4. **Under "Source"**, select:
   - **Branch**: `main`
   - **Folder**: `/ (root)`
5. **Click "Save"**
6. **Wait 1-2 minutes** for the initial deployment

Once enabled, GitHub Pages will automatically update whenever new commits are pushed to the repository.

## Step 6: Test the Installation

1. **Restart the API container** to load the new environment variables:
   ```bash
   docker compose restart api
   ```

2. **Go to `http://localhost:3000/publish`**
3. **Try uploading an artwork** - you should now get past the "GitHub App not installed" error

## Troubleshooting

### Common Issues

1. **"Invalid private key format"**
   - Ensure the private key is properly formatted with line breaks
   - Include the `-----BEGIN RSA PRIVATE KEY-----` and `-----END RSA PRIVATE KEY-----` lines

2. **"App not found"**
   - Verify the `GITHUB_APP_ID` is correct
   - Check that the app is installed on your account

3. **"Insufficient permissions"**
   - Ensure the app has `Contents: write` and `Metadata: read` permissions
   - Reinstall the app if you changed permissions

### Getting the App ID

The App ID can be found in your GitHub App settings under "About" section.

## Next Steps

After successful installation, you can:
1. Upload artwork through the publish page
2. Configure your target repository
3. Publish content to GitHub Pages

The complete flow will:
1. Validate your uploaded bundle
2. Create a relay job
3. Commit files to your GitHub repository
4. Create post records in the database
5. Make your artwork available on GitHub Pages