import os, json
from dotenv import load_dotenv
load_dotenv()

def get_ai_prediction(match_data: dict):
    api_key = os.getenv("OPENROUTER_KEY")
    if not api_key:
        print("OPENROUTER_KEY missing - using fallback")
        return {
            "home_prob": 55, "draw_prob": 25, "away_prob": 20,
            "best_pick": "Over 1.5 Goals",
            "confidence": "Medium",
            "explanation": "Home dey score for house, away defense dey leak. Over 1.5 safer.",
            "is_value_bet": False,
            "stake_advice": "Flat 2% bankroll. No chase loss."
        }
    try:
        from openai import OpenAI
        client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
        implied_home = 100 / match_data['odds_h'] if match_data['odds_h'] else 50
        prompt = f"Match: {match_data['home']} vs {match_data['away']}. Return JSON home_prob,draw_prob,away_prob,best_pick,confidence,explanation,is_value_bet,stake_advice. Prefer safe Over 1.5/X2/BTTS."
        res = client.chat.completions.create(
            model="deepseek/deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            response_format={"type": "json_object"}
        )
        data = json.loads(res.choices[0].message.content)
        return data
    except Exception as e:
        print(f"AI fail: {e}")
        return {
            "home_prob": 55, "draw_prob": 25, "away_prob": 20,
            "best_pick": "Over 1.5 Goals",
            "confidence": "Medium",
            "explanation": "Home dey score for house, away defense dey leak.",
            "is_value_bet": False,
            "stake_advice": "Flat 2% bankroll."
        }
