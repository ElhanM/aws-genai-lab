variable "aws_region" {
  description = "The AWS region to deploy in (must match your quota approval)"
  type        = string
  default     = "us-east-1"
}

variable "instance_size" {
  description = "Instance size: 'cpu' (4 vCPU, 16GB RAM, no quota), 'gpu_small' (1 GPU, 24GB VRAM), 'gpu_medium' (4 GPUs, 96GB VRAM), 'gpu_large' (4 GPUs, 96GB VRAM, high CPU), 'gpu_xlarge' (8 GPUs, 192GB VRAM)"
  type        = string
  default     = "cpu"
  validation {
    condition     = contains(["cpu", "gpu_small", "gpu_medium", "gpu_large", "gpu_xlarge"], var.instance_size)
    error_message = "The instance_size must be one of: cpu, gpu_small, gpu_medium, gpu_large, gpu_xlarge."
  }
}

variable "aws_access_key_id" {
  description = "AWS Access Key ID"
  type        = string
  sensitive   = true
}

variable "aws_secret_access_key" {
  description = "AWS Secret Access Key"
  type        = string
  sensitive   = true
}