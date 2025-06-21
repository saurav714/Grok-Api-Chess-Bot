import tkinter as tk
from tkinter import ttk, messagebox
import random
import os
import requests
import re
from dotenv import load_dotenv

load_dotenv()

class ChessVsAI:
    def __init__(self):
        self.PIECES = {
            'K': '♔', 'Q': '♕', 'R': '♖', 'B': '♗', 'N': '♘', 'P': '♙',
            'k': '♚', 'q': '♛', 'r': '♜', 'b': '♝', 'n': '♞', 'p': '♟'
        }
        self.player_side = 'white'
        self.api_provider = os.getenv("API_PROVIDER", "ollama")
        self.reset_game()
        self.setup_gui()

    def reset_game(self):
        self.board = [
            ['r','n','b','q','k','b','n','r'],
            ['p','p','p','p','p','p','p','p'],
            ['.','.','.','.','.','.','.','.'],
            ['.','.','.','.','.','.','.','.'],
            ['.','.','.','.','.','.','.','.'],
            ['.','.','.','.','.','.','.','.'],
            ['P','P','P','P','P','P','P','P'],
            ['R','N','B','Q','K','B','N','R']
        ]
        self.move_history = []
        self.selected_square = None
        self.last_move = None
        self.current_turn = 'white'
        self.white_king_moved = False
        self.black_king_moved = False
        self.white_rook_moved = {'left': False, 'right': False}
        self.black_rook_moved = {'left': False, 'right': False}
        self.en_passant_target = None

    def setup_gui(self):
        self.root = tk.Tk()
        self.root.title("Chess vs AI")
        self.root.configure(bg='#2c3e50')
        
        # Main container
        main_frame = tk.Frame(self.root, bg='#2c3e50')
        main_frame.pack(padx=20, pady=20)
        
        # Title
        title_label = tk.Label(main_frame, text="♔ Chess vs AI ♚", 
                              font=('Arial', 24, 'bold'), 
                              fg='#ecf0f1', bg='#2c3e50')
        title_label.pack(pady=(0, 20))
        
        self.board_frame = tk.Frame(main_frame, bg='#34495e')
        self.board_frame.pack(pady=10)

        self.status_label = tk.Label(main_frame, text="Your move", 
                                   font=('Arial', 16), 
                                   fg='#ecf0f1', bg='#2c3e50')
        self.status_label.pack(pady=15)

        # Control buttons
        self.control_frame = tk.Frame(main_frame, bg='#2c3e50')
        self.control_frame.pack(pady=10)
        
        btn_style = {'font': ('Arial', 12), 'bg': '#3498db', 'fg': 'white', 
                    'relief': 'flat', 'padx': 20, 'pady': 5}
        
        tk.Button(self.control_frame, text="New Game", 
                 command=self.new_game, **btn_style).pack(side='left', padx=5)
        tk.Button(self.control_frame, text="Switch Side", 
                 command=self.switch_side, **btn_style).pack(side='left', padx=5)

        # Move history display
        self.history_label = tk.Label(main_frame, text="Move History: ", 
                                    font=('Arial', 10), 
                                    fg='#bdc3c7', bg='#2c3e50')
        self.history_label.pack(pady=(10, 0))

        self.squares = [[None for _ in range(8)] for _ in range(8)]
        for r in range(8):
            for c in range(8):
                btn = tk.Button(self.board_frame, width=4, height=2,
                               font=('Arial', 20), 
                               command=lambda x=r, y=c: self.on_click(x, y),
                               relief='flat', bd=2)
                btn.grid(row=r, column=c, padx=1, pady=1)
                self.squares[r][c] = btn

        self.update_board()
        if self.player_side == 'black':
            self.root.after(1000, self.ai_move)

        self.root.mainloop()

    def update_board(self):
        for r in range(8):
            for c in range(8):
                piece = self.board[r][c]
                square = self.squares[r][c]
                square.configure(text=self.PIECES.get(piece, ''))
                
                # Board coloring
                if (r + c) % 2 == 0:
                    bg_color = '#f0d9b5'
                else:
                    bg_color = '#b58863'
                
                # Highlight selected square
                if self.selected_square == (r, c):
                    bg_color = '#81e6d9'
                
                # Highlight last move
                if self.last_move and ((r, c) == self.last_move[0] or (r, c) == self.last_move[1]):
                    bg_color = '#9acd32'
                
                square.configure(bg=bg_color)

        # Update status
        if self.is_in_check(self.current_turn):
            if self.is_checkmate(self.current_turn):
                status = f"Checkmate! {'AI' if self.current_turn == self.player_side else 'You'} win!"
            else:
                status = f"Check! {'Your' if self.current_turn == self.player_side else 'AI'} move"
        else:
            status = f"{'Your' if self.current_turn == self.player_side else 'AI'} move"
        
        self.status_label.config(text=status)
        
        # Update move history
        if self.move_history:
            recent_moves = self.move_history[-5:]  # Show last 5 moves
            history_text = "Recent moves: " + " | ".join([
                f"{self.format_move(move)}" for move in recent_moves
            ])
            self.history_label.config(text=history_text)

    def format_move(self, move):
        """Format move for display"""
        from_pos, to_pos, piece = move
        fr, fc = from_pos
        tr, tc = to_pos
        return f"{self.PIECES.get(piece, piece)}{chr(97+fc)}{8-fr}→{chr(97+tc)}{8-tr}"

    def on_click(self, row, col):
        if self.current_turn != self.player_side:
            return

        piece = self.board[row][col]

        if self.selected_square:
            if self.is_valid_move(self.selected_square, (row, col)):
                self.make_move(self.selected_square, (row, col))
                self.selected_square = None
                if not self.is_checkmate(self.current_turn) and self.current_turn != self.player_side:
                    self.root.after(1000, self.ai_move)
            else:
                if self.is_player_piece(piece):
                    self.selected_square = (row, col)
                else:
                    self.selected_square = None
        else:
            if self.is_player_piece(piece):
                self.selected_square = (row, col)

        self.update_board()

    def is_player_piece(self, piece):
        if piece == '.':
            return False
        return piece.isupper() if self.player_side == 'white' else piece.islower()

    def is_valid_move(self, from_pos, to_pos):
        """Enhanced move validation with proper chess rules"""
        fr, fc = from_pos
        tr, tc = to_pos
        
        # Basic bounds check
        if not (0 <= tr < 8 and 0 <= tc < 8):
            return False
        
        piece = self.board[fr][fc].lower()
        target = self.board[tr][tc]
        
        # Can't capture own pieces
        if target != '.' and self.is_same_color(self.board[fr][fc], target):
            return False
        
        # Can't move empty square
        if self.board[fr][fc] == '.':
            return False
        
        # Check if it's the right player's turn
        is_white_piece = self.board[fr][fc].isupper()
        if (self.current_turn == 'white') != is_white_piece:
            return False
        
        # Piece-specific movement validation
        if piece == 'p':
            return self.is_valid_pawn_move(from_pos, to_pos)
        elif piece == 'r':
            return self.is_valid_rook_move(from_pos, to_pos)
        elif piece == 'n':
            return self.is_valid_knight_move(from_pos, to_pos)
        elif piece == 'b':
            return self.is_valid_bishop_move(from_pos, to_pos)
        elif piece == 'q':
            return self.is_valid_queen_move(from_pos, to_pos)
        elif piece == 'k':
            return self.is_valid_king_move(from_pos, to_pos)
        
        return False

    def is_same_color(self, piece1, piece2):
        return piece1.isupper() == piece2.isupper()

    def is_valid_pawn_move(self, from_pos, to_pos):
        fr, fc = from_pos
        tr, tc = to_pos
        piece = self.board[fr][fc]
        target = self.board[tr][tc]
        
        direction = -1 if piece.isupper() else 1  # White moves up (-1), black moves down (+1)
        
        # Forward move
        if fc == tc:
            if tr == fr + direction and target == '.':
                return True
            # Double move from starting position
            if ((fr == 6 and piece.isupper()) or (fr == 1 and piece.islower())) and \
               tr == fr + 2 * direction and target == '.':
                return True
        
        # Diagonal capture
        elif abs(fc - tc) == 1 and tr == fr + direction:
            if target != '.' and not self.is_same_color(piece, target):
                return True
            # En passant
            if self.en_passant_target == (tr, tc):
                return True
        
        return False

    def is_valid_rook_move(self, from_pos, to_pos):
        fr, fc = from_pos
        tr, tc = to_pos
        
        # Must move in straight line
        if fr != tr and fc != tc:
            return False
        
        return self.is_path_clear(from_pos, to_pos)

    def is_valid_bishop_move(self, from_pos, to_pos):
        fr, fc = from_pos
        tr, tc = to_pos
        
        # Must move diagonally
        if abs(fr - tr) != abs(fc - tc):
            return False
        
        return self.is_path_clear(from_pos, to_pos)

    def is_valid_queen_move(self, from_pos, to_pos):
        return self.is_valid_rook_move(from_pos, to_pos) or \
               self.is_valid_bishop_move(from_pos, to_pos)

    def is_valid_knight_move(self, from_pos, to_pos):
        fr, fc = from_pos
        tr, tc = to_pos
        
        dr, dc = abs(fr - tr), abs(fc - tc)
        return (dr == 2 and dc == 1) or (dr == 1 and dc == 2)

    def is_valid_king_move(self, from_pos, to_pos):
        fr, fc = from_pos
        tr, tc = to_pos
        
        # Normal king move (one square in any direction)
        if abs(fr - tr) <= 1 and abs(fc - tc) <= 1:
            return True
        
        # Castling (simplified - doesn't check for check conditions)
        if fr == tr and abs(fc - tc) == 2:
            piece = self.board[fr][fc]
            if piece.isupper() and not self.white_king_moved:
                return True
            elif piece.islower() and not self.black_king_moved:
                return True
        
        return False

    def is_path_clear(self, from_pos, to_pos):
        """Check if path is clear for rook, bishop, queen moves"""
        fr, fc = from_pos
        tr, tc = to_pos
        
        dr = 0 if fr == tr else (1 if tr > fr else -1)
        dc = 0 if fc == tc else (1 if tc > fc else -1)
        
        r, c = fr + dr, fc + dc
        while (r, c) != (tr, tc):
            if self.board[r][c] != '.':
                return False
            r, c = r + dr, c + dc
        
        return True

    def is_in_check(self, color):
        """Check if the king of given color is in check"""
        # Find king position
        king = 'K' if color == 'white' else 'k'
        king_pos = None
        
        for r in range(8):
            for c in range(8):
                if self.board[r][c] == king:
                    king_pos = (r, c)
                    break
            if king_pos:
                break
        
        if not king_pos:
            return False
        
        # Check if any opponent piece can attack the king
        for r in range(8):
            for c in range(8):
                piece = self.board[r][c]
                if piece != '.' and ((piece.isupper() and color == 'black') or 
                                   (piece.islower() and color == 'white')):
                    # Temporarily allow capturing king for check detection
                    if self.can_piece_attack((r, c), king_pos):
                        return True
        
        return False

    def can_piece_attack(self, from_pos, to_pos):
        """Check if piece at from_pos can attack to_pos (ignoring check rules)"""
        fr, fc = from_pos
        piece = self.board[fr][fc].lower()
        
        if piece == 'p':
            return self.is_valid_pawn_attack(from_pos, to_pos)
        elif piece == 'r':
            return self.is_valid_rook_move(from_pos, to_pos)
        elif piece == 'n':
            return self.is_valid_knight_move(from_pos, to_pos)
        elif piece == 'b':
            return self.is_valid_bishop_move(from_pos, to_pos)
        elif piece == 'q':
            return self.is_valid_queen_move(from_pos, to_pos)
        elif piece == 'k':
            fr, fc = from_pos
            tr, tc = to_pos
            return abs(fr - tr) <= 1 and abs(fc - tc) <= 1
        
        return False

    def is_valid_pawn_attack(self, from_pos, to_pos):
        """Check if pawn can attack (different from normal pawn move)"""
        fr, fc = from_pos
        tr, tc = to_pos
        piece = self.board[fr][fc]
        
        direction = -1 if piece.isupper() else 1
        return abs(fc - tc) == 1 and tr == fr + direction

    def is_checkmate(self, color):
        """Check if the given color is in checkmate"""
        if not self.is_in_check(color):
            return False
        
        # Try all possible moves for this color
        for fr in range(8):
            for fc in range(8):
                piece = self.board[fr][fc]
                if piece != '.' and ((piece.isupper() and color == 'white') or 
                                   (piece.islower() and color == 'black')):
                    for tr in range(8):
                        for tc in range(8):
                            if self.is_valid_move((fr, fc), (tr, tc)):
                                # Try the move
                                original = self.board[tr][tc]
                                self.board[tr][tc] = piece
                                self.board[fr][fc] = '.'
                                
                                # Check if still in check
                                still_in_check = self.is_in_check(color)
                                
                                # Undo the move
                                self.board[fr][fc] = piece
                                self.board[tr][tc] = original
                                
                                if not still_in_check:
                                    return False
        
        return True

    def make_move(self, from_pos, to_pos):
        fr, fc = from_pos
        tr, tc = to_pos
        piece = self.board[fr][fc]
        captured = self.board[tr][tc]
        
        # Handle en passant
        if piece.lower() == 'p' and self.en_passant_target == (tr, tc):
            # Remove the captured pawn
            self.board[fr][tc] = '.'
        
        # Make the move
        self.board[tr][tc] = piece
        self.board[fr][fc] = '.'
        
        # Update castling rights
        if piece.lower() == 'k':
            if piece.isupper():
                self.white_king_moved = True
            else:
                self.black_king_moved = True
        elif piece.lower() == 'r':
            if piece.isupper():
                if fc == 0:
                    self.white_rook_moved['left'] = True
                elif fc == 7:
                    self.white_rook_moved['right'] = True
            else:
                if fc == 0:
                    self.black_rook_moved['left'] = True
                elif fc == 7:
                    self.black_rook_moved['right'] = True
        
        # Set en passant target
        self.en_passant_target = None
        if piece.lower() == 'p' and abs(fr - tr) == 2:
            self.en_passant_target = ((fr + tr) // 2, fc)
        
        # Record move
        self.move_history.append((from_pos, to_pos, piece))
        self.last_move = (from_pos, to_pos)
        
        # Switch turns
        self.current_turn = 'white' if self.current_turn == 'black' else 'black'
        self.update_board()

    def new_game(self):
        self.reset_game()
        self.update_board()
        if self.player_side == 'black':
            self.root.after(500, self.ai_move)

    def switch_side(self):
        self.player_side = 'black' if self.player_side == 'white' else 'white'
        self.new_game()

    def ai_move(self):
        if self.is_checkmate(self.current_turn):
            return
            
        prompt = self.generate_prompt()
        move_str = self.query_ai(prompt).strip()
        print("AI raw response:", move_str)

        # Try multiple parsing patterns
        patterns = [
            r"(\d+),\s*(\d+)\s*[-→>]+\s*(\d+),\s*(\d+)",
            r"\((\d+),\s*(\d+)\)\s*[-→>]+\s*\((\d+),\s*(\d+)\)",
            r"([a-h][1-8])\s*[-→>]+\s*([a-h][1-8])"  # Chess notation
        ]

        for pattern in patterns:
            match = re.search(pattern, move_str)
            if match:
                try:
                    if len(match.groups()) == 4:  # Coordinate format
                        fr = (int(match.group(1)), int(match.group(2)))
                        to = (int(match.group(3)), int(match.group(4)))
                    else:  # Chess notation
                        fr = self.chess_to_coords(match.group(1))
                        to = self.chess_to_coords(match.group(2))
                    
                    if self.is_valid_move(fr, to):
                        self.make_move(fr, to)
                        return
                except Exception as e:
                    print("Failed to parse AI move:", e)

        # Fallback: make a random valid move
        print("❌ No valid move found in AI response. Making random move.")
        self.make_random_move()

    def chess_to_coords(self, notation):
        """Convert chess notation (e.g., 'e4') to coordinates"""
        col = ord(notation[0]) - ord('a')
        row = 8 - int(notation[1])
        return (row, col)

    def make_random_move(self):
        """Make a random valid move for the AI"""
        valid_moves = []
        
        for fr in range(8):
            for fc in range(8):
                piece = self.board[fr][fc]
                if piece != '.' and ((piece.isupper() and self.current_turn == 'white') or 
                                   (piece.islower() and self.current_turn == 'black')):
                    for tr in range(8):
                        for tc in range(8):
                            if self.is_valid_move((fr, fc), (tr, tc)):
                                valid_moves.append(((fr, fc), (tr, tc)))
        
        if valid_moves:
            from_pos, to_pos = random.choice(valid_moves)
            self.make_move(from_pos, to_pos)

    def generate_prompt(self):
        board_text = "\n".join([" ".join(row) for row in self.board])
        
        # Add more context for the AI
        context = f"""
You are playing chess as {self.current_turn}.
Current board position (row 0-7, col 0-7):
{board_text}

Legend: 
- Uppercase = White pieces (K=King, Q=Queen, R=Rook, B=Bishop, N=Knight, P=Pawn)
- Lowercase = Black pieces (k=king, q=queen, r=rook, b=bishop, n=knight, p=pawn)  
- . = empty square

"""
        
        if self.is_in_check(self.current_turn):
            context += "⚠️ You are in CHECK! You must move your king to safety or block the attack.\n"
        
        if self.move_history:
            last_move = self.move_history[-1]
            context += f"Last move: {self.format_move(last_move)}\n"
        
        context += """
Respond with ONLY a move in this exact format:
row,col -> row,col

Examples:
6,4 -> 4,4  (move piece from row 6, col 4 to row 4, col 4)
1,1 -> 3,2  (knight move)

Do not include any explanation or other text.
"""
        
        return context

    def query_ai(self, prompt):
        provider = self.api_provider.lower()
        headers = {"Content-Type": "application/json"}

        try:
            if provider == "ollama":
                model = os.getenv("OLLAMA_MODEL", "llama3")
                endpoint = "http://localhost:11434/api/chat"
                data = {
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "options": {
                        "temperature": 0.3,  # Lower temperature for more consistent moves
                        "top_p": 0.9
                    }
                }
                res = requests.post(endpoint, headers=headers, json=data, timeout=30)
                res.raise_for_status()
                json_data = res.json()
                
                if "message" in json_data and "content" in json_data["message"]:
                    return json_data["message"]["content"].strip()
                else:
                    print("Unexpected API response format:", json_data)
                    return ""
                    
            else:
                print(f"Unsupported provider: {provider}")
                return ""

        except requests.exceptions.Timeout:
            print("AI request timed out")
            return ""
        except Exception as e:
            print(f"Error querying {provider}:", e)
            return ""

if __name__ == "__main__":
    ChessVsAI()