# AWS GenAI Spot (Terraform) 🧪

This repository contains **Infrastructure as Code (Terraform)** to spin up a powerful, self-hosted AI environment on AWS using **Spot Instances**. It is designed for personal R&D, allowing you to deploy open-source Large Language Models (LLMs) like Llama 3 or Mistral for cents on the dollar.

It features a **Dual Mode** switch so you can test immediately with a CPU, or run full AI workloads with a GPU (available after AWS quota increase approval).

## 🎯 Project Goal

To create a **"dispose-on-demand"** AI lab. We use Terraform to automate the creation and destruction of the infrastructure, ensuring we only pay for the exact minutes we are using the GPU.

-----

## 🚧 Step 1: AWS Account Setup

### 1.1 Create an IAM User (Security Best Practice)

**⚠️ Important:** Do NOT use root user access keys. Instead, create a dedicated IAM user for Terraform:

1. Log into your AWS Console
2. Search for **IAM** (Identity and Access Management) in the top search bar
3. Click **Users** in the left sidebar → **Create user**
4. Set username: `terraform-deployer` (or any name you prefer)
5. Click **Next**
6. Select **Attach policies directly**
7. Search and check: **AdministratorAccess**
   - *For production, you'd want to restrict permissions further, but for a personal lab this is simplest*
8. Click **Next** → **Create user**

### 1.2 Create Access Keys for the IAM User

1. Click on your newly created user (`terraform-deployer`)
2. Go to the **Security credentials** tab
3. Scroll down to **Access keys** → Click **Create access key**
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

1. Log into your AWS Console
2. Select AWS Region: **US East (N. Virginia)** (or Ohio)
3. Search for **"Service Quotas"** in the top search bar
4. Click **AWS Services** in the sidebar → type **"Amazon Elastic Compute Cloud (Amazon EC2)"**
5. In the search bar specifically for EC2, type **"Running On-Demand G and VT instances"**
6. Click **Request increase at account level**
7. Set new value: **8** (Enough for one `g5.xlarge`)
8. Wait for approval email (usually 1-24 hours) before proceeding
9. If prompted for justification, use something like:
   > "Requesting quota increase for personal professional development. My goal is to gain hands-on DevOps experience by deploying self-hosted open-source LLMs using Terraform for Infrastructure as Code. I intend to benchmark performance and compare the reasoning capabilities of different model architectures. This is strictly for personal education and research; no production or business traffic."

-----

## 💻 Hardware Selection - Dual Mode

| **Mode** | **Flag** | **Hardware** | **Requires Permission?** | **Cost (Spot)** | **Use Case** | **Auto-Installed Model** |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **CPU** | `cpu` | `t3.xlarge` (16GB RAM) | **No** (Usually) | ~$0.05/hr | Testing Terraform, proving concept. | `phi3` (Small, Fast) |
| **GPU** | `gpu` | `g5.xlarge` (24GB VRAM) | **Yes** (Requires Quota) | ~$0.30/hr | Real AI inference, 30B+ models. | `llama3` (Powerful) |

-----

## 💰 Cost Strategy: Spot Instances

We use **Spot Instances** in this Terraform configuration.

  * **Concept:** We bid on unused AWS capacity.
  * **Benefit:** \~60-90% discount vs On-Demand prices.
  * **Risk:** AWS can terminate the instance if they need the capacity back (rare in N. Virginia for G5s, but possible).
  * **Control:** The Terraform scripts use a disposable SSH key. If you destroy the infrastructure, you lose the data on the disk. This is by design to prevent accidental billing.

-----

## 🚀 Usage

### 1\. Initialize

Initialize the Terraform working directory.

```bash
terraform init
```

### 2\. Launch (Select your Mode)

**Option A: Test Immediately (CPU Mode)**
Use this to prove your setup works while waiting for AWS Support. It will install the smaller `phi3` model.

```bash
terraform apply -var="lab_mode=cpu"
```

**Option B: Power Mode (GPU Mode)**
Use this once your Quota Increase is approved. It will install the powerful `llama3` model.

```bash
terraform apply -var="lab_mode=gpu"
```

*Type `yes` when prompted.*

### 3\. Monitor Setup Progress ⚡

**After `terraform apply` completes, the instance is booting and installing software.**

Run this script to watch the installation progress in real-time:

```bash
./connect.sh
```

**What it shows:**
- ✅ Instance boot status
- ✅ Ollama service installation
- ✅ AI model download progress (with download speed and completion %)
- ✅ Docker & Open WebUI startup
- ✅ Live installation logs

**Timeline:** The script will monitor for 2-5 minutes until everything is ready, then display the WebUI URL.

**Note:** The script also offers optional SSH access for advanced users who want to explore the server internals, but this is not necessary for normal use.

### 4\. Access Your AI Lab 🎉

Once `connect.sh` shows "SETUP COMPLETE", open the Web Interface:

#### **Web Interface (ChatGPT-like UI)** 🌐

1. Open the URL shown by `connect.sh` in your browser:
   ```
   http://YOUR_INSTANCE_IP:3000
   ```

2. Create a local account (stored only on your instance)

3. Start chatting with your AI model!

### 5\. Tear Down (The "Stop Billing" Button)

**Crucial:** When you are done, run this immediately.

```bash
terraform destroy -var="lab_mode=cpu"
# Or if you used GPU mode:
terraform destroy -var="lab_mode=gpu"
```

*This deletes everything. No hidden costs linger.*