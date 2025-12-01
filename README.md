# AWS GenAI Lab 🧪

This repository contains **Infrastructure as Code (Terraform)** to spin up a powerful, self-hosted AI environment on AWS. It is designed for personal R&D, allowing you to deploy open-source Large Language Models (LLMs) like Llama 3, Mistral, or even uncensored models like Dolphin.

It features a **Dual Mode** switch so you can test immediately with a CPU, or run full AI workloads with a GPU (available after AWS quota increase approval).

**🔒 Security:** Your AI lab is **not exposed to the internet**. All access is secured through SSH tunneling, and Open WebUI runs in single-user mode (no authentication required).

## 🎯 Project Goal

To create a **"dispose-on-demand"** AI lab. We use Terraform to automate the creation and destruction of the infrastructure, ensuring we only pay for the exact time we are using the resources.

-----

## 🚧 Step 1: AWS Account Setup

### 1.1 Create an IAM User (Security Best Practice)

**⚠️ Important:** Do NOT use root user access keys. Instead, create a dedicated IAM user for Terraform:

1. Log into your AWS Console
2. Search for **IAM** (Identity and Access Management) in the top search bar
3. Click **Users** in the left sidebar -> **Create user**
4. Set username: `terraform-deployer` (or any name you prefer)
5. Click **Next**
6. Select **Attach policies directly**
7. Search and check: **AdministratorAccess**
   - *For production, you'd want to restrict permissions further, but for a personal lab this is simplest*
8. Click **Next** -> **Create user**

### 1.2 Create Access Keys for the IAM User

1. Click on your newly created user (`terraform-deployer`)
2. Go to the **Security credentials** tab
3. Scroll down to **Access keys** -> Click **Create access key**
4. Select **Command Line Interface (CLI)** as the use case
5. Check the confirmation box: "I understand the above recommendation..."
6. Click **Next**
7. Add a description tag (optional): "Terraform GenAI Lab"
8. Click **Create access key**
9. **Important:** Download the CSV or copy both:
   - **Access Key ID** (starts with `AKIA...`)
   - **Secret Access Key** (you won't see this again!)

### 1.3 Configure Credentials

Create a file named `terraform.tfvars` in the project root (this file is already in .gitignore to prevent accidental commits):

```bash
# Create the credentials file
cat > terraform.tfvars << 'EOF'
aws_access_key_id     = "AKIA..."  # Replace with your IAM user's Access Key ID
aws_secret_access_key = "your-secret-access-key-here"  # Replace with your IAM user's Secret Key
EOF
```

**Security Note:** Never commit `terraform.tfvars` to Git. It's already excluded in .gitignore.

**Why IAM User Instead of Root?**
- Root user has unlimited permissions and can't be restricted
- IAM user permissions can be revoked or rotated easily
- If credentials leak, you can delete the IAM user without affecting your root account

### 1.4 Request GPU Quota (If Needed)

> **STOP.** You cannot run GPU mode until AWS trusts you with a GPU. New AWS accounts have a **default quota of 0 vCPUs** for GPU-enabled instance families (like G and VT).
>
> **In simple terms: AWS blocks new accounts from launching any EC2 instance that contains a GPU (even a small one) until you formally request and receive permission to use these expensive resources.**

**You can skip this step if you only want to test CPU mode first.**

#### How to Request GPU Quota

1. Log into your AWS Console
2. Select AWS Region: **US East (N. Virginia)** (or Ohio)
3. Search for **"Service Quotas"** in the top search bar
4. Click **AWS Services** in the sidebar → type **"Amazon Elastic Compute Cloud (Amazon EC2)"**
5. In the search bar specifically for EC2, type **"Running On-Demand G and VT instances"**
6. Click **Request increase at account level**
7. **Choose a quota value based on which GPU size you want:**
   - **Small (1 GPU):** Request at least **4 vCPUs**
   - **Medium (4 GPUs, 48 vCPUs):** Request at least **48 vCPUs**
   - **Large (4 GPUs, 96 vCPUs, faster inference):** Request at least **96 vCPUs**
   - **XLarge (8 GPUs):** Request at least **192 vCPUs**
8. Wait for approval email (usually 1-24 hours for small, up to 2-3 days for larger quotas)
9. If prompted for justification, use something like:
   > "I am requesting a quota increase to run self-hosted LLMs for personal research. I plan to spin up these instances on-demand to interact with open-source models from Hugging Face. The larger GPU configurations allow me to experiment with models ranging from 7B to 120B+ parameters. Self-hosting on AWS ensures I can use AI without third-party providers collecting my data. I am using Terraform to manage these resources efficiently and will destroy them when not in use. This is strictly for personal education and testing; there is no production or business traffic."

**Pro Tip:** Start with `small` (4 vCPU quota) to test your setup while waiting for approval of larger quotas.

-----

## 💻 Hardware Selection

### CPU Mode (No Quota Needed)

| Instance | vCPUs | RAM | Cost/Hour | Use Case |
|----------|-------|-----|-----------|----------|
| `t3.xlarge` | 4 | 16GB | ~$0.17 | Testing Terraform, small models (≤7B) |

**To use:** Just run with `lab_mode=cpu` (default)

### GPU Mode (Requires Quota Approval)

**The key to running bigger models is MORE GPUs, not more CPUs.** Each GPU adds 24GB of VRAM.

| Size Flag | Instance | GPUs | CPU/RAM | vCPU Quota | Cost/Hour | Best Use Case |
|-----------|----------|------|---------|------------|-----------|---------------|
| `small` | `g5.xlarge` | 1 | 4/16GB | 4 | ~$1.01 | **7B-13B Q8** (highest quality, small models) |
| `medium` | `g5.12xlarge` | 4 | 48/192GB | 48 | ~$5.67 | **30B-34B Q8** (highest quality, mid-size models) |
| `large` | `g5.24xlarge` | 4 | 96/384GB | 96 | ~$8.14 | **70B Q8** (highest quality, large models) |
| `xlarge` | `g5.48xlarge` | 8 | 192/768GB | 192 | ~$16.29 | **120B Q8** (highest quality, massive models) |

**To use:** Run with `lab_mode=gpu` and specify the size with `gpu_size=small|medium|large|xlarge`

**Understanding Quantization (Quality Levels):**
- **Q8** = Highest quality, nearly identical to original model (uses most VRAM)
- **Q5** = Balanced, slight quality loss, fits bigger models (recommended)
- **Q4** = Smallest files, noticeably lower quality, fits massive models (not recommended unless you need 120B+)

**Note:** 
- `medium` vs `large`: Same GPU/VRAM, but `large` has 2x CPU/RAM for faster inference and bigger context windows
- Costs shown are approximate US East (N. Virginia) on-demand rates

-----

## 🤖 Finding and Installing Models

Once your lab is running, you can pull any model available through Ollama or Hugging Face.

### Browse Available Models

**Ollama Library:** [https://ollama.com/library](https://ollama.com/library)
- Curated, pre-optimized models ready to use
- Simple pull commands (e.g., `llama3`, `mistral`, `phi3`)

**Hugging Face GGUF Models:** [https://huggingface.co/models?library=gguf](https://huggingface.co/models?library=gguf)
- Thousands of community models in GGUF format
- Click **"Use this model"** -> **"Ollama"** to get the command
- Copy only the part after `ollama run` (e.g., `hf.co/TheBloke/Mistral-7B-Instruct-v0.2-GGUF:Q4_K_M`)

### How to Install a Model

1. Open the WebUI at `http://localhost:8080` (via SSH tunnel)
2. Click the **model selector** dropdown (top of chat)
3. Click **"Pull a model from Ollama.com"**
4. Enter one of:
   - **Ollama model:** Just the name (e.g., `llama3`)
   - **Hugging Face GGUF:** The path without `ollama run` (e.g., `hf.co/TheBloke/Mistral-7B-Instruct-v0.2-GGUF:Q4_K_M`)
5. Click **Pull** and wait for the download
6. Select the model and start chatting!

-----

## 🚀 Usage

### 1\. Initialize

Initialize the Terraform working directory.

```bash
terraform init
```

### 2\. Launch (Select your Mode and Size)

#### Option A: Test Immediately (CPU Mode)
Use this to prove your setup works while waiting for AWS Support.

```bash
terraform apply -var="lab_mode=cpu"
```

#### Option B: Power Mode (GPU) - Choose Your Size

**Small GPU (1 GPU, 24GB VRAM)** - For 7B-13B models
```bash
terraform apply -var="lab_mode=gpu" -var="gpu_size=small"
```

**Medium GPU (4 GPUs, 96GB VRAM)** - For 30B-70B models
```bash
terraform apply -var="lab_mode=gpu" -var="gpu_size=medium"
```

**Large GPU (4 GPUs, 96GB VRAM)** - For 70B-120B models with faster inference
```bash
terraform apply -var="lab_mode=gpu" -var="gpu_size=large"
```

**XLarge GPU (8 GPUs, 192GB VRAM)** - For 120B+ models
```bash
terraform apply -var="lab_mode=gpu" -var="gpu_size=xlarge"
```

*Type `yes` when prompted.*

### 3\. Connect via Secure SSH Tunnel ⚡

**After `terraform apply` completes, the instance is booting and installing software.**

Run this script to establish a secure SSH tunnel and monitor setup progress:

```bash
./connect.sh
```

**What it does:**
- ✅ Creates an encrypted SSH tunnel to your instance
- ✅ Forwards ports securely to `localhost` (8080, 11434, 9099)
- ✅ Monitors installation progress in real-time
- ✅ Shows live logs until setup is complete

**Timeline:** The script will monitor for 2-3 minutes until everything is ready.

**Important:** Keep this terminal window open! Closing it will disconnect the tunnel.

### 4\. Access Your AI Lab 🎉

Once [`connect.sh`](connect.sh) shows "SETUP COMPLETE", the SSH tunnel is active.

#### **Web Interface (ChatGPT-like UI)** 🌐

1. **Open your browser to:**
   ```
   http://localhost:8080
   ```

2. **No login required!** Open WebUI runs in single-user admin mode.

3. **Pull a model** using the model selector (see [Finding and Installing Models](#-finding-and-installing-models) above)

4. Start chatting with your AI model!

**🔒 Security Notes:**
- Your AI lab is **NOT accessible from the internet**
- Only accessible through the SSH tunnel on your local machine
- No authentication needed (you are the only user)
- All traffic is encrypted through SSH

### 5\. Tear Down (The "Stop Billing" Button)

**Crucial:** When you are done, run this immediately.

**For CPU mode:**
```bash
terraform destroy -var="lab_mode=cpu"
```

**For GPU mode (specify the size you used):**
```bash
terraform destroy -var="lab_mode=gpu" -var="gpu_size=small"
# Or whatever size you launched: medium, large, xlarge
```

*This deletes everything. No hidden costs linger.*