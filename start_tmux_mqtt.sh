#!/bin/bash

SESSION="mqtt_session"

# Check if tmux is installed
if ! command -v tmux &> /dev/null
then
    echo "tmux is not installed. Please install it first."
    exit 1
fi

# Kill any existing tmux session with the same name
tmux kill-session -t $SESSION 2>/dev/null

# Start a new tmux session in detached mode
tmux new-session -d -s $SESSION

# Split the window horizontally into 3 panes
tmux split-window -v -t $SESSION:0
tmux split-window -v -t $SESSION:0.0

# Rename the panes
tmux select-pane -t $SESSION:0.0 -T "MQTT Adapter"
tmux select-pane -t $SESSION:0.1 -T "MQTT Sender"
tmux select-pane -t $SESSION:0.2 -T "MQTT Receiver"

# Start commands in each pane (replace with your actual commands)
tmux send-keys -t $SESSION:0.0 "echo 'Starting MQTT Adapter...'" C-m
tmux send-keys -t $SESSION:0.1 "echo 'Starting MQTT Sender...'" C-m
tmux send-keys -t $SESSION:0.2 "echo 'Starting MQTT Receiver...'" C-m

# Attach to the tmux session
tmux attach -t $SESSION