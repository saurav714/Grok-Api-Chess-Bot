import os
import chess
import requests
import logging

logger = logging.getLogger(__name__)

class ChessEngine:
    def __init__(self):
        self.api_key = os.getenv('GROK_API_KEY')

    def get_best_move(self, board):
        """
        Given a python-chess Board object, query the Grok API for the best move and explanation.
        Returns (move, explanation) or (None, error_message)
        """
        if not self.api_key:
            logger.error("GROK_API_KEY not set in environment.")
            return None, "API key not set."

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        color = "White" if board.turn else "Black"
        prompt = (
            f"Given this chess position (FEN): {board.fen()}\n"
            f"Suggest the best move for {color} and explain why.\n"
            f"Format: Best move in algebraic notation (e.g., e4, Nf3) "
            f"followed by a brief explanation."
        )

        payload = {
            "model": "grok-3",
            "prompt": prompt,
            "max_tokens": 100,
            "temperature": 0.7
        }

        try:
            response = requests.post(
                "https://api.x.ai/v1/grok",
                headers=headers,
                json=payload,
                timeout=30
            )
            if response.status_code == 200:
                result = response.json()['choices'][0]['text'].strip()
                lines = result.split('\n', 1)
                move = lines[0].split()[-1].strip()
                explanation = lines[1].strip() if len(lines) > 1 else ""
                try:
                    move_obj = board.parse_san(move)
                    if board.is_legal(move_obj):
                        return move, explanation
                except Exception:
                    pass
                return None, "No valid move found"
            else:
                logger.error(f"Grok API error: {response.status_code}")
                return None, f"API error: {response.status_code}"
        except Exception as e:
            logger.error(f"Error contacting Grok API: {e}")
            return None, str(e)