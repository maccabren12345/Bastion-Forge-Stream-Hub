# Bastion Forge Stream Hub Beta Backend

This small service is for the private Discord beta and can continue serving the public app later.

It provides:

- Stream Hub update manifest
- verified installer downloads
- structured beta feedback endpoint
- optional Discord webhook notification when a tester sends a report
- release history files created by the publish script

## Private beta setup

1. Run `INSTALL_WINDOWS.bat` on the Bastion Forge server.
2. Edit `.env`.
3. Set `PUBLIC_BASE_URL` to the public HTTPS hostname (Cloudflare Tunnel is fine).
4. Optionally set `DISCORD_FEEDBACK_WEBHOOK_URL` to a webhook from a private `stream-hub-beta-bugs` channel.
5. Start `RUN_WINDOWS.bat` or install it as a startup service/task.
6. Point the client build config at:
   - `/streamhub/manifest.json`
   - `/streamhub/feedback`

Keep the Discord webhook URL server-side only.
