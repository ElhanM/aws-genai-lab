output "instance_ip" {
  description = "The public IP address of your instance"
  value       = aws_instance.lab_instance.public_ip
}

output "webui_url" {
  description = "Open WebUI URL"
  value       = "http://${aws_instance.lab_instance.public_ip}:8080"
}

output "connection_instructions" {
  description = "How to connect to your instance"
  value       = <<-EOT
╔════════════════════════════════════════════════════════════╗
║           AWS GenAI Lab - Ready to Connect!                ║
╚════════════════════════════════════════════════════════════╝

Instance IP: ${aws_instance.lab_instance.public_ip}
Mode: ${var.lab_mode}

⚡ NEXT STEP: Monitor Setup Progress
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Run this command to watch the installation progress:

    ./connect.sh

This script will show you:
  ✓ Instance boot status
  ✓ Ollama installation progress  
  ✓ Docker & WebUI startup
  ✓ Real-time logs

Once complete (2-3 minutes), you'll get the WebUI URL!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🌐 WEB INTERFACE (After setup completes):
   http://${aws_instance.lab_instance.public_ip}:8080

📦 PULL A MODEL: After opening WebUI, use the model selector
   to pull a model like 'dolphin-mistral' or 'llama3'

💻 SSH ACCESS (Optional, for advanced users):
   The connect.sh script also provides SSH access after setup

EOT
}