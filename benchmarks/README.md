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

## Benchmarking Un-aligned Models (Representation Engineering)

Activation steering modifies the model's hidden states at inference time.
It does not produce a new model file. It only works with HuggingFace
models loaded via `transformers` -- Ollama models cannot be steered this
way because Ollama does not expose internal layer activations.

The AI lab must be running.

### 1. Start the RepE inference server on the EC2 instance

SSH into the instance (via the `connect.sh` shell) and run:

```bash
cd benchmarks
source venv/bin/activate
python -m src.repe_server \
    --model "meta-llama/Llama-3.1-8B-Instruct" \
    --port 11435 \
    --strength 1.5 \
    --save-direction /tmp/refusal_dir.npy
```

This will:
  - Load the base model from HuggingFace
  - Compute the refusal direction from contrast pairs (or load from file)
  - Register a forward hook that subtracts the refusal direction at inference time
  - Serve an Ollama-compatible API on port 11435

Options:
  - `--layer N` : which transformer layer to steer (default: middle layer)
  - `--strength F` : how aggressively to subtract the refusal direction (default: 1.5)
  - `--direction-file path.npy` : load a pre-computed direction instead of recomputing
  - `--save-direction path.npy` : save the computed direction for reuse

> **Note:** Gated models (like Meta Llama) are not supported. If you try to
> load a gated model, the server will exit with an error telling you to use
> a non-gated model instead.

### 2. Uncomment the un-aligned model in models.yaml

Comment out the base models (they should already have CSVs in `results/`)
and uncomment the un-aligned entry:

```yaml
  - tag: "repe::meta-llama/Llama-3.1-8B-Instruct"
    category: "unaligned"
    description: "Llama 3.1 8B with refusal direction ablated via RepE"
    ollama_base_url: "http://localhost:11435"
```

### 3. Run the benchmark

```bash
python -m run_benchmark
```

### 4. Compare results

```bash
python -m run_analysis
```

The analysis script reads all CSVs in `results/`, so base and un-aligned
model results appear side by side automatically. The `model_category`
column distinguishes "base" from "unaligned" entries.

## Output Structure

```
results/
  CognitiveComputations_dolphin-llama3.1_8b.csv               # One CSV per model
  TheBloke_Mistral-7B-Instruct-v0.2-GGUF_Q4_K_M.csv
  repe__meta-llama_Llama-3.1-8B-Instruct.csv
  summaries/
    summary_overall.csv                                        # Aggregated rankings
    summary_by_difficulty.csv
    summary_by_category.csv
```