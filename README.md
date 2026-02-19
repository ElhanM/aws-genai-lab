# AWS GenAI Lab

This repository contains **Infrastructure as Code (Terraform)** to spin up a powerful, self-hosted AI environment on AWS. It allows you to deploy open-source LLMs (Llama 3, Mistral, Dolphin) in a private environment.

## Project Goal & Architecture

To create a **"dispose-on-demand"** AI lab. We use Terraform to automate the creation and destruction of infrastructure, ensuring you only pay for resources while they are in use.

**Security & Privacy**

* **Zero Internet Exposure:** This lab is **not exposed to the public internet**.
* **Secure Tunnel:** All access is routed through an encrypted SSH tunnel.
* **Private:** Open WebUI runs in single-user mode (no auth required) because you are the only user with access to the tunnel.

## Step 1: AWS Account Setup

### 1.1 Create an IAM User

**Important:** Do NOT use root user access keys.

1. Log into AWS Console and search for **IAM**.
2. Click **Users** -> **Create user**.
3. Set username: `terraform-deployer`.
4. Select **Attach policies directly**.
5. Search and check: **AdministratorAccess**.
6. Click **Next** -> **Create user**.

### 1.2 Create Access Keys

1. Click your new user (`terraform-deployer`).
2. Go to **Security credentials** -> **Access keys** -> **Create access key**.
3. Select **Command Line Interface (CLI)**.
4. Check the confirmation box and click **Next**.
5. Click **Create access key**.
6. **Download the CSV** or copy the **Access Key ID** and **Secret Access Key**.

### 1.3 Configure Credentials

Create a file named `terraform.tfvars` in the project root:

```bash
cat > terraform.tfvars << 'EOF'
# --- Required: AWS Credentials ---
aws_access_key_id     = "AKIA..."         # Your IAM user's Access Key ID
aws_secret_access_key = "your-secret..."  # Your IAM user's Secret Access Key

# --- Optional: Deployment Settings ---
aws_region    = "us-east-1"  # AWS region (default: us-east-1)
instance_size = "gpu_small"  # Instance size: cpu / gpu_small / gpu_medium / gpu_large / gpu_xlarge
EOF
```

*Note: `terraform.tfvars` is ignored by Git to prevent accidental commits.*

### 1.4 Request GPU Quota (Required for GPU Mode)

New AWS accounts have a default quota of **0 vCPUs** for GPU instances. You must request an increase before using GPU mode.

1. Log into AWS Console (Region: **US East N. Virginia** or **Ohio**).
2. Go to **Service Quotas** -> **Amazon EC2**.
3. Search for **"Running On-Demand G and VT instances"**.
4. Click **Request increase at account level**.
5. **Select Quota:**
    * **Small (1 GPU):** Request **4 vCPUs**
    * **Medium (4 GPUs):** Request **48 vCPUs**
    * **Large (4 GPUs, High CPU):** Request **96 vCPUs**
    * **XLarge (8 GPUs):** Request **192 vCPUs**
6. If prompted for justification, use:
> "I am requesting a quota increase to run self-hosted LLMs for personal research. I plan to spin up these instances on-demand to interact with open-source models from Hugging Face. The larger GPU configurations allow me to experiment with a wide range of model sizes. Self-hosting on AWS also ensures I can use AI without third-party providers collecting my data. I am using Terraform to manage these resources efficiently and will destroy them when not in use. This is strictly for personal education and testing; there is no production or business traffic."

## Hardware Selection

| Size Flag    | Instance      | GPUs | VRAM  | vCPU Quota | Cost/Hour | Target Model Size    |
| ------------ | ------------- | ---- | ----- | ---------- | --------- | -------------------- |
| `cpu`        | `t3.xlarge`   | -    | -     | None       | ~$0.17    | Testing, models <=7B |
| `gpu_small`  | `g5.xlarge`   | 1    | 24GB  | 4          | ~$1.01    | 7B-13B Q8            |
| `gpu_medium` | `g5.12xlarge` | 4    | 96GB  | 48         | ~$5.67    | 30B-34B Q8           |
| `gpu_large`  | `g5.24xlarge` | 4    | 96GB  | 96         | ~$8.14    | 70B Q8               |
| `gpu_xlarge` | `g5.48xlarge` | 8    | 192GB | 192        | ~$16.29   | 120B Q8              |

Set `instance_size` in your `terraform.tfvars` before applying.

## Models & RAG Capabilities

Once the lab is running, you interact with it via **Open WebUI**.

### Finding & Installing Models

1. **Find a Model Tag:**
    * **[Ollama Library](https://ollama.com/library):** Search for a model tag (e.g., `CognitiveComputations/dolphin-llama3.1:8b`).
    * **[Hugging Face GGUF](https://huggingface.co/models?library=gguf):** Find a model, then click **Use this model -> Ollama** to get the command.
2. **Open the Downloader:**
In the WebUI, click the **model selector** (top of chat) -> **"Pull a model from Ollama.com"**.
3. **Enter Tag & Pull:**
Paste the tag or command into the box and click the download button.

**Examples:**
> * **Ollama Tag:** `CognitiveComputations/dolphin-llama3.1:8b`
> * **Hugging Face Command:** `ollama run hf.co/TheBloke/Mistral-7B-Instruct-v0.2-GGUF:Q4_K_M`

### RAG (Chat with Documents)

The system includes built-in RAG (Retrieval-Augmented Generation) using ChromaDB.

* **Quick Upload:** Click the **+** icon in chat to upload files (PDF, DOCX, TXT) for a single session.
* **Knowledge Base:** Go to **Workspace** -> **Knowledge** to create reusable document collections.

## Usage

### 1. Configure

Edit `terraform.tfvars` and set your credentials and desired `instance_size`.

### 2. Initialize

```bash
terraform init
```

### 3. Launch

```bash
terraform apply -auto-approve
```

### 4. Connect via SSH Tunnel

Run the connection script to establish the secure tunnel and monitor installation.

```bash
./connect.sh
```

- Wait for "SETUP COMPLETE".
- Keep this terminal open. The tunnel is active only while this session is running.
- Ignore "Connection refused" errors during the boot process.

### 5. Access The Lab

Open your browser to:

```
http://localhost:8080
```

You can now pull models and upload documents as described in the **Models & RAG** section above.

### 6. Tear Down (Stop Billing)

**Crucial:** When finished, destroy resources to stop costs. This deletes all data.

1. Type `exit` in the `connect.sh` terminal.
2. Run:

```bash
terraform destroy -auto-approve
```