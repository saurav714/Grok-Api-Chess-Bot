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
        self.root.geometry("minsize")
        self.root.resizable(True, True)

        # Main container
        main_frame = tk.Frame(self.root, bg='#2c3e50')
        main_frame.pack(padx=20, pady=20, expand=True, fill='both')

        # Title
        title_label = tk.Label(main_frame, text="♔ Chess vs AI ♚", 
                              font=('Arial', 24, 'bold'), 
                              fg='#ecf0f1', bg='#2c3e50')
        title_label.pack(pady=(0, 20))

        self.board_frame = tk.Frame(main_frame, bg='#34495e')
        self.board_frame.pack(pady=10, expand=True)

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
                btn.grid(row=r, column=c, padx=1, pady=1, sticky='nsew')
                self.squares[r][c] = btn

        for i in range(8):
            self.board_frame.grid_columnconfigure(i, weight=1)
            self.board_frame.grid_rowconfigure(i, weight=1)

        self.update_board()
        if self.player_side == 'black':
            self.root.after(1000, self.ai_move)

        self.root.mainloop()

    # ... rest of the class unchanged ...

if __name__ == "__main__":
    ChessVsAI()
