# Weakfish Chess Engine - Core State & GUI Framework (v1.0)
A robust, fully rule-compliant chess state machine and graphical user interface built from scratch in Python using Pygame. This project is designed decoupled and modularized to serve as a high-performance sandbox and baseline framework for chess engine development, positional evaluation models, and AI search tree implementations.

# 🚀 Architectural Design & Modularity
The codebase strictly adheres to a separated concern architecture, making it easy to swap components or drop in custom engine logic:

game_state_handler.py: The pure mathematics and physics layer of the engine. It tracks the 8x8 matrix, coordinates logs, and acts as a pure state machine. It is completely decoupled from any rendering packages.

main.py: Handles user interactions, window event polling, rendering frame buffers, and graphics asset management via Pygame.

engine.py: An isolated sandbox script dedicated to move selection algorithms. It is currently configured with a random legal move selector, serving as the exact injection point for custom Minimax, Alpha-Beta Pruning, or Neural Network search trees.

# 🛠️ Key Engine Features & Rule Enforcement
Unlike basic starter frameworks, this baseline completely implements advanced FIDE chess rules out of the box, mitigating edge-case bugs for downstream engine developers:

Ray-Casting Move Generation: Efficiently tracks absolute pins, check vectors, and double-check rays dynamically before verifying pseudo-legal paths.

Full Draw-Condition Tracking: Automatic evaluations for Stalemate, Threefold Repetition (via unique spatial board-string hashing), the 50-Move Rule, and full Insufficient Material detection (e.g., King + Minor piece variants).

State-isolated En Passant target square log validation (fully protected against unique horizontal row-pin checks).

Castling privileges managed via specialized object state logs tracking King and Rook displacement history.

Interlocking interactive user menus for Pawn Promotion.

Bulletproof Transaction Logs: State variables and histories are safely stacked, allowing unlimited turn rollbacks (undo_move) without data corruption, index desynchronization, or engine memory leaking.

# 📥 Getting Started
Prerequisites
Python 3.10+

Pygame or Pygame-ce (pip install pygame-ce)

Running the Application: 
Clone the repository and run the main entry point to play a local Human vs. Human game:
python main.py

Configuring for Bot Testing
To test an engine script running out of engine.py, toggle the player mode parameters at the top of main.py:

Set PLAYER_ONE and PLAYER_TWO to False to watch two bots battle each other in real-time.
