@echo off
echo Starting EventZella Cloudflare Tunnel...
echo.
echo Your friends can access the app at:
echo https://bare-worm-imports-republican.trycloudflare.com
echo.
echo Close this window to stop the tunnel.
echo.
cloudflared tunnel --url http://localhost:4200
pause
