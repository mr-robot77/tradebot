# Procfile
#
# Start command for Railway, Heroku, and any Procfile-aware platform.
#
# Railway deployment (3 minutes):
#   1. Sign up at https://railway.app  (GitHub login works)
#   2. New Project → Deploy from GitHub repo → mr-robot77/tradebot
#   3. Railway reads this file automatically
#   4. Set NIXPACKS_INSTALL_CMD=pip install -r requirements-dashboard.txt
#      in the Railway service environment variables
#   5. Your dashboard is live at the URL Railway assigns

web: gunicorn backtest_dashboard:server --bind 0.0.0.0:$PORT --workers 1 --timeout 120
