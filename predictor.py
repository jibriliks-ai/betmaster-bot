import os, json
from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()

client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=os.getenv("OPENROUTER_KEY"))

def get_ai_prediction(match_data: dict):
    implied_home = 100 / match_data['odds_h'] if match_data['odds_h'] else 50
    prompt = f"""
    You are BetMaster, quantitative analyst for Nigeria betting.
    NEVER guarantee win. Give probabilities.

    DATA:
    Match: {match_data['home']} vs {match_data['away']} ({match_data['league']})
    Home xG: {match_data['home_xg']} Away xG: {match_data['away_xg']}
    Form: Home {match_data['home_form']} Away {match_data['away_form']}
    H2H Home wins last 5: {match_data['h2h']}
    Injuries: Home {match_data['home_inj']} Away {match_data['away_inj']}
    Bookie Odds: H {match_data['odds_h']} D {match_data['odds_d']} A {match_data['odds_a']} Over2.5 {match_data['odds_over']}
    Bookie Implied Home: {implied_home:.1f}%

    TASK:
    1. fair probabilities home/draw/away sum 100%
    2. is_value_bet = true if your prob > implied +5%
    3. best_pick MUST be safe: Prefer Over 1.5, Double Chance X2, BTTS, Under 3.5. Only straight win if prob >65%
    4. confidence Low/Medium/High
    5. explanation 2 lines Naija English
    6. stake_advice e.g. "Flat 2% bankroll"

    Return JSON: {{"home_prob": int, "draw_prob": int, "away_prob": int, "best_pick": str, "confidence": str, "explanation": str, "is_value_bet": bool, "stake_advice": str}}
    """
    try:
        res = client.chat.completions.create(
            model="deepseek/deepseek-r1",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            response_format={"type": "json_object"}
        )
        return json.loads(res.choices[0].message.content)
    except Exception as e:
        # Fallback if AI fails
        return {
            "home_prob": 55, "draw_prob": 25, "away_prob": 20,
            "best_pick": "Over 1.5 Goals",
            "confidence": "Medium",
            "explanation": "Home dey score for house, away defense dey leak small.",
            "is_value_bet": False,
            "stake_advice": "Flat 2% bankroll. No chase."
        }
