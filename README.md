Chess vs AI with LLM
Overview
This is a Python-based chess application that allows users to play against an AI opponent powered by either the Stockfish chess engine or the Ollama language model. The game features a graphical user interface (GUI) built with Tkinter, move history, position evaluation, and game review capabilities. Players can choose to play as either White or Black, switch sides, undo moves, resign, or test the AI's performance.
Features

Interactive Chess Board: A Tkinter-based GUI with a responsive chess board that supports piece movement via clicks.
AI Opponents:
Primary AI: Ollama language model for move generation.
Fallback AI: Stockfish chess engine (configurable).
Random move generator as a last resort.


Game Analysis:
Real-time position evaluation with an evaluation bar.
Move history display with Standard Algebraic Notation (SAN).
Analysis of moves in review mode, highlighting blunders, mistakes, and inaccuracies.


Game Modes:
Play as White or Black.
Review mode to analyze past games move-by-move.
Test AI mode to simulate multiple games and evaluate performance.


Additional Features:
Move undo functionality.
Resign option.
Responsive board resizing.
Pawn promotion dialog.
Check, checkmate, stalemate, and other draw condition detection.
Transposition table to cache AI moves for efficiency.



Requirements
To run the application, you need the following dependencies:

Python 3.7 or higher
Required Python packages:
python-chess: For chess logic and board management.
ollama: For AI move generation using the Ollama language model.
python-dotenv: For loading environment variables.


Stockfish chess engine (optional, for fallback AI):
Download the appropriate Stockfish binary for your system from https://stockfishchess.org/download/.
Specify the path to the Stockfish executable in the .env file or ensure it is in the default path.



Install the required Python packages using:
pip install python-chess ollama python-dotenv

Installation

Clone or download this repository to your local machine.
Ensure Python 3.7+ is installed.
Install the required dependencies:pip install -r requirements.txt

Alternatively, install individually as shown above.
(Optional) Install Stockfish:
Download the Stockfish binary and note its path.
Create a .env file in the project root (see Configuration section).


Run the application:python chess_vs_ai.py



Configuration
The application uses a .env file to configure the Stockfish path and Ollama settings. Create a .env file in the project root with the following optional variables:
STOCKFISH_PATH=/path/to/stockfish
OLLAMA_MODEL=phi3
OLLAMA_TIMEOUT=5.0


STOCKFISH_PATH: Path to the Stockfish executable (e.g., C:\Users\HP\Desktop\stockfish.exe on Windows).
OLLAMA_MODEL: The Ollama model to use (default: phi3).
OLLAMA_TIMEOUT: Timeout for Ollama responses in seconds (default: 5.0).

If the .env file is missing or variables are not set, the application will use default values.
Usage

Launch the application by running:python chess_vs_ai.py


The GUI will display a chess board with the following controls:
New Game: Start a new game.
Switch Side: Toggle between playing as White or Black.
Undo Move: Undo the last move (or last two moves if AI has responded).
Resign: Concede the game.
Test AI: Run a simulation of three games to test AI performance.


Click on a piece to select it, then click a target square to move. Legal moves are highlighted.
If a pawn reaches the last rank, a promotion dialog will appear to choose a piece (Queen, Rook, Knight, or Bishop).
After the game ends, enter Review Mode to analyze moves with evaluations and suggested best moves.
In Review Mode, use Previous and Next buttons to navigate through moves, or Exit Review to return to normal mode.

How It Works

GUI: Built with Tkinter, the board is an 8x8 grid of buttons that display chess pieces using Unicode symbols. The board is responsive and adjusts to window resizing.
AI Move Generation:
The application first attempts to get a move from the Ollama model using the current board's FEN (Forsyth-Edwards Notation).
If Ollama fails or provides an invalid move, it falls back to Stockfish (if available) or a random legal move.
A transposition table caches Ollama moves to improve performance for repeated positions.


Evaluation: Stockfish provides position evaluations (if available), displayed in an evaluation bar and used to identify blunders, mistakes, and inaccuracies.
Review Mode: Allows post-game analysis with move-by-move navigation, showing evaluations and suggested best moves.
Error Handling: The application gracefully handles missing dependencies, invalid moves, and engine failures.

Limitations

Requires an active Ollama server running locally for AI move generation. Ensure the Ollama service is running before starting the application.
Stockfish is optional but recommended for better AI performance and accurate evaluations. Without Stockfish, the AI may rely on random moves if Ollama fails.
The application does not support online multiplayer or saving/loading games.
The AI's strength depends on the Ollama model and Stockfish configuration (e.g., depth and time limits).

Troubleshooting

Stockfish not found: Ensure the STOCKFISH_PATH in the .env file points to a valid Stockfish executable.
Ollama errors: Verify that the Ollama server is running and the specified model (e.g., phi3) is available.
Missing dependencies: Install required packages using pip install python-chess ollama python-dotenv.
GUI issues: Ensure Tkinter is available (it comes with standard Python installations). If the board doesn't display correctly, try resizing the window.

Contributing
Contributions are welcome! To contribute:

Fork the repository.
Create a new branch for your feature or bug fix.
Submit a pull request with a clear description of changes.

Please ensure code follows PEP 8 style guidelines and includes appropriate error handling.
License
This project is licensed under the MIT License. See the LICENSE file for details.
Acknowledgments

python-chess for chess logic and engine integration.
Ollama for AI move generation.
Stockfish for strong chess engine support.
Unicode chess symbols for visual representation.
