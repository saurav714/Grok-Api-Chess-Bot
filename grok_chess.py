import chess
import requests
import json
import time
import os
from dotenv import load_dotenv
from typing import Optional, Dict, Any

# Load environment variables from .env file
load_dotenv()

class ChessGameGrok:
    def __init__(self):
        """
        Initialize chess game with Grok API integration
        Loads API key from environment variables
        """
        self.board = chess.Board()
        
        # Load Grok API key from environment
        self.grok_api_key = os.getenv('GROK_API_KEY')
        if not self.grok_api_key:
            raise ValueError("GROK_API_KEY not found in environment variables. Please set it in your .env file.")
        
        self.game_history = []
        self.grok_api_url = "https://api.x.ai/v1/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {self.grok_api_key}",
            "Content-Type": "application/json"
        }
        
    def display_board(self):
        """Display the current board position"""
        print("\n" + "="*50)
        print("Current Board Position:")
        print("="*50)
        print(self.board)
        print(f"\nFEN: {self.board.fen()}")
        print(f"Turn: {'White' if self.board.turn else 'Black'}")
        
        if self.board.is_check():
            print("*** CHECK! ***")
        if self.board.is_checkmate():
            print("*** CHECKMATE! ***")
        if self.board.is_stalemate():
            print("*** STALEMATE! ***")
        print("="*50)
    
    def get_legal_moves(self):
        """Get all legal moves in current position"""
        return [str(move) for move in self.board.legal_moves]
    
    def make_move(self, move_str: str) -> bool:
        """
        Make a move on the board
        
        Args:
            move_str: Move in algebraic notation (e.g., 'e2e4', 'Nf3')
            
        Returns:
            bool: True if move was successful, False otherwise
        """
        try:
            # Try to parse the move as UCI format first
            move = chess.Move.from_uci(move_str)
            
            if move in self.board.legal_moves:
                self.board.push(move)
                self.game_history.append(move_str)
                print(f"Move played: {move_str}")
                return True
            else:
                print(f"Illegal move: {move_str}")
                return False
                
        except ValueError:
            # Try algebraic notation
            try:
                move = self.board.parse_san(move_str)
                self.board.push(move)
                self.game_history.append(str(move))
                print(f"Move played: {move_str}")
                return True
            except ValueError:
                print(f"Invalid move format: {move_str}")
                return False
    
    def get_grok_chess_move(self, difficulty: str = "medium") -> Optional[str]:
        """
        Get best move from Grok API
        
        Args:
            difficulty: Difficulty level ("easy", "medium", "hard", "expert")
            
        Returns:
            str: Best move in UCI format, or None if API call fails
        """
        try:
            # Create legal moves list for Grok
            legal_moves = self.get_legal_moves()
            legal_moves_str = ", ".join(legal_moves[:20])  # Limit to first 20 moves
            
            # Difficulty-based prompts
            difficulty_prompts = {
                "easy": "Play a reasonable but not necessarily optimal move. Consider basic tactics.",
                "medium": "Play a good move considering tactics and positional play.",
                "hard": "Play a strong move with deep tactical and strategic consideration.",
                "expert": "Play the best possible move with maximum precision and depth."
            }
            
            prompt = f"""You are a chess engine. Analyze the current position and suggest the best move.

Current board position (FEN): {self.board.fen()}
Your color: {'White' if self.board.turn else 'Black'}
Legal moves available: {legal_moves_str}

Difficulty level: {difficulty}
Instructions: {difficulty_prompts.get(difficulty, difficulty_prompts["medium"])}

Game context:
- Move history: {' '.join(self.game_history[-10:])}  # Last 10 moves
- Is in check: {self.board.is_check()}
- Castling rights: K={'O-O' in [str(m) for m in self.board.legal_moves]}, Q={'O-O-O' in [str(m) for m in self.board.legal_moves]}

Please respond with ONLY the move in UCI format (e.g., e2e4, g1f3, e1g1 for castling).
Do not include any explanation or additional text - just the move."""

            payload = {
                "messages": [
                    {
                        "role": "system",
                        "content": "You are Grok, a chess-playing AI. Respond only with chess moves in UCI format."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "model": "grok-beta",
                "stream": False,
                "temperature": 0.3
            }
            
            print("🤖 Grok is analyzing the position...")
            
            response = requests.post(
                self.grok_api_url,
                headers=self.headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if "choices" in data and len(data["choices"]) > 0:
                    grok_response = data["choices"][0]["message"]["content"].strip()
                    
                    # Extract move from response (handle various formats)
                    move_candidates = grok_response.split()
                    
                    for candidate in move_candidates:
                        # Clean the candidate (remove punctuation, etc.)
                        clean_move = ''.join(c for c in candidate if c.isalnum())
                        
                        # Check if it's a valid UCI move format
                        if len(clean_move) >= 4 and clean_move in legal_moves:
                            return clean_move
                    
                    # If no valid move found, try the full response
                    clean_response = ''.join(c for c in grok_response if c.isalnum())
                    if clean_response in legal_moves:
                        return clean_response
                    
                    print(f"⚠️ Grok suggested: '{grok_response}' but it's not a valid move")
                    return None
                else:
                    print("❌ No response from Grok API")
                    return None
            else:
                print(f"❌ Grok API error: {response.status_code}")
                if response.text:
                    print(f"Error details: {response.text}")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"🌐 Network error connecting to Grok: {e}")
            return None
        except json.JSONDecodeError as e:
            print(f"📄 JSON parsing error: {e}")
            return None
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            return None
    
    def get_random_legal_move(self) -> str:
        """Get a random legal move as fallback"""
        import random
        legal_moves = list(self.board.legal_moves)
        if legal_moves:
            return str(random.choice(legal_moves))
        return None
    
    def play_grok_move(self, difficulty: str = "medium") -> bool:
        """
        Let Grok make a move
        
        Args:
            difficulty: Difficulty level for Grok
            
        Returns:
            bool: True if move was made, False if game is over
        """
        if self.board.is_game_over():
            return False
        
        # Try to get move from Grok
        grok_move = self.get_grok_chess_move(difficulty)
        
        # Fallback to random move if Grok fails
        if not grok_move:
            print("🎲 Grok unavailable, using random move...")
            grok_move = self.get_random_legal_move()
        
        if grok_move:
            success = self.make_move(grok_move)
            if success:
                print(f"🤖 Grok played: {grok_move}")
                return True
        
        return False
    
    def get_grok_analysis(self) -> str:
        """Get position analysis from Grok"""
        try:
            prompt = f"""Analyze this chess position briefly:

Current position (FEN): {self.board.fen()}
Turn: {'White' if self.board.turn else 'Black'}
Recent moves: {' '.join(self.game_history[-5:])}

Provide a concise analysis covering:
1. Material balance
2. Key tactical/strategic themes
3. Who has the advantage and why

Keep it under 100 words."""

            payload = {
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "model": "grok-beta",
                "stream": False,
                "temperature": 0.5
            }
            
            response = requests.post(
                self.grok_api_url,
                headers=self.headers,
                json=payload,
                timeout=20
            )
            
            if response.status_code == 200:
                data = response.json()
                if "choices" in data and len(data["choices"]) > 0:
                    return data["choices"][0]["message"]["content"]
            
            return "Analysis unavailable"
            
        except Exception as e:
            return f"Analysis error: {e}"
    
    def get_game_status(self) -> Dict[str, Any]:
        """Get current game status"""
        return {
            "is_game_over": self.board.is_game_over(),
            "is_checkmate": self.board.is_checkmate(),
            "is_stalemate": self.board.is_stalemate(),
            "is_check": self.board.is_check(),
            "turn": "White" if self.board.turn else "Black",
            "move_count": len(self.game_history),
            "fen": self.board.fen()
        }
    
    def save_game_pgn(self, filename: str = "grok_chess_game.pgn"):
        """Save game in PGN format"""
        try:
            game = chess.pgn.Game()
            game.headers["Event"] = "Grok Chess Game"
            game.headers["Site"] = "Python Chess with Grok"
            game.headers["Date"] = time.strftime("%Y.%m.%d")
            game.headers["White"] = "Human"
            game.headers["Black"] = "Grok AI"
            
            node = game
            board = chess.Board()
            
            for move_str in self.game_history:
                try:
                    move = chess.Move.from_uci(move_str)
                    node = node.add_variation(move)
                    board.push(move)
                except ValueError:
                    continue
            
            with open(filename, "w") as f:
                f.write(str(game))
            
            print(f"💾 Game saved to {filename}")
            
        except Exception as e:
            print(f"❌ Error saving game: {e}")

def main():
    """Main game loop"""
    print("="*60)
    print("🤖 PYTHON CHESS GAME WITH GROK AI 🤖")
    print("="*60)
    print("Play chess against Grok, xAI's conversational AI!")
    print()
    print("Commands:")
    print("- Enter moves in UCI format (e2e4) or algebraic notation (Nf3)")
    print("- Type 'help' for available commands")
    print("- Type 'quit' to exit")
    print("="*60)
    
    # Initialize game (API key loaded from .env file)
    try:
        game = ChessGameGrok()
        print("✅ Grok API key loaded successfully!")
    except ValueError as e:
        print(f"❌ Error: {e}")
        print("\n📋 To fix this:")
        print("1. Create a .env file in the same directory as this script")
        print("2. Add this line to the .env file:")
        print("   GROK_API_KEY=your_actual_api_key_here")
        print("3. Replace 'your_actual_api_key_here' with your real Grok API key")
        return
    
    # Choose difficulty
    print("\n🎯 Choose Grok's difficulty level:")
    print("1. Easy - Basic moves")
    print("2. Medium - Good tactical play")
    print("3. Hard - Strong strategic play")
    print("4. Expert - Maximum strength")
    
    difficulty_map = {"1": "easy", "2": "medium", "3": "hard", "4": "expert"}
    difficulty_choice = input("Enter choice (1-4, default=2): ").strip()
    difficulty = difficulty_map.get(difficulty_choice, "medium")
    
    print(f"🎮 Playing against Grok on {difficulty} difficulty!")
    
    # Game loop
    while True:
        game.display_board()
        
        # Check if game is over
        status = game.get_game_status()
        if status["is_game_over"]:
            if status["is_checkmate"]:
                winner = "Black (Grok)" if game.board.turn else "White (You)"
                print(f"\n🎉 Game Over! {winner} wins by checkmate!")
            elif status["is_stalemate"]:
                print("\n🤝 Game Over! Draw by stalemate!")
            else:
                print("\n🏁 Game Over!")
            
            save_game = input("💾 Save game? (y/n): ").lower()
            if save_game == 'y':
                filename = input("Enter filename (or press Enter for default): ").strip()
                if filename:
                    game.save_game_pgn(filename)
                else:
                    game.save_game_pgn()
            break
        
        # Human move
        if game.board.turn:  # White's turn (human)
            print(f"\n📋 Legal moves: {', '.join(game.get_legal_moves()[:8])}{'...' if len(game.get_legal_moves()) > 8 else ''}")
            
            user_input = input("👤 Your move: ").strip().lower()
            
            if user_input == 'quit':
                break
            elif user_input == 'help':
                print("\n📚 Commands:")
                print("- moves: Show all legal moves")
                print("- analysis: Get Grok's position analysis")
                print("- fen: Show current FEN")
                print("- history: Show move history")
                print("- status: Show game status")
                print("- difficulty: Change Grok's difficulty")
                print("- save: Save current game")
                print("- quit: Exit game")
                continue
            elif user_input == 'moves':
                legal_moves = game.get_legal_moves()
                print(f"\n📋 All legal moves ({len(legal_moves)}):")
                for i, move in enumerate(legal_moves, 1):
                    print(f"{i:2d}. {move}", end="  ")
                    if i % 6 == 0:
                        print()
                print()
                continue
            elif user_input == 'analysis':
                print("\n🧠 Grok's Analysis:")
                print(game.get_grok_analysis())
                continue
            elif user_input == 'fen':
                print(f"📄 FEN: {game.board.fen()}")
                continue
            elif user_input == 'history':
                print(f"📜 Move history: {' '.join(game.game_history)}")
                continue
            elif user_input == 'status':
                status = game.get_game_status()
                for key, value in status.items():
                    print(f"{key}: {value}")
                continue
            elif user_input == 'difficulty':
                print("🎯 Change difficulty:")
                print("1. Easy  2. Medium  3. Hard  4. Expert")
                new_choice = input("Enter choice (1-4): ").strip()
                difficulty = difficulty_map.get(new_choice, difficulty)
                print(f"🔄 Difficulty set to: {difficulty}")
                continue
            elif user_input == 'save':
                filename = input("💾 Enter filename: ").strip()
                if filename:
                    game.save_game_pgn(filename)
                continue
            
            # Try to make the move
            if not game.make_move(user_input):
                print("❌ Invalid move! Try again.")
                continue
        
        else:  # Black's turn (Grok)
            if not game.play_grok_move(difficulty):
                print("🤖 Grok cannot move!")
                break
    
    print("\n🎮 Thanks for playing chess with Grok! 👋")

if __name__ == "__main__":
    # Note: You'll need to install required packages:
    # pip install python-chess requests python-dotenv
    # 
    # Also create a .env file with:
    # GROK_API_KEY=your_actual_grok_api_key_here
    
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⏹️ Game interrupted. Goodbye! 👋")
    except ImportError as e:
        print(f"❌ Missing required package: {e}")
        print("Please install required packages:")
        print("pip install python-chess requests python-dotenv")
        print("\nAlso create a .env file with your Grok API key:")
        print("GROK_API_KEY=your_actual_api_key_here")