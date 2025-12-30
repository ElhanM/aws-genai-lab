output "instance_ip" {
  description = "The public IP address of your instance"
  value       = aws_instance.lab_instance.public_ip
}

output "ssh_tunnel_command" {
  description = "SSH tunnel command for secure access"
  value       = "ssh -i generated_key.pem -L 8080:localhost:8080 -L 11434:localhost:11434 ubuntu@${aws_instance.lab_instance.public_ip}"
}

output "connection_instructions" {
  description = "How to connect to your instance"
  value       = <<-EOT
╔════════════════════════════════════════════════════════════╗
║           AWS GenAI Lab - Ready to Connect!                ║
╚════════════════════════════════════════════════════════════╝

Instance IP: ${aws_instance.lab_instance.public_ip}
Mode: ${var.lab_mode}

⚡ NEXT STEP: Start SSH Tunnel & Monitor Setup
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Run this command to establish a secure connection:

    ./connect.sh

This script will:
     Create an SSH tunnel to your instance
     Monitor installation progress  
     Forward ports securely to localhost
     Show real-time setup logs
     Give you an interactive shell on the instance

Once complete (2-3 minutes), access the WebUI at:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

   SECURE WEB INTERFACE (via SSH tunnel):
   http://localhost:8080

   SECURITY NOTES:
   - WebUI is NOT exposed to the internet
   - Only accessible through SSH tunnel
   - No authentication required (single-user mode)
   - Keep the connect.sh terminal open while using
   - Type 'exit' in the terminal to disconnect

   FIND MODELS:
   - Ollama Library: ollama.com/library
   - Hugging Face GGUF: huggingface.co/models?library=gguf

EOT
}