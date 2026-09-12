BASTION FORGE STREAM HUB — RAILWAY BACKEND PACK

SERVICES
1. streamhub-auth        -> auth_gateway
2. streamhub-beta        -> beta_backend
3. streamhub-kick-bridge -> bridge

IMPORTANT
- Stream Hub video does NOT pass through Railway.
- Railway handles OAuth/login, updates/feedback and Kick webhook/chat bridging.
- Twitch/YouTube/Kick/TikTok video is sent directly from the user's PC to each platform.
- Keep the auth gateway and Kick bridge at ONE replica with serverless/sleep disabled,
  because current Beta 6 auth sessions and bridge clients are stored in memory.

WINDOWS CLI SETUP
Install Railway CLI:
  npm i -g @railway/cli

Login:
  railway login

From this folder:
  railway init --name "Bastion Forge Stream Hub"

Create services:
  railway add --service streamhub-auth
  railway add --service streamhub-beta
  railway add --service streamhub-kick-bridge

Deploy:
  railway up .\auth_gateway --service streamhub-auth
  railway up .\beta_backend --service streamhub-beta
  railway up .\bridge --service streamhub-kick-bridge

Generate public domains:
  railway domain --service streamhub-auth
  railway domain --service streamhub-beta
  railway domain --service streamhub-kick-bridge

Then add the variables from each RAILWAY_VARIABLES.example file in Railway's
Variables tab. Set PUBLIC_BASE_URL to the actual generated HTTPS URL for that service.

HEALTHCHECKS
Set Healthcheck Path = /health on all three services.

BETA BACKEND VOLUME
Attach a Railway Volume to streamhub-beta:
  Mount path: /data
and set:
  BASTION_DATA_DIR=/data

OAUTH CALLBACKS
Replace AUTH_DOMAIN below with the actual streamhub-auth Railway domain:

Twitch:
  https://AUTH_DOMAIN/oauth/twitch/callback

Google/YouTube:
  https://AUTH_DOMAIN/oauth/youtube/callback

Kick:
  https://AUTH_DOMAIN/oauth/kick/callback

Streamlabs:
  https://AUTH_DOMAIN/oauth/streamlabs/callback

After creating the provider apps, put their Client IDs and Client Secrets into
the streamhub-auth Railway service variables.

STREAM HUB WINDOWS BUILD
Copy STREAM_HUB_BUILD_CONFIG.example.json to:
  config\bastion_build_config.json

Replace the Railway URLs with your real Railway service domains, then rebuild:
  .\BUILD_BETA_INSTALLER.bat

CURRENT BETA 6 LIMITATION
Account login and video-output credentials are separate:
- Twitch: login handles chat/stats; Beta 6 still asks for a stream key.
- YouTube: login handles chat/stats; Beta 6 still asks for a stream key.
- Kick: login handles chat/stats; paste the RTMPS server/key from Kick Creator Dashboard.
- TikTok: Beta 6 uses TikTok LIVE server/key manually when encoder access is enabled.
A later client update can automate Twitch stream-key retrieval and YouTube live-stream creation.
