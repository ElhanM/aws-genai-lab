#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Get the IP from terraform output
IP=$(terraform output -raw instance_ip 2>/dev/null)

if [ -z "$IP" ]; then
    echo -e "${RED}Error: Could not get instance IP. Did you run 'terraform apply'?${NC}"
    exit 1
fi

echo ""
echo -e "${BLUE}${BOLD}AWS GenAI Lab - Setup Progress Monitor${NC}"
echo -e "${YELLOW}Instance IP: ${IP}${NC}"
echo ""

# Fix permissions on the key
chmod 400 generated_key.pem 2>/dev/null || true

SSH_OPTS="-i generated_key.pem -o StrictHostKeyChecking=no -o ConnectTimeout=2 -o LogLevel=ERROR"

# Function to check if SSH is ready
check_ssh() {
    ssh $SSH_OPTS ubuntu@${IP} "exit" 2>/dev/null
    return $?
}

# Function to check if setup is complete
check_ready() {
    ssh $SSH_OPTS ubuntu@${IP} "test -f /var/lib/cloud/instance/ready" 2>/dev/null
    return $?
}

# Function to check if WebUI is running
check_webui() {
    ssh $SSH_OPTS ubuntu@${IP} "docker ps | grep -q open-webui" 2>/dev/null
    return $?
}

# Function to show connection instructions and start tunnel
start_tunnel() {
    echo ""
    echo -e "${GREEN}${BOLD}==========================================================${NC}"
    echo -e "${MAGENTA}${BOLD}                      ALL READY!${NC}"
    echo -e "${GREEN}${BOLD}==========================================================${NC}"
    echo ""
    echo -e "${CYAN}Starting secure SSH tunnel...${NC}"
    echo ""
    echo -e "${GREEN}${BOLD}Open your browser to: http://localhost:8080${NC}"
    echo ""
    echo -e "${YELLOW}Next steps:${NC}"
    echo -e "${YELLOW}  1. Open http://localhost:8080 in your browser${NC}"
    echo -e "${YELLOW}  2. Click model selector -> Pull a model${NC}"
    echo -e "${YELLOW}  3. Find models: ollama.com/library or huggingface.co${NC}"
    echo ""
    echo -e "${CYAN}SSH Tunnel Active & Interactive Shell Ready${NC}"
    echo -e "${YELLOW}  - You can run commands on the EC2 instance (e.g., 'docker ps', 'ollama list')${NC}"
    echo -e "${YELLOW}  - To disconnect: type 'exit' and press Enter${NC}"
    echo -e "${YELLOW}  - To reconnect: run './connect.sh' again${NC}"
    echo ""

    # Start SSH tunnel with port forwarding and interactive shell
    ssh -i generated_key.pem \
        -o StrictHostKeyChecking=no \
        -o ExitOnForwardFailure=yes \
        -o ServerAliveInterval=60 \
        -o ServerAliveCountMax=3 \
        -L 8080:localhost:8080 \
        -L 11434:localhost:11434 \
        -L 9099:localhost:9099 \
        ubuntu@${IP} || true

    echo -e "\n${GREEN}SSH tunnel closed successfully${NC}"
}

# Wait for SSH to be available
echo -e "${YELLOW}Step 1/2: Waiting for instance to boot...${NC}"
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
echo -e "\n${GREEN}SSH is ready!${NC}"
echo ""

# Check if setup is already complete
if check_ready && check_webui; then
    echo -e "${GREEN}${BOLD}Instance is fully configured and ready!${NC}"
    start_tunnel
    exit 0
fi

# Show setup progress
echo -e "${YELLOW}Step 2/2: Installing Ollama and Open WebUI...${NC}"
echo -e "${BLUE}This will take 2-3 minutes.${NC}"
echo ""

# Monitor progress with live updates
ssh $SSH_OPTS ubuntu@${IP} 'bash -s' << 'ENDSSH'
    export TERM=xterm

    show_progress() {
        echo ""
        echo "-----------------------------------------------------------"
        echo "  Installation Progress"
        echo "-----------------------------------------------------------"

        # Check Ollama service
        if systemctl is-active --quiet ollama 2>/dev/null; then
            echo "  Ollama:     Running"
        else
            echo "  Ollama:     Installing..."
        fi

        # Check Docker
        if systemctl is-active --quiet docker 2>/dev/null; then
            echo "  Docker:     Running"
        else
            echo "  Docker:     Installing..."
        fi

        # Check Open WebUI container
        if docker ps 2>/dev/null | grep -q open-webui; then
            echo "  Open WebUI: Running"
        else
            echo "  Open WebUI: Waiting..."
        fi

        echo ""

        # Show recent log lines
        if [ -f /var/log/user-data.log ]; then
            echo "  Recent activity:"
            tail -5 /var/log/user-data.log | sed 's/^/    /'
        fi
        echo "-----------------------------------------------------------"
    }

    # Show progress until ready
    while [ ! -f /var/lib/cloud/instance/ready ]; do
        show_progress
        sleep 4
    done

    # Wait for WebUI to be fully responsive
    echo ""
    echo "  Waiting for WebUI to accept connections..."
    for i in $(seq 1 30); do
        if curl -s -o /dev/null -w "%{http_code}" http://localhost:8080 2>/dev/null | grep -q "200\|301\|302"; then
            echo "  WebUI is now accessible!"
            break
        fi
        echo -n "."
        sleep 2
    done

    echo ""
    echo "-----------------------------------------------------------"
    echo "  SETUP COMPLETE"
    echo "-----------------------------------------------------------"
    echo ""
    echo "  Running containers:"
    sudo docker ps --format "table {{.Names}}\t{{.Status}}" 2>/dev/null
    echo ""
ENDSSH

# After monitoring is done, start the tunnel
start_tunnel