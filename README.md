# AWS GenAI Lab 🧪

This repository contains **Infrastructure as Code (Terraform)** to spin up a powerful, self-hosted AI environment on AWS. It allows you to deploy open-source LLMs (Llama 3, Mistral, Dolphin) in a private environment.

## 🎯 Project Goal & Architecture

To create a **"dispose-on-demand"** AI lab. We use Terraform to automate the creation and destruction of infrastructure, ensuring you only pay for resources while they are in use.

**🔒 Security & Privacy**

  * **Zero Internet Exposure:** This lab is **not exposed to the public internet**.
  * **Secure Tunnel:** All access is routed through an encrypted SSH tunnel.
  * **Private:** Open WebUI runs in single-user mode (no auth required) because you are the only user with access to the tunnel.

## 🚧 Step 1: AWS Account Setup

### 1.1 Create an IAM User

**⚠️ Important:** Do NOT use root user access keys.

1.  Log into AWS Console and search for **IAM**.
2.  Click **Users** -\> **Create user**.
3.  Set username: `terraform-deployer`.
4.  Select **Attach policies directly**.
5.  Search and check: **AdministratorAccess**.
6.  Click **Next** -\> **Create user**.

### 1.2 Create Access Keys

1.  Click your new user (`terraform-deployer`).
2.  Go to **Security credentials** -\> **Access keys** -\> **Create access key**.
3.  Select **Command Line Interface (CLI)**.
4.  Check the confirmation box and click **Next**.
5.  Click **Create access key**.
6.  **Download the CSV** or copy the **Access Key ID** and **Secret Access Key**.

### 1.3 Configure Credentials

Create a file named `terraform.tfvars` in the project root.

```bash
cat > terraform.tfvars << 'EOF'
aws_access_key_id     = "AKIA..."  # Replace with your Access Key ID
aws_secret_access_key = "your-secret-access-key-here"
EOF
```

*Note: `terraform.tfvars` is ignored by Git to prevent accidental commits.*

### 1.4 Request GPU Quota (Required for GPU Mode)

New AWS accounts have a default quota of **0 vCPUs** for GPU instances. You must request an increase before using GPU mode.

1.  Log into AWS Console (Region: **US East N. Virginia** or **Ohio**).
2.  Go to **Service Quotas** -\> **Amazon EC2**.
3.  Search for **"Running On-Demand G and VT instances"**.
4.  Click **Request increase at account level**.
5.  **Select Quota:**
      * **Small (1 GPU):** Request **4 vCPUs**
      * **Medium (4 GPUs):** Request **48 vCPUs**
      * **Large (4 GPUs, High CPU):** Request **96 vCPUs**
      * **XLarge (8 GPUs):** Request **192 vCPUs**
6.  If prompted for justification, use:
    > "I am requesting a quota increase to run self-hosted LLMs for personal research. I plan to spin up these instances on-demand to interact with open-source models from Hugging Face. The larger GPU configurations allow me to experiment with a wide range of model sizes. Self-hosting on AWS also ensures I can use AI without third-party providers collecting my data. I am using Terraform to manage these resources efficiently and will destroy them when not in use. This is strictly for personal education and testing; there is no production or business traffic."

## 💻 Hardware Selection

### CPU Mode (No Quota Needed)

Run with `lab_mode=cpu`.

| Instance | vCPUs | RAM | Cost/Hour | Use Case |
|----------|-------|-----|-----------|----------|
| `t3.xlarge` | 4 | 16GB | \~$0.17 | Testing Terraform, small models (≤7B) |

### GPU Mode (Requires Quota)

Run with `lab_mode=gpu` and set `gpu_size`.

| Size Flag | Instance | GPUs | VRAM | vCPU Quota | Cost/Hour | Target Model Size |
|-----------|----------|------|------|------------|-----------|-------------------|
| `small` | `g5.xlarge` | 1 | 24GB | 4 | \~$1.01 | **7B-13B Q8** |
| `medium` | `g5.12xlarge` | 4 | 96GB | 48 | ~$5.67 | **30B-34B Q8** |
| `large` | `g5.24xlarge` | 4 | 96GB | 96 | \~$8.14 | **70B Q8** |
| `xlarge` | `g5.48xlarge` | 8 | 192GB | 192 | ~$16.29 | **120B Q8** |

*Note: `large` has the same VRAM as `medium` but double the system RAM/CPU for faster inference.*

## 🤖 Models & RAG Capabilities

Once the lab is running, you interact with it via **Open WebUI**.

### Installing Models

1.  **Find a model:**
      * [Ollama Library](https://ollama.com/library) (e.g., `llama3`)
      * [Hugging Face GGUF](https://huggingface.co/models?library=gguf) (look for "Ollama" run commands).
2.  **In WebUI:** Click the model selector -\> **"Pull a model from Ollama.com"**.
3.  **Enter tag:** Paste the model tag (e.g., `CognitiveComputations/dolphin-llama3.1:8b`) and click **Pull**.

### RAG (Chat with Documents)

The system includes built-in RAG (Retrieval-Augmented Generation) using ChromaDB.

  * **Quick Upload:** Click the **+** icon in chat to upload files (PDF, DOCX, TXT) for a single session.
  * **Knowledge Base:** Go to **Workspace** -\> **Knowledge** to create reusable document collections.

## 🚀 Usage

### 1\. Initialize

```bash
terraform init
```

### 2\. Launch

Select your mode and run the corresponding command. Type `yes` when prompted.

**Option A: CPU Mode (Test)**

```bash
terraform apply -var="lab_mode=cpu"
```

**Option B: GPU Mode (Power)**

```bash
# Select one size: small | medium | large | xlarge
terraform apply -var="lab_mode=gpu" -var="gpu_size=small"
```

### 3\. Connect via SSH Tunnel

Run the connection script to establish the secure tunnel and monitor installation.

```bash
./connect.sh
```

  * **Wait for "SETUP COMPLETE".**
  * **Keep this terminal open.** The tunnel is active only while this session is running.
  * Ignore "Connection refused" errors during the boot process.

### 4\. Access The Lab

Open your browser to:

```
http://localhost:8080
```

You can now pull models and upload documents as described in the **Models & RAG** section above.

### 5\. Tear Down (Stop Billing)

**Crucial:** When finished, destroy resources to stop costs. This deletes all data.

1.  Type `exit` in the `connect.sh` terminal.
2.  Run the destroy command matching your launch mode:


```bash
# CPU
terraform destroy -var="lab_mode=cpu"

# GPU (example)
terraform destroy -var="lab_mode=gpu" -var="gpu_size=small"
# Or whatever size you launched
```