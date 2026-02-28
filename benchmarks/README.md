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
# Edit .env with your API key and EC2 connection details
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

This reads all CSV files in `results/` and generates **both** output files
in a single run:

- `results/analysis_output.md` — redacted (answers hidden), version-controlled
- `results/analysis_output_full.md` — full with answers, gitignored

Both files contain per-prompt detail with judge reasoning and summary
tables ranked by overall score. Summaries are also exported as CSVs to
`results/summaries/`.

### View Individual Results

To generate a full Markdown report (with AI responses) for a single model:

```bash
python -m run_analysis --single results/<filename>.csv
```

This creates `results/<filename>_view.md` with the complete per-prompt
detail including responses, scores, and judge reasoning. The output file
is gitignored.

### Patch a Single Failed Result

If a prompt failed (e.g. due to a timeout), re-run just that prompt and
update the existing CSV in-place:

```bash
python -m patch_result <model_tag> <prompt_id>
```

The model tag is the same format used in `config/models.yaml`. The script will:
- Derive the CSV path automatically from the model tag
- Pull the model if it is not already loaded
- Re-run the single prompt
- Judge the response
- Overwrite only that row in the CSV, leaving all other results intact

**Example:**

```bash
python -m patch_result "hf.co/AlicanKiraz0/Seneca-Cybersecurity-LLM-x-QwQ-32B-Q8_Max-Version:Q8_0" exploit-01
```

After patching, re-run the analysis to update the summary tables:

```bash
python -m run_analysis
```

## Output Structure

```
results/
  CognitiveComputations_dolphin-llama3.1_8b.csv               # One CSV per model (gitignored)
  TheBloke_Mistral-7B-Instruct-v0.2-GGUF_Q4_K_M.csv          # One CSV per model (gitignored)
  TheBloke_Mistral-7B-Instruct-v0.2-GGUF_Q4_K_M_view.md      # Single-model viewer (gitignored)
  analysis_output.md                                           # Redacted analysis - version controlled
  analysis_output_full.md                                      # Full analysis with answers - gitignored
  summaries/
    summary_overall.csv                                        # Aggregated rankings
    summary_by_difficulty.csv
    summary_by_category.csv
```