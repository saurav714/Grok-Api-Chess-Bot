import os
import chess
import logging
import requests
import time
import queue
from .browser_helper import BrowserHelper

logger = logging.getLogger(__name__)

class ChessBot:
    def __init__(self, config):
        self.config = config
        self.browser = BrowserHelper(config['platform'])
        self.board = chess.Board()
        self.running = False
        self.grok_api_key = os.getenv('GROK_API_KEY')
        self.message_queue = queue.Queue()
        
    def start(self):
        if not self.grok_api_key:
            raise ValueError("GROK_API_KEY not found in environment variables")
            
        if not self.browser.initialize():
            raise RuntimeError("Failed to initialize browser")
            
        self.running = True
        while self.running:
            try:
                self.process_move()
                time.sleep(1)
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                self.message_queue.put(('error', str(e)))
                break
                
        self.cleanup()
        
    def process_move(self):
        current_fen = self.browser.get_position()
        if not current_fen:
            return
            
        self.board = chess.Board(current_fen)
        self.message_queue.put(('board_update', self.board))
        
        is_our_turn = (self.board.turn == chess.WHITE and 
                      self.config['player_color'] == 'white') or \
                     (self.board.turn == chess.BLACK and 
                      self.config['player_color'] == 'black')
        
        if is_our_turn:
            move, explanation = self.get_best_move(current_fen)
            if move:
                self.message_queue.put(('suggestion', f"Suggested: {move}\n{explanation}"))
                move_obj = self.board.parse_san(move)
                if self.browser.play_move(move_obj, self.board):
                    self.message_queue.put(('info', f"Played move: {move}"))
                
    def get_best_move(self, fen):
        try:
            headers = {
                "Authorization": f"Bearer {self.grok_api_key}",
                "Content-Type": "application/json"
            }
            
            color = "White" if self.board.turn else "Black"
            prompt = (
                f"Given this chess position (FEN): {fen}\n"
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
                    self.board.parse_san(move)
                    return move, explanation
                except ValueError:
                    logger.warning(f"Invalid move suggested: {move}")
                    return None, "Invalid move suggested"
            else:
                logger.error(f"API error: {response.status_code}")
                return None, f"API error: {response.status_code}"
                
        except Exception as e:
            logger.error(f"Error getting move suggestion: {e}")
            return None, str(e)
            
    def cleanup(self):
        if self.browser:
            self.browser.cleanup()
        self.running = False