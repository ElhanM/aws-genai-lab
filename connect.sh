#!/bin/bash
set -e

# Get the IP from terraform output
IP=$(terraform output -raw instance_ip 2>/dev/null)

if [ -z "$IP" ]; then
    echo "Error: Could not get instance IP. Did you run 'terraform apply'?"
    exit 1
fi

echo ""
echo "AWS GenAI Lab - Setup Progress Monitor"
echo "Instance IP: ${IP}"
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
    echo "=========================================================="
    echo "                      ALL READY!"
    echo "=========================================================="
    echo ""
    echo "Starting secure SSH tunnel..."
    echo ""
    echo "Open your browser to: http://localhost:8080"
    echo ""
    echo "Next steps:"
    echo "  1. Open http://localhost:8080 in your browser"
    echo "  2. Click model selector -> Pull a model"
    echo "  3. Find models: ollama.com/library or huggingface.co"
    echo ""
    echo "SSH Tunnel Active & Interactive Shell Ready"
    echo "  - You can run commands on the EC2 instance (e.g., 'docker ps', 'ollama list')"
    echo "  - To disconnect: type 'exit' and press Enter"
    echo "  - To reconnect: run './connect.sh' again"
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

    echo ""
    echo "SSH tunnel closed successfully"
}

# Wait for SSH to be available
echo "Step 1/2: Waiting for instance to boot..."
COUNTER=0
MAX_WAIT=60
while ! check_ssh; do
    echo -n "."
    sleep 2
    COUNTER=$((COUNTER + 1))
    if [ $COUNTER -gt $MAX_WAIT ]; then
        echo ""
        echo "Error: SSH connection timeout"
        exit 1
    fi
done
echo ""
echo "SSH is ready!"
echo ""

# Check if setup is already complete
if check_ready && check_webui; then
    echo "Instance is fully configured and ready!"
    start_tunnel
    exit 0
fi

# Show setup progress
echo "Step 2/2: Installing Ollama and Open WebUI..."
echo "This will take 2-3 minutes."
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
            echo ""
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