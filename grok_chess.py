import tkinter as tk
from tkinter import ttk, messagebox
import random
import copy

class ChessVsAI:
    def __init__(self):
        self.PIECES = {
            'K': '♔', 'Q': '♕', 'R': '♖', 'B': '♗', 'N': '♘', 'P': '♙',
            'k': '♚', 'q': '♛', 'r': '♜', 'b': '♝', 'n': '♞', 'p': '♟'
        }
        self.player_side = 'white'
        self.board_size = 6  # 6x6 board
        self.reset_game()
        self.setup_gui()

    def reset_game(self):
        # Initial 6x6 board setup (custom for mini-chess)
        self.board = [
            ['r', 'n', 'b', 'q', 'k', 'r'],
            ['p', 'p', 'p', 'p', 'p', 'p'],
            ['.', '.', '.', '.', '.', '.'],
            ['.', '.', '.', '.', '.', '.'],
            ['P', 'P', 'P', 'P', 'P', 'P'],
            ['R', 'N', 'B', 'Q', 'K', 'R']
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
        self.game_over = False
        self.check_status = None
        self.fifty_move_counter = 0
        self.position_history = []

    def setup_gui(self):
        self.root = tk.Tk()
        self.root.title("Mini-Chess vs AI")
        self.root.configure(bg='#2c3e50')
        self.root.geometry("600x700")  # Smaller window for 6x6
        self.root.resizable(True, True)
        self.root.minsize(500, 500)

        main_frame = tk.Frame(self.root, bg='#2c3e50')
        main_frame.pack(padx=15, pady=15, expand=True, fill='both')

        title_label = tk.Label(main_frame, text="♔ Mini-Chess vs AI ♚", 
                              font=('Arial', 20, 'bold'), 
                              fg='#ecf0f1', bg='#2c3e50')
        title_label.pack(pady=(0, 15))

        self.board_container = tk.Frame(main_frame, bg='#34495e')
        self.board_container.pack(pady=10, expand=True, fill='both')
        
        self.board_frame = tk.Frame(self.board_container, bg='#34495e')
        self.board_frame.pack(expand=True, fill='both')
        
        self.status_label = tk.Label(main_frame, text="Your move", 
                                   font=('Arial', 14), 
                                   fg='#ecf0f1', bg='#2c3e50')
        self.status_label.pack(pady=10)

        self.control_frame = tk.Frame(main_frame, bg='#2c3e50')
        self.control_frame.pack(pady=10)

        btn_style = {'font': ('Arial', 10), 'bg': '#3498db', 'fg': 'white', 
                    'relief': 'flat', 'padx': 15, 'pady': 5}

        tk.Button(self.control_frame, text="New Game", 
                 command=self.new_game, **btn_style).pack(side='left', padx=5)
        tk.Button(self.control_frame, text="Switch Side", 
                 command=self.switch_side, **btn_style).pack(side='left', padx=5)
        tk.Button(self.control_frame, text="Undo Move", 
                 command=self.undo_move, **btn_style).pack(side='left', padx=5)

        self.history_label = tk.Label(main_frame, text="Move History: ", 
                                    font=('Arial', 8), 
                                    fg='#bdc3c7', bg='#2c3e50')
        self.history_label.pack(pady=(10, 0))

        self.squares = [[None for _ in range(self.board_size)] for _ in range(self.board_size)]
        self.create_board()
        
        self.root.bind('<Configure>', self.on_window_resize)

        self.update_board()
        if self.player_side == 'black':
            self.root.after(1000, self.ai_move)

    def create_board(self):
        for r in range(self.board_size):
            for c in range(self.board_size):
                if self.squares[r][c]:
                    self.squares[r][c].destroy()
                
                btn = tk.Button(
                    self.board_frame,
                    font=('Arial', 18),
                    command=lambda x=r, y=c: self.on_click(x, y),
                    relief='flat', 
                    bd=2
                )
                btn.grid(row=r, column=c, padx=1, pady=1, sticky='nsew')
                self.squares[r][c] = btn

        for i in range(self.board_size):
            self.board_frame.grid_rowconfigure(i, weight=1, uniform='chess_rows')
            self.board_frame.grid_columnconfigure(i, weight=1, uniform='chess_cols')

    def on_window_resize(self, event):
        board_height = self.board_container.winfo_height()
        if board_height > 0:
            new_size = max(10, min(35, int(board_height / 20)))
            
            for r in range(self.board_size):
                for c in range(self.board_size):
                    self.squares[r][c].config(font=('Arial', new_size))

    def is_white_piece(self, piece):
        return piece.isupper() and piece != '.'

    def is_black_piece(self, piece):
        return piece.islower() and piece != '.'

    def get_piece_color(self, piece):
        if piece == '.':
            return None
        return 'white' if piece.isupper() else 'black'

    def is_valid_position(self, row, col):
        return 0 <= row < self.board_size and 0 <= col < self.board_size

    def get_piece_moves(self, row, col, include_king_safety=True):
        piece = self.board[row][col]
        if piece == '.':
            return []

        piece_type = piece.lower()
        moves = []

        if piece_type == 'p':
            moves = self.get_pawn_moves(row, col)
        elif piece_type == 'r':
            moves = self.get_rook_moves(row, col)
        elif piece_type == 'n':
            moves = self.get_knight_moves(row, col)
        elif piece_type == 'b':
            moves = self.get_bishop_moves(row, col)
        elif piece_type == 'q':
            moves = self.get_queen_moves(row, col)
        elif piece_type == 'k':
            moves = self.get_king_moves(row, col, include_king_safety)

        if include_king_safety and piece_type != 'k':
            legal_moves = []
            for move in moves:
                if self.is_legal_move(row, col, move[0], move[1]):
                    legal_moves.append(move)
            return legal_moves

        return moves

    def get_pawn_moves(self, row, col):
        moves = []
        piece = self.board[row][col]
        is_white = self.is_white_piece(piece)
        direction = -1 if is_white else 1
        start_row = self.board_size - 1 if is_white else 0

        new_row = row + direction
        if self.is_valid_position(new_row, col) and self.board[new_row][col] == '.':
            moves.append((new_row, col))
            
            if row == start_row and self.board[new_row + direction][col] == '.':
                moves.append((new_row + direction, col))

        for dc in [-1, 1]:
            new_col = col + dc
            if self.is_valid_position(new_row, new_col):
                target = self.board[new_row][new_col]
                if target != '.' and self.get_piece_color(target) != self.get_piece_color(piece):
                    moves.append((new_row, new_col))

        if self.en_passant_target:
            ep_row, ep_col = self.en_passant_target
            if row == ep_row and abs(col - ep_col) == 1:
                if self.is_valid_position(ep_row + direction, ep_col):
                    moves.append((ep_row + direction, ep_col))

        return moves

    def get_rook_moves(self, row, col):
        moves = []
        directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]
        
        for dr, dc in directions:
            for i in range(1, self.board_size):
                new_row, new_col = row + dr * i, col + dc * i
                if not self.is_valid_position(new_row, new_col):
                    break
                
                target = self.board[new_row][new_col]
                if target == '.':
                    moves.append((new_row, new_col))
                else:
                    if self.get_piece_color(target) != self.get_piece_color(self.board[row][col]):
                        moves.append((new_row, new_col))
                    break
        
        return moves

    def get_knight_moves(self, row, col):
        moves = []
        knight_moves = [(-2, -1), (-2, 1), (-1, -2), (-1, 2), 
                       (1, -2), (1, 2), (2, -1), (2, 1)]
        
        for dr, dc in knight_moves:
            new_row, new_col = row + dr, col + dc
            if self.is_valid_position(new_row, new_col):
                target = self.board[new_row][new_col]
                if target == '.' or self.get_piece_color(target) != self.get_piece_color(self.board[row][col]):
                    moves.append((new_row, new_col))
        
        return moves

    def get_bishop_moves(self, row, col):
        moves = []
        directions = [(-1, -1), (-1, 1), (1, -1), (1, 1)]
        
        for dr, dc in directions:
            for i in range(1, self.board_size):
                new_row, new_col = row + dr * i, col + dc * i
                if not self.is_valid_position(new_row, new_col):
                    break
                
                target = self.board[new_row][new_col]
                if target == '.':
                    moves.append((new_row, new_col))
                else:
                    if self.get_piece_color(target) != self.get_piece_color(self.board[row][col]):
                        moves.append((new_row, new_col))
                    break
        
        return moves

    def get_queen_moves(self, row, col):
        return self.get_rook_moves(row, col) + self.get_bishop_moves(row, col)

    def get_king_moves(self, row, col, include_king_safety=True):
        moves = []
        king_moves = [(-1, -1), (-1, 0), (-1, 1), (0, -1), 
                     (0, 1), (1, -1), (1, 0), (1, 1)]
        
        piece = self.board[row][col]
        piece_color = self.get_piece_color(piece)
        enemy_color = 'black' if piece_color == 'white' else 'white'
        
        for dr, dc in king_moves:
            new_row, new_col = row + dr, col + dc
            if self.is_valid_position(new_row, new_col):
                target = self.board[new_row][new_col]
                if target == '.' or self.get_piece_color(target) != piece_color:
                    if not include_king_safety or not self.is_square_attacked_simple(new_row, new_col, enemy_color):
                        moves.append((new_row, new_col))
        
        # Simplified castling for 6x6 (only kingside)
        if include_king_safety:
            is_white = self.is_white_piece(piece)
            if not self.is_in_check_simple(piece_color):
                if is_white and not self.white_king_moved and not self.white_rook_moved['right']:
                    if self.board[5][4] == '.' and not self.is_square_attacked_simple(5, 4, 'black'):
                        moves.append((5, 4))
                elif not is_white and not self.black_king_moved and not self.black_rook_moved['right']:
                    if self.board[0][4] == '.' and not self.is_square_attacked_simple(0, 4, 'white'):
                        moves.append((0, 4))
        
        return moves

    def is_square_attacked_simple(self, row, col, by_color):
        for r in range(self.board_size):
            for c in range(self.board_size):
                piece = self.board[r][c]
                if piece != '.' and self.get_piece_color(piece) == by_color:
                    if self.can_piece_attack_square(r, c, row, col):
                        return True
        return False

    def can_piece_attack_square(self, piece_row, piece_col, target_row, target_col):
        piece = self.board[piece_row][piece_col]
        piece_type = piece.lower()
        
        row_diff = target_row - piece_row
        col_diff = target_col - piece_col
        
        if piece_type == 'p':
            is_white = self.is_white_piece(piece)
            direction = -1 if is_white else 1
            return row_diff == direction and abs(col_diff) == 1
            
        elif piece_type == 'r':
            if row_diff == 0 or col_diff == 0:
                return self.is_path_clear(piece_row, piece_col, target_row, target_col)
            
        elif piece_type == 'n':
            return (abs(row_diff) == 2 and abs(col_diff) == 1) or (abs(row_diff) == 1 and abs(col_diff) == 2)
            
        elif piece_type == 'b':
            if abs(row_diff) == abs(col_diff):
                return self.is_path_clear(piece_row, piece_col, target_row, target_col)
            
        elif piece_type == 'q':
            if row_diff == 0 or col_diff == 0 or abs(row_diff) == abs(col_diff):
                return self.is_path_clear(piece_row, piece_col, target_row, target_col)
            
        elif piece_type == 'k':
            return abs(row_diff) <= 1 and abs(col_diff) <= 1 and (row_diff != 0 or col_diff != 0)
        
        return False

    def is_path_clear(self, from_row, from_col, to_row, to_col):
        row_diff = to_row - from_row
        col_diff = to_col - from_col
        
        row_step = 0 if row_diff == 0 else (1 if row_diff > 0 else -1)
        col_step = 0 if col_diff == 0 else (1 if col_diff > 0 else -1)
        
        current_row, current_col = from_row + row_step, from_col + col_step
        
        while (current_row, current_col) != (to_row, to_col):
            if self.board[current_row][current_col] != '.':
                return False
            current_row += row_step
            current_col += col_step
        
        return True

    def is_in_check_simple(self, color):
        king_pos = self.find_king(color)
        if not king_pos:
            return False
        
        enemy_color = 'black' if color == 'white' else 'white'
        return self.is_square_attacked_simple(king_pos[0], king_pos[1], enemy_color)

    def find_king(self, color):
        king = 'K' if color == 'white' else 'k'
        for r in range(self.board_size):
            for c in range(self.board_size):
                if self.board[r][c] == king:
                    return (r, c)
        return None

    def is_legal_move(self, from_row, from_col, to_row, to_col):
        original_piece = self.board[to_row][to_col]
        moving_piece = self.board[from_row][from_col]
        
        self.board[to_row][to_col] = moving_piece
        self.board[from_row][from_col] = '.'
        
        piece_color = self.get_piece_color(moving_piece)
        in_check = self.is_in_check_simple(piece_color)
        
        self.board[from_row][from_col] = moving_piece
        self.board[to_row][to_col] = original_piece
        
        return not in_check

    def is_checkmate(self, color):
        if not self.is_in_check_simple(color):
            return False
        
        for r in range(self.board_size):
            for c in range(self.board_size):
                piece = self.board[r][c]
                if piece != '.' and self.get_piece_color(piece) == color:
                    moves = self.get_piece_moves(r, c)
                    if moves:
                        return False
        
        return True

    def is_stalemate(self, color):
        if self.is_in_check_simple(color):
            return False
        
        for r in range(self.board_size):
            for c in range(self.board_size):
                piece = self.board[r][c]
                if piece != '.' and self.get_piece_color(piece) == color:
                    moves = self.get_piece_moves(r, c)
                    if moves:
                        return False
        
        return True

    def is_insufficient_material(self):
        pieces = {'white': [], 'black': []}
        
        for r in range(self.board_size):
            for c in range(self.board_size):
                piece = self.board[r][c]
                if piece != '.':
                    color = self.get_piece_color(piece)
                    pieces[color].append(piece.lower())
        
        if len(pieces['white']) == 1 and len(pieces['black']) == 1:
            return True
        
        for color in ['white', 'black']:
            other = 'black' if color == 'white' else 'white'
            if (len(pieces[color]) == 2 and len(pieces[other]) == 1 and
                ('b' in pieces[color] or 'n' in pieces[color])):
                return True
        
        return False

    def get_promotion_piece(self, is_white):
        dialog = tk.Toplevel(self.root)
        dialog.title("Pawn Promotion")
        dialog.transient(self.root)
        dialog.grab_set()
        
        pieces = ['Queen', 'Rook', 'Bishop', 'Knight']
        piece_var = tk.StringVar(value='Queen')
        
        tk.Label(dialog, text="Choose promotion piece:", font=('Arial', 12)).pack(pady=10)
        
        for piece in pieces:
            tk.Radiobutton(dialog, text=piece, variable=piece_var, value=piece, font=('Arial', 10)).pack(anchor='w', padx=20)
        
        tk.Button(dialog, text="Confirm", command=dialog.destroy, font=('Arial', 10)).pack(pady=10)
        
        self.root.wait_window(dialog)
        
        piece_map = {'Queen': 'Q', 'Rook': 'R', 'Bishop': 'B', 'Knight': 'N'}
        selected = piece_map[piece_var.get()]
        return selected if is_white else selected.lower()

    def make_move(self, from_row, from_col, to_row, to_col):
        if self.game_over:
            return False
        
        piece = self.board[from_row][from_col]
        captured_piece = self.board[to_row][to_col]
        
        move_data = {
            'from': (from_row, from_col),
            'to': (to_row, to_col),
            'piece': piece,
            'captured': captured_piece,
            'en_passant_target': self.en_passant_target,
            'castling_rights': {
                'white_king_moved': self.white_king_moved,
                'black_king_moved': self.black_king_moved,
                'white_rook_moved': self.white_rook_moved.copy(),
                'black_rook_moved': self.black_rook_moved.copy()
            },
            'fifty_move_counter': self.fifty_move_counter
        }
        
        self.en_passant_target = None
        
        piece_type = piece.lower()
        
        if piece_type == 'p':
            self.fifty_move_counter = 0
            
            if abs(from_row - to_row) == 2:
                self.en_passant_target = (from_row + (to_row - from_row) // 2, from_col)
            
            elif from_col != to_col and captured_piece == '.':
                captured_row = from_row
                self.board[captured_row][to_col] = '.'
                move_data['en_passant_captured'] = self.board[captured_row][to_col]
            
            elif (to_row == 0 and self.is_white_piece(piece)) or (to_row == self.board_size - 1 and self.is_black_piece(piece)):
                if self.current_turn == self.player_side:
                    piece = self.get_promotion_piece(self.is_white_piece(piece))
                else:
                    piece = 'Q' if self.is_white_piece(piece) else 'q'
                move_data['promotion'] = piece
        
        elif piece_type == 'k':
            if self.is_white_piece(piece):
                self.white_king_moved = True
                if from_col == 3 and to_col == 4:  # Kingside castling
                    self.board[5][3] = self.board[5][5]
                    self.board[5][5] = '.'
                    move_data['castling'] = 'kingside'
            else:
                self.black_king_moved = True
                if from_col == 3 and to_col == 4:  # Kingside castling
                    self.board[0][3] = self.board[0][5]
                    self.board[0][5] = '.'
                    move_data['castling'] = 'kingside'
        
        elif piece_type == 'r':
            if self.is_white_piece(piece):
                if from_row == 5 and from_col == 0:
                    self.white_rook_moved['left'] = True
                elif from_row == 5 and from_col == 5:
                    self.white_rook_moved['right'] = True
            else:
                if from_row == 0 and from_col == 0:
                    self.black_rook_moved['left'] = True
                elif from_row == 0 and from_col == 5:
                    self.black_rook_moved['right'] = True
        
        if captured_piece != '.' or piece_type == 'p':
            self.fifty_move_counter = 0
        else:
            self.fifty_move_counter += 1
        
        self.board[to_row][to_col] = piece
        self.board[from_row][from_col] = '.'
        
        self.move_history.append(move_data)
        
        self.current_turn = 'black' if self.current_turn == 'white' else 'white'
        self.last_move = (from_row, from_col, to_row, to_col)
        
        return True

    def undo_move(self):
        if not self.move_history:
            return False
        
        move_data = self.move_history.pop()
        from_row, from_col = move_data['from']
        to_row, to_col = move_data['to']
        
        self.board[from_row][from_col] = move_data['piece']
        self.board[to_row][to_col] = move_data['captured']
        
        if 'en_passant_captured' in move_data:
            self.board[from_row][to_col] = move_data['en_passant_captured']
        
        if 'castling' in move_data:
            if move_data['castling'] == 'kingside':
                if self.is_white_piece(move_data['piece']):
                    self.board[5][5] = self.board[5][3]
                    self.board[5][3] = '.'
                else:
                    self.board[0][5] = self.board[0][3]
                    self.board[0][3] = '.'
        
        self.en_passant_target = move_data['en_passant_target']
        self.white_king_moved = move_data['castling_rights']['white_king_moved']
        self.black_king_moved = move_data['castling_rights']['black_king_moved']
        self.white_rook_moved = move_data['castling_rights']['white_rook_moved']
        self.black_rook_moved = move_data['castling_rights']['black_rook_moved']
        self.fifty_move_counter = move_data['fifty_move_counter']
        
        self.current_turn = 'white' if self.current_turn == 'black' else 'black'
        self.game_over = False
        
        self.update_board()
        self.update_status()
        return True

    def on_click(self, row, col):
        if self.game_over:
            return
        
        if (self.current_turn == 'white') != (self.player_side == 'white'):
            return
        
        if self.selected_square is None:
            piece = self.board[row][col]
            if piece != '.' and self.get_piece_color(piece) == self.current_turn:
                self.selected_square = (row, col)
                self.update_board()
        else:
            from_row, from_col = self.selected_square
            
            if (row, col) == self.selected_square:
                self.selected_square = None
                self.update_board()
            elif self.board[row][col] != '.' and self.get_piece_color(self.board[row][col]) == self.current_turn:
                self.selected_square = (row, col)
                self.update_board()
            else:
                legal_moves = self.get_piece_moves(from_row, from_col)
                if (row, col) in legal_moves:
                    self.make_move(from_row, from_col, row, col)
                    self.selected_square = None
                    self.update_board()
                    self.update_status()
                    self.check_game_end()
                    
                    if not self.game_over and self.current_turn != self.player_side:
                        self.root.after(500, self.ai_move)
                else:
                    self.selected_square = None
                    self.update_board()

    def check_game_end(self):
        current_color = self.current_turn
        
        if self.is_checkmate(current_color):
            winner = 'Black' if current_color == 'white' else 'White'
            self.status_label.config(text=f"Checkmate! {winner} wins!")
            self.game_over = True
        elif self.is_stalemate(current_color):
            self.status_label.config(text="Stalemate! Draw!")
            self.game_over = True
        elif self.fifty_move_counter >= 100:
            self.status_label.config(text="Draw by 50-move rule!")
            self.game_over = True
        elif self.is_insufficient_material():
            self.status_label.config(text="Draw by insufficient material!")
            self.game_over = True

    def update_board(self):
        for r in range(self.board_size):
            for c in range(self.board_size):
                btn = self.squares[r][c]
                piece = self.board[r][c]
                
                bg_color = '#f0d9b5' if (r + c) % 2 == 0 else '#b58863'
                
                if self.selected_square and self.selected_square == (r, c):
                    bg_color = '#FFFF00'
                
                if self.selected_square:
                    from_row, from_col = self.selected_square
                    legal_moves = self.get_piece_moves(from_row, from_col)
                    if (r, c) in legal_moves:
                        bg_color = '#90EE90'
                
                if self.last_move:
                    from_r, from_c, to_r, to_c = self.last_move
                    if (r, c) == (from_r, from_c) or (r, c) == (to_r, to_c):
                        bg_color = '#FFD700'
                
                if self.is_in_check_simple(self.current_turn):
                    king_pos = self.find_king(self.current_turn)
                    if king_pos and (r, c) == king_pos:
                        bg_color = '#FF6B6B'
                
                btn.config(text=self.PIECES.get(piece, ''), bg=bg_color)

    def update_status(self):
        if self.game_over:
            return
        
        status = f"{self.current_turn.title()}'s turn"
        if self.is_in_check_simple(self.current_turn):
            status += " - CHECK!"
        
        self.status_label.config(text=status)
        
        if self.move_history:
            recent_moves = self.move_history[-5:]
            history_text = "Recent moves: " + ", ".join([
                f"{self.square_to_notation(move['from'])}-{self.square_to_notation(move['to'])}" 
                for move in recent_moves
            ])
            self.history_label.config(text=history_text)

    def square_to_notation(self, pos):
        row, col = pos
        return chr(ord('a') + col) + str(self.board_size - row)

    def ai_move(self):
        if self.game_over or self.current_turn == self.player_side:
            return
        
        move = self.minimax(2, self.current_turn, -float('inf'), float('inf'))[1]
        if move:
            from_r, from_c, to_r, to_c = move
            self.make_move(from_r, from_c, to_r, to_c)
            self.update_board()
            self.update_status()
            self.check_game_end()

    def minimax(self, depth, color, alpha, beta):
        if depth == 0 or self.is_checkmate(color) or self.is_stalemate(color) or self.is_insufficient_material():
            return self.evaluate_board(), None
        
        best_move = None
        if color == self.current_turn:
            max_eval = -float('inf')
            moves = self.get_all_moves(color)
            for move in moves:
                from_r, from_c, to_r, to_c = move
                original_piece = self.board[to_r][to_c]
                moving_piece = self.board[from_r][from_col]
                
                self.board[to_r][to_c] = moving_piece
                self.board[from_r][from_c] = '.'
                eval_score = self.minimax(depth - 1, 'black' if color == 'white' else 'white', alpha, beta)[0]
                
                self.board[from_r][from_c] = moving_piece
                self.board[to_r][to_c] = original_piece
                
                if eval_score > max_eval:
                    max_eval = eval_score
                    best_move = move
                alpha = max(alpha, eval_score)
                if beta <= alpha:
                    break
            return max_eval, best_move
        else:
            min_eval = float('inf')
            moves = self.get_all_moves(color)
            for move in moves:
                from_r, from_c, to_r, to_c = move
                original_piece = self.board[to_r][to_c]
                moving_piece = self.board[from_r][from_c]
                
                self.board[to_r][to_c] = moving_piece
                self.board[from_r][from_c] = '.'
                eval_score = self.minimax(depth - 1, 'black' if color == 'white' else 'white', alpha, beta)[0]
                
                self.board[from_r][from_c] = moving_piece
                self.board[to_r][to_c] = original_piece
                
                if eval_score < min_eval:
                    min_eval = eval_score
                    best_move = move
                beta = min(beta, eval_score)
                if beta <= alpha:
                    break
            return min_eval, best_move

    def evaluate_board(self):
        piece_values = {'p': 1, 'n': 3, 'b': 3, 'r': 5, 'q': 9, 'k': 100}
        score = 0
        
        for r in range(self.board_size):
            for c in range(self.board_size):
                piece = self.board[r][c]
                if piece != '.':
                    value = piece_values.get(piece.lower(), 0)
                    if self.is_white_piece(piece):
                        score += value
                        if 1 <= r <= 4 and 1 <= c <= 4:  # Center control
                            score += 0.5
                    else:
                        score -= value
                        if 1 <= r <= 4 and 1 <= c <= 4:
                            score -= 0.5
        
        if self.is_checkmate('white'):
            score -= 1000
        elif self.is_checkmate('black'):
            score += 1000
        
        return score

    def get_all_moves(self, color):
        moves = []
        for r in range(self.board_size):
            for c in range(self.board_size):
                piece = self.board[r][c]
                if piece != '.' and self.get_piece_color(piece) == color:
                    piece_moves = self.get_piece_moves(r, c)
                    for move in piece_moves:
                        moves.append((r, c, move[0], move[1]))
        return moves

    def new_game(self):
        self.reset_game()
        self.update_board()
        self.update_status()
        
        if self.player_side == 'black':
            self.root.after(1000, self.ai_move)

    def switch_side(self):
        self.player_side = 'black' if self.player_side == 'white' else 'white'
        self.new_game()

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    game = ChessVsAI()
    game.run()