terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    tls = {
      source = "hashicorp/tls"
      version = "~> 4.0"
    }
    local = {
      source = "hashicorp/local"
      version = "~> 2.0"
    }
  }
}

provider "aws" {
  region     = var.aws_region
  access_key = var.aws_access_key_id
  secret_key = var.aws_secret_access_key
}

# --- 1. Dynamic Hardware Selection ---
locals {
  # CPU Instance (Always the same)
  cpu_instance = "t3.xlarge"  # 4 vCPU, 16GB RAM
  
  # GPU Instance Sizes (Quota-based selection)
  gpu_instances = {
    small  = "g5.xlarge"   # 4 vCPUs,  1 GPU, 24GB VRAM  - Quota: 4
    medium = "g5.2xlarge"  # 8 vCPUs,  1 GPU, 24GB VRAM  - Quota: 8
    large  = "g5.4xlarge"  # 16 vCPUs, 1 GPU, 24GB VRAM  - Quota: 16
    xlarge = "g5.8xlarge"  # 32 vCPUs, 1 GPU, 24GB VRAM  - Quota: 32
  }
  
  # Final instance selection
  selected_instance = var.lab_mode == "cpu" ? local.cpu_instance : local.gpu_instances[var.gpu_size]
}

# --- 2. Networking & Security ---
data "aws_vpc" "default" {
  default = true
}

# Get availability zones
data "aws_availability_zones" "available" {
  state = "available"
}

# Get Subnets in the default VPC
data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

# Create a subnet if none exist
resource "aws_subnet" "default_subnet" {
  count                   = length(data.aws_subnets.default.ids) == 0 ? 1 : 0
  vpc_id                  = data.aws_vpc.default.id
  cidr_block              = "172.31.0.0/20"
  availability_zone       = data.aws_availability_zones.available.names[0]
  map_public_ip_on_launch = true

  tags = {
    Name = "ai-lab-default-subnet"
  }
}

resource "aws_security_group" "ai_lab_sg" {
  name        = "ai-lab-security-group"
  description = "Allow SSH and AI UI ports"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  ingress {
    from_port   = 11434
    to_port     = 11434
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  ingress {
    from_port   = 8080
    to_port     = 8080
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  ingress {
    from_port   = 3000
    to_port     = 3000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Open WebUI"
  }
  ingress {
    from_port   = 9099
    to_port     = 9099
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Open WebUI Pipelines"
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# --- 3. SSH Key Generation ---
resource "tls_private_key" "lab_key" {
  algorithm = "RSA"
  rsa_bits  = 4096
}

resource "aws_key_pair" "generated_key" {
  key_name   = "ai-lab-key-${substr(uuid(), 0, 8)}"
  public_key = tls_private_key.lab_key.public_key_openssh
}

resource "local_file" "private_key" {
  content         = tls_private_key.lab_key.private_key_pem
  filename        = "${path.module}/generated_key.pem"
  file_permission = "0400"
}

# --- 4. AMI Selection (The Brains) ---
# If GPU mode, get the NVIDIA Deep Learning AMI (Has drivers pre-installed)
data "aws_ami" "deep_learning_ami" {
  count       = var.lab_mode == "gpu" ? 1 : 0
  most_recent = true
  owners      = ["amazon"]
  filter {
    name   = "name"
    values = ["Deep Learning OSS Nvidia Driver AMI GPU PyTorch 2.0.1 (Ubuntu 20.04)*"]
  }
}

# If CPU mode, get standard Ubuntu 22.04 (Lighter, faster boot)
data "aws_ami" "ubuntu_ami" {
  count       = var.lab_mode == "cpu" ? 1 : 0
  most_recent = true
  owners      = ["099720109477"] # Canonical
  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }
}

# --- 5. The Instance ---
resource "aws_instance" "lab_instance" {
  # Select the right AMI based on the mode
  ami = var.lab_mode == "gpu" ? data.aws_ami.deep_learning_ami[0].id : data.aws_ami.ubuntu_ami[0].id
  
  # Select the right Instance Type based on mode and size
  instance_type = local.selected_instance
  
  key_name      = aws_key_pair.generated_key.key_name
  vpc_security_group_ids = [aws_security_group.ai_lab_sg.id]
  
  # Use existing subnet if available, otherwise use the one we created
  subnet_id = length(data.aws_subnets.default.ids) > 0 ? data.aws_subnets.default.ids[0] : aws_subnet.default_subnet[0].id

  root_block_device {
    volume_size = 60
    volume_type = "gp3"
  }

  # Startup Script: Installs Ollama and Open WebUI
  user_data = <<-EOF
              #!/bin/bash
              set -e
              
              # Log everything to a file we can check
              exec > >(tee /var/log/user-data.log)
              exec 2>&1
              
              echo "=== Starting Ollama Installation ==="
              
              # Install Ollama
              curl -fsSL https://ollama.com/install.sh | sh
              
              # Enable and start Ollama service
              systemctl enable ollama
              systemctl start ollama
              
              # Wait for Ollama to be ready
              echo "Waiting for Ollama service to start..."
              for i in {1..30}; do
                if systemctl is-active --quiet ollama; then
                  echo "Ollama service is active!"
                  break
                fi
                sleep 1
              done
              
              # Wait for Ollama API to be responsive
              echo "Waiting for Ollama API..."
              for i in {1..60}; do
                if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
                  echo "Ollama API is ready!"
                  break
                fi
                sleep 2
              done
              
              # Install Docker for Open WebUI
              echo "=== Installing Docker ==="
              apt-get update
              apt-get install -y docker.io
              systemctl enable docker
              systemctl start docker
              
              # Add ubuntu user to docker group
              usermod -aG docker ubuntu
              
              # Run Open WebUI Pipelines for HuggingFace support
              echo "=== Starting Open WebUI Pipelines ==="
              docker run -d \
                --name pipelines \
                --network host \
                -v pipelines:/app/pipelines \
                --restart always \
                ghcr.io/open-webui/pipelines:main
              
              # Run Open WebUI with Pipelines integration
              echo "=== Starting Open WebUI ==="
              docker run -d \
                --name open-webui \
                --network host \
                -v open-webui:/app/backend/data \
                --restart always \
                -e OLLAMA_BASE_URL=http://localhost:11434 \
                -e OPENAI_API_BASE_URLS=http://localhost:9099 \
                ghcr.io/open-webui/open-webui:main
              
              # Create a ready flag file
              echo "=== Setup Complete ==="
              touch /var/lib/cloud/instance/ready
              echo "Ready at $(date)" > /var/lib/cloud/instance/ready
              EOF

  tags = {
    Name = "AWS-GenAI-Lab-${var.lab_mode}${var.lab_mode == "gpu" ? "-${var.gpu_size}" : ""}"
  }
}