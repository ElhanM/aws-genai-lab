#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

# Get the IP from terraform output
IP=$(terraform output -raw instance_ip 2>/dev/null)

if [ -z "$IP" ]; then
    echo -e "${RED}Error: Could not get instance IP. Did you run 'terraform apply'?${NC}"
    exit 1
fi

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║      AWS GenAI Lab - Setup Progress Monitor 🚀             ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo -e "${YELLOW}Instance IP: ${IP}${NC}"
echo -e "${CYAN}WebUI URL: http://${IP}:3000${NC}"
echo ""

# Fix permissions on the key
chmod 400 generated_key.pem 2>/dev/null || true

# Function to check if SSH is ready
check_ssh() {
    ssh -i generated_key.pem -o StrictHostKeyChecking=no -o ConnectTimeout=2 ubuntu@${IP} "exit" 2>/dev/null
    return $?
}

# Function to check if setup is complete
check_ready() {
    ssh -i generated_key.pem -o StrictHostKeyChecking=no -o ConnectTimeout=2 ubuntu@${IP} "test -f /var/lib/cloud/instance/ready" 2>/dev/null
    return $?
}

# Function to check if WebUI is running
check_webui() {
    ssh -i generated_key.pem -o StrictHostKeyChecking=no -o ConnectTimeout=2 ubuntu@${IP} "docker ps | grep -q open-webui" 2>/dev/null
    return $?
}

# Wait for SSH to be available
echo -e "${YELLOW}⏳ Step 1/3: Waiting for instance to boot and SSH to be ready...${NC}"
COUNTER=0
MAX_WAIT=60
while ! check_ssh; do
    echo -n "."
    sleep 2
    COUNTER=$((COUNTER + 1))
    if [ $COUNTER -gt $MAX_WAIT ]; then
        echo -e "\n${RED}Error: SSH connection timeout${NC}"
        exit 1
    fi
done
echo -e "\n${GREEN}✓ SSH is ready!${NC}\n"

# Check if setup is already complete
if check_ready && check_webui; then
    echo -e "${GREEN}✓✓✓ Instance is fully configured and ready! ✓✓✓${NC}\n"
    echo -e "${MAGENTA}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${MAGENTA}║                    🎉 SETUP COMPLETE! 🎉                   ║${NC}"
    echo -e "${MAGENTA}╚════════════════════════════════════════════════════════════╝${NC}\n"
    echo -e "${CYAN}🌐 Open your browser to:${NC}"
    echo -e "${GREEN}   http://${IP}:3000${NC}\n"
    echo -e "${YELLOW}📝 Create an account and start chatting with your AI model!${NC}\n"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
    echo -e "${CYAN}💻 Optional: Connect via SSH to use Ollama CLI${NC}"
    read -p "Press Enter to connect via SSH (or Ctrl+C to exit): "
    ssh -i generated_key.pem ubuntu@${IP}
    exit 0
fi

# Show setup progress
echo -e "${YELLOW}⏳ Step 2/3: Installing Ollama and downloading AI model...${NC}"
echo -e "${BLUE}This will take 2-5 minutes depending on model size and network speed.${NC}\n"

# Monitor progress with live updates
ssh -i generated_key.pem -o StrictHostKeyChecking=no ubuntu@${IP} << 'ENDSSH'
    # Function to show progress
    show_progress() {
        clear
        echo "╔════════════════════════════════════════════════════════════╗"
        echo "║           AWS GenAI Lab - Installation Progress           ║"
        echo "╚════════════════════════════════════════════════════════════╝"
        echo ""
        
        # Check Ollama service
        echo "📦 Ollama Service Status:"
        if systemctl is-active --quiet ollama; then
            echo "   ✓ Ollama service: Running"
        else
            echo "   ⏳ Ollama service: Installing..."
        fi
        echo ""
        
        # Check model download
        echo "🤖 AI Model Download Progress:"
        if [ -f /var/log/ollama-pull.log ]; then
            tail -15 /var/log/ollama-pull.log | grep -E "pulling|success|SHA256" || echo "   ⏳ Download in progress..."
        else
            echo "   ⏳ Waiting for download to start..."
        fi
        echo ""
        
        # Check Docker installation
        echo "🐳 Docker & WebUI Status:"
        if systemctl is-active --quiet docker; then
            echo "   ✓ Docker: Running"
            if docker ps 2>/dev/null | grep -q open-webui; then
                echo "   ✓ Open WebUI: Running on port 3000"
            else
                echo "   ⏳ Open WebUI: Starting..."
            fi
        else
            echo "   ⏳ Docker: Installing..."
        fi
        echo ""
        
        # Show recent logs
        echo "📋 Recent Activity:"
        if [ -f /var/log/user-data.log ]; then
            tail -5 /var/log/user-data.log | sed 's/^/   /'
        fi
        echo ""
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "⏱️  Monitoring... (Press Ctrl+C to disconnect, setup continues)"
    }
    
    # Show progress until ready
    while [ ! -f /var/lib/cloud/instance/ready ]; do
        show_progress
        sleep 3
    done
    
    # Final check for WebUI
    echo "⏳ Waiting for WebUI to be fully ready..."
    for i in {1..20}; do
        if sudo docker ps 2>/dev/null | grep -q open-webui; then
            break
        fi
        sleep 2
    done
    
    clear
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║                  ✓✓✓ SETUP COMPLETE! ✓✓✓                 ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo ""
    echo "📊 Installed Models:"
    ollama list
    echo ""
    echo "🐳 Running Containers:"
    sudo docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
ENDSSH

IP_FOR_OUTPUT=$IP

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${MAGENTA}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${MAGENTA}║                    🎉 ALL READY! 🎉                        ║${NC}"
echo -e "${MAGENTA}╚════════════════════════════════════════════════════════════╝${NC}\n"
echo -e "${CYAN}🌐 OPEN WEB INTERFACE (Recommended):${NC}"
echo -e "${GREEN}   http://${IP_FOR_OUTPUT}:3000${NC}\n"
echo -e "${YELLOW}   1. Open the URL in your browser${NC}"
echo -e "${YELLOW}   2. Create a local account${NC}"
echo -e "${YELLOW}   3. Start chatting with your AI model!${NC}\n"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
echo -e "${CYAN}💻 OPTIONAL: SSH Terminal Access${NC}"
read -p "Press Enter to connect via SSH for CLI access (or Ctrl+C to exit): "

# Final connection for SSH users
ssh -i generated_key.pem ubuntu@${IP}