variable "aws_region" {
  description = "The AWS region to deploy in (must match your quota approval)"
  type        = string
  default     = "us-east-1" 
}

variable "lab_mode" {
  description = "Choose 'cpu' for testing (no quota needed) or 'gpu' for AI power (requires quota)"
  type        = string
  default     = "cpu" 
  validation {
    condition     = contains(["cpu", "gpu"], var.lab_mode)
    error_message = "The lab_mode must be either 'cpu' or 'gpu'."
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