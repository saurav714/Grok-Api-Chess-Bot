♟️ Chess vs AI with LLM
A Python-based chess application featuring a powerful AI opponent driven by the Ollama language model, with a fallback to the Stockfish chess engine. Enjoy an interactive GUI, move suggestions, game review tools, and various play modes — all packed into one simple yet robust chess interface.

🚀 Features
♟️ Game Interface
Interactive Chess Board: Tkinter-based GUI with click-to-move support.

Responsive Design: Automatically resizes to fit your screen.

Pawn Promotion Dialog: Choose from Queen, Rook, Knight, or Bishop.

🧠 AI Opponents
Primary AI: Move generation using Ollama LLM.

Fallback AI: Stockfish engine for precise, fast evaluations.

Random Move Generator: Ensures playability when AI fails.

📊 Game Analysis
Real-time Evaluation Bar (requires Stockfish).

Move History: Displayed in Standard Algebraic Notation (SAN).

Review Mode: Step-by-step move analysis with identification of blunders, mistakes, and best moves.

🕹️ Game Modes
Play as White or Black.

Switch Sides, Undo Moves, or Resign anytime.

Test AI Mode: Run simulations to evaluate AI performance.

🧰 Additional Features
Transposition table to cache repeated positions.

Check, checkmate, stalemate, and other draw condition detection.

User-friendly error handling for missing dependencies or engine failures.

📦 Requirements
Python 3.7+

Install dependencies:

bash
Copy
Edit
pip install python-chess ollama python-dotenv
Optional: Download Stockfish and note the path to the binary.

⚙️ Installation
Clone the repository:

bash
Copy
Edit
git clone https://github.com/your-username/chess-vs-ai.git
cd chess-vs-ai
Install dependencies:

bash
Copy
Edit
pip install -r requirements.txt
(Optional) Install Stockfish:

Download the binary for your OS.

Create a .env file in the project root:

ini
Copy
Edit
STOCKFISH_PATH=/path/to/stockfish
OLLAMA_MODEL=phi3
OLLAMA_TIMEOUT=5.0
Run the application:

bash
Copy
Edit
python chess_vs_ai.py
🛠️ Configuration
Edit or create a .env file in the root directory:

ini
Copy
Edit
STOCKFISH_PATH=/absolute/path/to/stockfish
OLLAMA_MODEL=phi3
OLLAMA_TIMEOUT=5.0
STOCKFISH_PATH: Path to Stockfish binary (optional but recommended).

OLLAMA_MODEL: Ollama model name (default: phi3).

OLLAMA_TIMEOUT: Response timeout in seconds.

🧩 Usage
Once launched:

🎮 New Game: Start fresh.

⚪/⚫ Switch Side: Play as White or Black.

↩️ Undo Move: Undo last one/two moves.

🏳️ Resign: End the game.

🧪 Test AI: Simulate 3 AI games.

Click a piece, then click a destination to move. Legal moves are highlighted. Enter Review Mode after the game to navigate through each move and evaluation.

⚙️ How It Works
GUI: Built with Tkinter using Unicode chess symbols on an 8x8 grid.

AI Logic:

Tries to generate a move using Ollama based on FEN.

Falls back to Stockfish (if set), or a random move.

Caches AI responses for repeated board states.

Evaluation: Stockfish provides evaluations and is essential for game review insights.

❗ Limitations
Requires local Ollama server running.

Stockfish recommended for serious play and reviews.

No online multiplayer or save/load features (yet).

Ollama model strength and response time may vary.

🧩 Troubleshooting
Issue	Fix
Stockfish not found	Check STOCKFISH_PATH in .env.
Ollama errors	Ensure Ollama server is running and OLLAMA_MODEL exists.
GUI problems	Resize window or verify Tkinter is installed.
Missing packages	Run pip install python-chess ollama python-dotenv.

🤝 Contributing
Fork the repo

Create a feature branch

Submit a pull request with a clear description

Please follow PEP 8 and ensure proper error handling.

📄 License
MIT License — See the LICENSE file for details.

🙏 Acknowledgments
python-chess

Ollama

Stockfish

Unicode symbols for clean board visuals

Let me know if you'd like a badge section, logo/banner, or GitHub Actions CI workflow included too.
