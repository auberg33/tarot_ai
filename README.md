# AlphaTarot: Hybrid AI Engine for 4-Player French Tarot

AlphaTarot is an advanced artificial intelligence engine designed to master the 4-player game of French Tarot, a highly complex imperfect-information environment with a massive state space.

## Project History & Contributions

This project was built in two distinct phases, showcasing both collaborative engineering and advanced solo AI research:

* **Phase 1: The Foundation (Academic Project PE 49):** The project originated as a 6-person engineering group project at **École Centrale de Lyon**. The team successfully developed the core Tarot rules engine, the baseline expert heuristic (`IA_2`), and a web interface (not included in this AI-focused repository). My personal contribution during this phase was the initial design and implementation of the Monte Carlo Tree Search (MCTS) algorithm. This collective effort was awarded the **Prix Francis Leboeuf** for the best study project of the year amongst 100.
* **Phase 2: The Deep Learning Overhaul (Solo Research):** Driven by newly acquired expertise in modern Artificial Intelligence, I recently returned to the project solo to completely redesign the engine. I implemented the Deep Learning components (Transformers, Value MLP), the PyTorch GPU inference pipeline, and upgraded the MCTS to an AlphaZero-style architecture to create the current "Hybrid Brain."

## Hybrid Brain Architecture

To overcome the challenges of hidden information and deep combinatorics, this engine bridges the gap between classic expert heuristics and modern Deep Learning architectures:

1. **TarotFormer (Belief Network):** A Transformer-based architecture. By analyzing the history of tricks played and the agent's current hand, it infers a probabilistic distribution of the hidden cards held by opponents or left in the "dog" (écart).
2. **TarotValueMLP (Value Network):** A Multi-Layer Perceptron (MLP) trained to instantly evaluate a given board state (cards played, current contract, declarer) and predict the continuous margin of victory, bypassing the need for full terminal rollouts.
3. **Biased MCTS (AlphaZero-style):** A Monte Carlo Tree Search algorithm that simulates parallel universes based on the TarotFormer's card distribution. It integrates a **Policy Prior** derived from the team's hardcoded expert heuristic (`IA_2`) to aggressively prune the search tree in early nodes, which is then refined by the UCB1 algorithm and the TarotValueMLP evaluations.

## Data Pipeline & Processing

The models were trained using a custom data pipeline:
* Built with **Python, SQLAlchemy, and Pandas**.
* Capable of parsing complex, multi-block CSV datasets containing hundreds of thousands of historical 4-player Tarot games to extract precise game states and database structures.

## Installation

**Prerequisites:** Python 3.9+ and a CUDA-compatible GPU (highly recommended to leverage PyTorch 2.0+ compilation).

```bash
# Clone the repository
git clone [https://github.com/auberg33/tarot-ai-alphazero.git](https://github.com/auberg33/tarot-ai-alphazero.git)
cd tarot-ai-alphazero

# Install dependencies
pip install -r requirements.txt
```

## Usage

To launch a duplicate tournament or test the engine in a local game:

```bash
python main.py
```

*Hardware Optimization:* The engine automatically detects GPU availability and attempts a PyTorch compilation (`torch.compile`) utilizing Triton on Linux environments to drastically reduce batch inference overhead. Standard Eager mode is used as a fallback on Windows.

## Tech Stack

* **Language:** Python 3
* **Deep Learning:** PyTorch (Transformers, MLP, torch.compile, GPU Batching)
* **Data Processing:** NumPy, Pandas, SQLAlchemy
* **Algorithms:** MCTS, MinMax with Alpha-Beta Pruning, Softmax Sampling with Temperature, UCB1

## [Demo with the website](https://www.youtube.com/watch?v=roY9kAKXQnM)

## Author

**Guilhem Conter**  
*Engineering Student specializing in Machine Learning & Decision Algorithms at École Centrale de Lyon.*
