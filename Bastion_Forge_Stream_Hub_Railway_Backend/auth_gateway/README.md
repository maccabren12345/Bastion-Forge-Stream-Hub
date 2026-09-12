# Bastion Forge Auth Gateway

This is what removes all Client ID / Client Secret boxes from Stream Hub.

Bastion Forge configures the four provider applications once on this server.
Every Stream Hub user then gets ordinary **Log in with ...** buttons.

## Provider callback URLs

If your public gateway is:

`https://auth.example.com`

register these callback URLs:

- Twitch: `https://auth.example.com/oauth/twitch/callback`
- Google/YouTube: `https://auth.example.com/oauth/youtube/callback`
- Kick: `https://auth.example.com/oauth/kick/callback`
- Streamlabs: `https://auth.example.com/oauth/streamlabs/callback`

## Setup

1. Run `INSTALL_WINDOWS.bat`.
2. Edit `.env`.
3. Enter the Bastion Forge provider Client IDs and Client Secrets.
4. Set `PUBLIC_BASE_URL` to the public HTTPS hostname.
5. Run `RUN_WINDOWS.bat`.
6. Put the same public hostname in `../config/bastion_build_config.json`.
7. Build Stream Hub.

Provider secrets stay here. They are never included in the Windows client.

For a public service, put this behind HTTPS and add normal production controls
such as rate limiting, process supervision and monitoring.
