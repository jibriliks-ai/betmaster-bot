import requests, os
from datetime import date
from dotenv import load_dotenv
load_dotenv()

API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY")

def get_todays_fixtures():
    url = "https://v3.football.api-sports.io/fixtures"
    headers = {"x-apisports-key": API_FOOTBALL_KEY}
    today = date.today().isoformat()
    try:
        res = requests.get(url, headers=headers, params={"date": today}, timeout=15).json()
        fixtures = []
        for fix in res.get("response", [])[:15]:
            fixtures.append({
                "id": fix["fixture"]["id"],
                "home": fix["teams"]["home"]["name"],
                "away": fix["teams"]["away"]["name"],
                "league": fix["league"]["name"],
                "date": fix["fixture"]["date"]
            })
        return fixtures
    except:
        # Fallback mock if API fails / free limit reached
        return [
            {"id": 1, "home": "Arsenal", "away": "Chelsea", "league": "Premier League", "date": today},
            {"id": 2, "home": "Al Hilal", "away": "Al Nassr", "league": "Saudi Pro League", "date": today},
            {"id": 3, "home": "Palmeiras", "away": "Flamengo", "league": "Brazil Serie A", "date": today},
        ]

def get_odds_from_api_football(fixture_id):
    url = "https://v3.football.api-sports.io/odds"
    headers = {"x-apisports-key": API_FOOTBALL_KEY}
    params = {"fixture": fixture_id, "bookmaker": 8} # 8 = Bet9ja
    try:
        res = requests.get(url, headers=headers, params=params, timeout=15).json()
        bets = res["response"][0]["bookmakers"][0]["bets"]
        h2h = next((b for b in bets if b["name"] == "Match Winner"), None)
        if h2h:
            odds = {v["value"]: float(v["odd"]) for v in h2h["values"]}
            return odds.get("Home", 2.1), odds.get("Away", 3.2), odds.get("Draw", 3.4), 1.75
    except:
        pass
    return 2.1, 3.4, 3.2, 1.75
