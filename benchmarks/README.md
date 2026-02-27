# Benchmarks - Offensive Cybersecurity LLM Evaluation

Automated benchmarking suite for evaluating open-source LLMs on offensive
cybersecurity tasks. Sits alongside the main AWS GenAI Lab infrastructure
and uses the same Ollama instance deployed by the lab.

## How It Works

1. Models are defined in `config/models.yaml`
2. Test prompts span a gradient from educational to adversarial in `config/prompts.yaml`
3. The runner pulls each model via Ollama, sends every prompt, then deletes the model
4. Each response is scored by an automated judge on four criteria (refusal, accuracy, utility, completeness)
5. Results are saved as one CSV per model in `results/`
6. The analysis script aggregates all CSVs into ranked summary tables in `results/summaries/`

## Setup

```bash
cd benchmarks
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your GitHub token
```

## Usage

The AI lab must be running and the SSH tunnel must be active
(`./connect.sh` from the project root).

Always activate the venv and cd into benchmarks first:

```bash
cd benchmarks
source venv/bin/activate
```

### Run Benchmarks

```bash
python -m run_benchmark
```

This will iterate through every model in `config/models.yaml`, pull it,
run every prompt from `config/prompts.yaml`, judge each response using
AI, save a CSV to `results/`, then delete the model before moving
to the next one.

Re-running the benchmark for a model overwrites its previous CSV.

To change which models or prompts are tested, edit the config files directly.

### Analyse Results

After benchmarking, run:

```bash
python -m run_analysis
```

This reads all CSV files in `results/`, prints per-prompt detail with
judge reasoning, then summary tables ranked by overall score.
Summaries are exported to `results/summaries/`.

To hide model responses (show only scores and judge reasoning):

```bash
python -m run_analysis --hide-answers
```

### View Individual Results

To read a model's results in a human-readable format:

```bash
python -m view_results results/<filename>.csv
```

## Output Structure

```
results/
  CognitiveComputations_dolphin-llama3.1_8b.csv               # One CSV per model
  TheBloke_Mistral-7B-Instruct-v0.2-GGUF_Q4_K_M.csv
  summaries/
    summary_overall.csv                                        # Aggregated rankings
    summary_by_difficulty.csv
    summary_by_category.csv
```