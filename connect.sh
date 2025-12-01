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
echo -e "${CYAN}WebUI URL (via tunnel): http://localhost:8080${NC}"
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
echo -e "${YELLOW}⏳ Step 1/2: Waiting for instance to boot and SSH to be ready...${NC}"
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
    echo -e "${CYAN}🔒 Starting SSH tunnel to access WebUI securely...${NC}\n"
    echo -e "${GREEN}   Open your browser to: http://localhost:8080${NC}\n"
    echo -e "${YELLOW}📝 Next steps:${NC}"
    echo -e "${YELLOW}   1. Open http://localhost:8080 in your browser${NC}"
    echo -e "${YELLOW}   2. Click the model selector -> Pull a model${NC}"
    echo -e "${YELLOW}   3. Browse models at ollama.com/library or huggingface.co${NC}\n"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
    echo -e "${CYAN}🔐 SSH Tunnel Active - Press Ctrl+C to disconnect${NC}\n"
    
    # Start SSH tunnel with port forwarding
    ssh -i generated_key.pem -o StrictHostKeyChecking=no \
        -L 8080:localhost:8080 \
        -L 11434:localhost:11434 \
        -L 9099:localhost:9099 \
        ubuntu@${IP}
    exit 0
fi

# Show setup progress
echo -e "${YELLOW}⏳ Step 2/2: Installing Ollama and Open WebUI...${NC}"
echo -e "${BLUE}This will take 2-3 minutes.${NC}\n"

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
        
        # Check Docker installation
        echo "🐳 Docker & WebUI Status:"
        if systemctl is-active --quiet docker; then
            echo "   ✓ Docker: Running"
            if docker ps 2>/dev/null | grep -q open-webui; then
                echo "   ✓ Open WebUI: Running on localhost:8080"
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
    echo "🐳 Running Containers:"
    sudo docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
ENDSSH

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${MAGENTA}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${MAGENTA}║                    🎉 ALL READY! 🎉                        ║${NC}"
echo -e "${MAGENTA}╚════════════════════════════════════════════════════════════╝${NC}\n"
echo -e "${CYAN}🔒 Starting secure SSH tunnel...${NC}\n"
echo -e "${GREEN}   Open your browser to: http://localhost:8080${NC}\n"
echo -e "${YELLOW}   1. Open http://localhost:8080 in your browser${NC}"
echo -e "${YELLOW}   2. Click model selector -> Pull a model${NC}"
echo -e "${YELLOW}   3. Find models: ollama.com/library or huggingface.co${NC}\n"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
echo -e "${CYAN}🔐 SSH Tunnel Active - Keep this terminal open!${NC}"
echo -e "${CYAN}   Press Ctrl+C to disconnect${NC}\n"

# Start SSH tunnel with port forwarding
ssh -i generated_key.pem -o StrictHostKeyChecking=no \
    -L 8080:localhost:8080 \
    -L 11434:localhost:11434 \
    -L 9099:localhost:9099 \
    ubuntu@${IP}