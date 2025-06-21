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
        self.api_provider = os.getenv("API_PROVIDER", "openai")
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

    def setup_gui(self):
        self.root = tk.Tk()
        self.root.title("Chess vs AI")
        self.board_frame = tk.Frame(self.root)
        self.board_frame.pack()

        self.status_label = tk.Label(self.root, text="Your move", font=('Arial', 14))
        self.status_label.pack(pady=10)

        self.control_frame = tk.Frame(self.root)
        self.control_frame.pack(pady=5)
        tk.Button(self.control_frame, text="New Game", command=self.new_game).pack(side='left', padx=5)
        tk.Button(self.control_frame, text="Switch Side", command=self.switch_side).pack(side='left', padx=5)

        self.squares = [[None for _ in range(8)] for _ in range(8)]
        for r in range(8):
            for c in range(8):
                btn = tk.Button(self.board_frame, width=4, height=2,
                                font=('Arial', 20), command=lambda x=r, y=c: self.on_click(x, y))
                btn.grid(row=r, column=c)
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
                square.configure(text=self.PIECES.get(piece, ''), bg='#f0d9b5' if (r+c)%2==0 else '#b58863')
                if self.selected_square == (r, c):
                    square.configure(bg='#81e6d9')

        self.status_label.config(text=f"{'Your' if self.current_turn == self.player_side else 'AI'} move")

    def on_click(self, row, col):
        if self.current_turn != self.player_side:
            return

        piece = self.board[row][col]

        if self.selected_square:
            if self.is_valid_move(self.selected_square, (row, col)):
                self.make_move(self.selected_square, (row, col))
                self.selected_square = None
                if self.current_turn != self.player_side:
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
        return piece.isupper() if self.player_side == 'white' else piece.islower()

    def is_valid_move(self, from_pos, to_pos):
        fr, fc = from_pos
        tr, tc = to_pos
        if not (0 <= tr < 8 and 0 <= tc < 8):
            return False
        piece = self.board[fr][fc]
        target = self.board[tr][tc]
        if self.is_player_piece(target):
            return False
        return piece != '.'

    def make_move(self, from_pos, to_pos):
        fr, fc = from_pos
        tr, tc = to_pos
        piece = self.board[fr][fc]
        self.board[tr][tc] = piece
        self.board[fr][fc] = '.'
        self.move_history.append((from_pos, to_pos, piece))
        self.last_move = (from_pos, to_pos)
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
        prompt = self.generate_prompt()
        move_str = self.query_ai(prompt)
        print("AI raw response:", move_str)

        match = re.search(r"(\d,\d)\s*->\s*(\d,\d)", move_str)
        if match:
            try:
                fr = tuple(map(int, match.group(1).split(",")))
                to = tuple(map(int, match.group(2).split(",")))
                if self.is_valid_move(fr, to):
                    self.make_move(fr, to)
            except Exception as e:
                print("Failed to parse AI move:", e)
        else:
            print("No valid move found in AI response.")

    def generate_prompt(self):
        board_text = "\n".join([" ".join(row) for row in self.board])
        return f"""
You are a chess AI playing as {self.current_turn}.
The board is:
{board_text}
Give one best move in format: row,col -> row,col
Only respond with the move.
"""

    def query_ai(self, prompt):
        provider = self.api_provider.lower()
        headers = {"Content-Type": "application/json"}

        try:
            if provider == "openai":
                headers["Authorization"] = f"Bearer {os.getenv('OPENAI_API_KEY')}"
                endpoint = "https://api.openai.com/v1/chat/completions"
                data = {
                    "model": "gpt-3.5-turbo",
                    "messages": [{"role": "user", "content": prompt}]
                }
                res = requests.post(endpoint, headers=headers, json=data)
                res.raise_for_status()
                return res.json()["choices"][0]["message"]["content"]
            elif provider == "grok":
                headers["Authorization"] = f"Bearer {os.getenv('GROK_API_KEY')}"
                endpoint = "https://api.grok.com/v1/chat/completions"
                data = {
                    "model": "grok-1",
                    "messages": [{"role": "user", "content": prompt}]
                }
            elif provider == "deepseek":
                headers["Authorization"] = f"Bearer {os.getenv('DEEPSEEK_API_KEY')}"
                endpoint = "https://api.deepseek.com/v1/chat/completions"
                data = {
                    "model": "deepseek-chat",
                    "messages": [{"role": "user", "content": prompt}]
                }
            elif provider == "claude":
                headers["Authorization"] = f"Bearer {os.getenv('CLAUDE_API_KEY')}"
                endpoint = "https://api.anthropic.com/v1/messages"
                data = {
                    "model": "claude-3-opus-20240229",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 200
                }
            elif provider == "ollama":
                endpoint = "http://localhost:11434/api/chat"
                data = {
                    "model": "llama3",
                    "messages": [{"role": "user", "content": prompt}]
                }
            else:
                print("Unsupported API provider.")
                return ""

            res = requests.post(endpoint, headers=headers, json=data)
            res.raise_for_status()
            return res.json()["choices"][0]["message"]["content"]

        except Exception as e:
            print(f"Error querying {provider}:", e)
            return ""

if __name__ == "__main__":
    ChessVsAI()
