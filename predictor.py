import os, json
from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()

client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=os.getenv("OPENROUTER_KEY"))

def get_ai_prediction(match_data: dict):
    implied_home = 100 / match_data['odds_h'] if match_data['odds_h'] else 50
    prompt = f"""
    You are BetMaster, expert quantitative analyst for Nigerian punters.
    RULES: NEVER guarantee win. Always 18+ warning. Prefer safe markets.

    DATA:
    Match: {match_data['home']} vs {match_data['away']} ({match_data['league']})
    Home xG: {match_data['home_xg']} Away xG: {match_data['away_xg']}
    Form: Home {match_data['home_form']} Away {match_data['away_form']}
    H2H Home wins last 5: {match_data['h2h']}
    Injuries: Home {match_data['home_inj']} Away {match_data['away_inj']}
    Bookie Odds: H {match_data['odds_h']} D {match_data['odds_d']} A {match_data['odds_a']} Over2.5 {match_data['odds_over']}
    Bookie Implied Home: {implied_home:.1f}%

    TASK:
    Return JSON only:
    {{
      "home_prob": int, "draw_prob": int, "away_prob": int,
      "best_pick": "e.g Over 1.5 Goals, Double Chance X2, BTTS Yes, Home Win",
      "confidence": "Low/Medium/High",
      "explanation": "2 short lines in Naija Pidgin + English mix, why this pick",
      "is_value_bet": bool,
      "stake_advice": "Flat 2% bankroll etc"
    }}
    Best_pick MUST be safe: Prefer Over 1.5, Under 3.5, Double Chance, BTTS. Only straight win if prob >65%.
    Sum probs = 100.
    """
    try:
        res = client.chat.completions.create(
            model="deepseek/deepseek-r1",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            response_format={"type": "json_object"}
        )
        data = json.loads(res.choices[0].message.content)
        # validation
        total = data.get('home_prob',0)+data.get('draw_prob',0)+data.get('away_prob',0)
        if total!=100:
            data['home_prob']=50; data['draw_prob']=25; data['away_prob']=25
        return data
    except Exception as e:
        print(f"AI fail: {e}")
        return {
            "home_prob": 55, "draw_prob": 25, "away_prob": 20,
            "best_pick": "Over 1.5 Goals",
            "confidence": "Medium",
            "explanation": "Home dey score for house, away defense dey leak. Over 1.5 safer.",
            "is_value_bet": False,
            "stake_advice": "Flat 2% bankroll. No chase loss."
        }
