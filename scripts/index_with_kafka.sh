#!/bin/bash

# =============================================================================
# Kafka Indexing Script
# Starts Producer and Consumer processes to scrape, stream via Kafka, and index
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# PID files
PRODUCER_PID_FILE="/tmp/kafka_producer.pid"
CONSUMER_PID_FILE="/tmp/kafka_consumer.pid"

# Log files
LOG_DIR="$PROJECT_ROOT/logs"
PRODUCER_LOG="$LOG_DIR/producer.log"
CONSUMER_LOG="$LOG_DIR/consumer.log"

# Training data file
TRAINING_URLS_FILE="$PROJECT_ROOT/data/training_urls.txt"

# Ensure log directory exists
mkdir -p "$LOG_DIR"

# Default URLs to scrape
DEFAULT_URLS=(
    "https://en.wikipedia.org/wiki/Machine_learning"
    "https://en.wikipedia.org/wiki/Deep_learning"
    "https://en.wikipedia.org/wiki/Artificial_intelligence"
    "https://en.wikipedia.org/wiki/Neural_network"
    "https://en.wikipedia.org/wiki/Natural_language_processing"
)

# Function to print colored messages
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if Docker services are running
check_services() {
    log_info "Checking Docker services..."
    
    cd "$PROJECT_ROOT"
    
    # Check if docker-compose is running
    if ! docker-compose ps | grep -q "Up"; then
        log_error "Docker services are not running!"
        log_info "Starting Docker services..."
        docker-compose up -d
        log_info "Waiting 30 seconds for services to be ready..."
        sleep 30
    fi
    
    # Check Kafka
    if ! docker-compose ps kafka | grep -q "Up"; then
        log_error "Kafka is not running!"
        exit 1
    fi
    
    # Check OpenSearch
    if ! curl -s http://localhost:9200 > /dev/null 2>&1; then
        log_error "OpenSearch is not responding on port 9200!"
        exit 1
    fi
    
    log_success "All services are running!"
}

# Function to load URLs from file
load_urls_from_file() {
    local file="$1"
    local urls=()
    
    if [ ! -f "$file" ]; then
        log_error "File not found: $file"
        return 1
    fi
    
    while IFS= read -r line; do
        # Skip empty lines and comments
        [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
        urls+=("$line")
    done < "$file"
    
    echo "${urls[@]}"
}

# Function to start the consumer
start_consumer() {
    log_info "Starting Kafka Consumer..."
    
    cd "$PROJECT_ROOT"
    export PYTHONPATH="$PROJECT_ROOT"
    
    # Start consumer in background
    nohup python3 src/pipeline/pipeline_runner.py consumer \
        --batch-size 50 \
        > "$CONSUMER_LOG" 2>&1 &
    
    CONSUMER_PID=$!
    echo $CONSUMER_PID > "$CONSUMER_PID_FILE"
    
    sleep 2
    
    if ps -p $CONSUMER_PID > /dev/null 2>&1; then
        log_success "Consumer started with PID: $CONSUMER_PID"
        log_info "Consumer log: $CONSUMER_LOG"
    else
        log_error "Failed to start consumer!"
        cat "$CONSUMER_LOG"
        exit 1
    fi
}

# Function to start the producer
start_producer() {
    local urls=("$@")
    
    if [ ${#urls[@]} -eq 0 ]; then
        urls=("${DEFAULT_URLS[@]}")
        log_info "No URLs provided, using default URLs..."
    fi
    
    log_info "Starting Kafka Producer with ${#urls[@]} URLs..."
    
    cd "$PROJECT_ROOT"
    export PYTHONPATH="$PROJECT_ROOT"
    
    # Build the URL arguments
    URL_ARGS=""
    for url in "${urls[@]}"; do
        URL_ARGS="$URL_ARGS $url"
    done
    
    # Start producer in background
    nohup python3 src/pipeline/pipeline_runner.py producer \
        --urls $URL_ARGS \
        > "$PRODUCER_LOG" 2>&1 &
    
    PRODUCER_PID=$!
    echo $PRODUCER_PID > "$PRODUCER_PID_FILE"
    
    sleep 2
    
    if ps -p $PRODUCER_PID > /dev/null 2>&1; then
        log_success "Producer started with PID: $PRODUCER_PID"
        log_info "Producer log: $PRODUCER_LOG"
    else
        log_error "Failed to start producer!"
        cat "$PRODUCER_LOG"
        exit 1
    fi
}

# Function to stop processes
stop_processes() {
    log_info "Stopping Kafka processes..."
    
    # Stop producer
    if [ -f "$PRODUCER_PID_FILE" ]; then
        PRODUCER_PID=$(cat "$PRODUCER_PID_FILE")
        if ps -p $PRODUCER_PID > /dev/null 2>&1; then
            kill $PRODUCER_PID 2>/dev/null || true
            log_success "Producer (PID: $PRODUCER_PID) stopped"
        fi
        rm -f "$PRODUCER_PID_FILE"
    fi
    
    # Stop consumer
    if [ -f "$CONSUMER_PID_FILE" ]; then
        CONSUMER_PID=$(cat "$CONSUMER_PID_FILE")
        if ps -p $CONSUMER_PID > /dev/null 2>&1; then
            kill $CONSUMER_PID 2>/dev/null || true
            log_success "Consumer (PID: $CONSUMER_PID) stopped"
        fi
        rm -f "$CONSUMER_PID_FILE"
    fi
    
    # Also kill any remaining python processes for the pipeline
    pkill -f "pipeline_runner.py producer" 2>/dev/null || true
    pkill -f "pipeline_runner.py consumer" 2>/dev/null || true
    
    log_success "All processes stopped!"
}

# Function to show status
show_status() {
    echo ""
    echo "=========================================="
    echo "         KAFKA INDEXING STATUS           "
    echo "=========================================="
    echo ""
    
    # Producer status
    if [ -f "$PRODUCER_PID_FILE" ]; then
        PRODUCER_PID=$(cat "$PRODUCER_PID_FILE")
        if ps -p $PRODUCER_PID > /dev/null 2>&1; then
            echo -e "Producer: ${GREEN}RUNNING${NC} (PID: $PRODUCER_PID)"
        else
            echo -e "Producer: ${RED}STOPPED${NC}"
        fi
    else
        echo -e "Producer: ${YELLOW}NOT STARTED${NC}"
    fi
    
    # Consumer status
    if [ -f "$CONSUMER_PID_FILE" ]; then
        CONSUMER_PID=$(cat "$CONSUMER_PID_FILE")
        if ps -p $CONSUMER_PID > /dev/null 2>&1; then
            echo -e "Consumer: ${GREEN}RUNNING${NC} (PID: $CONSUMER_PID)"
        else
            echo -e "Consumer: ${RED}STOPPED${NC}"
        fi
    else
        echo -e "Consumer: ${YELLOW}NOT STARTED${NC}"
    fi
    
    echo ""
    echo "Logs:"
    echo "  Producer: $PRODUCER_LOG"
    echo "  Consumer: $CONSUMER_LOG"
    echo ""
    
    # Show recent log entries
    if [ -f "$PRODUCER_LOG" ]; then
        echo "Last 5 lines of Producer log:"
        tail -5 "$PRODUCER_LOG" 2>/dev/null || echo "  (empty)"
        echo ""
    fi
    
    if [ -f "$CONSUMER_LOG" ]; then
        echo "Last 5 lines of Consumer log:"
        tail -5 "$CONSUMER_LOG" 2>/dev/null || echo "  (empty)"
        echo ""
    fi
}

# Function to wait for producer to finish
wait_for_producer() {
    if [ -f "$PRODUCER_PID_FILE" ]; then
        PRODUCER_PID=$(cat "$PRODUCER_PID_FILE")
        log_info "Waiting for producer (PID: $PRODUCER_PID) to finish..."
        
        while ps -p $PRODUCER_PID > /dev/null 2>&1; do
            sleep 5
            echo -n "."
        done
        echo ""
        log_success "Producer finished!"
    fi
}

# Function to run full indexing workflow
run_indexing() {
    local urls=("$@")
    
    echo ""
    echo "=========================================="
    echo "     KAFKA INDEXING WORKFLOW             "
    echo "=========================================="
    echo ""
    
    # Check services
    check_services
    
    # Stop any existing processes
    stop_processes
    
    # Start consumer first (it will wait for messages)
    start_consumer
    
    # Give consumer time to connect
    sleep 3
    
    # Start producer with URLs
    start_producer "${urls[@]}"
    
    echo ""
    log_info "Both processes are running!"
    log_info "Producer is scraping URLs and sending to Kafka..."
    log_info "Consumer is reading from Kafka and indexing to OpenSearch..."
    echo ""
    
    # Show status
    show_status
    
    echo ""
    log_info "To monitor progress:"
    echo "  - Producer log: tail -f $PRODUCER_LOG"
    echo "  - Consumer log: tail -f $CONSUMER_LOG"
    echo "  - Kafka UI: http://localhost:8088"
    echo "  - OpenSearch: http://localhost:9200/_cat/indices"
    echo ""
    log_info "To stop: $0 stop"
    echo ""
}

# Function to show help
show_help() {
    echo ""
    echo "Usage: $0 <command> [urls...]"
    echo ""
    echo "Commands:"
    echo "  start [url1 url2 ...]  Start producer and consumer with given URLs"
    echo "                         If no URLs provided, uses default Wikipedia articles"
    echo "  start-file [file]      Start with URLs from a file (default: data/training_urls.txt)"
    echo "  start-all              Start with ALL training URLs from data/training_urls.txt"
    echo "  stop                   Stop all running processes"
    echo "  status                 Show status of running processes"
    echo "  wait                   Wait for producer to finish, then stop consumer"
    echo "  help                   Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 start"
    echo "  $0 start https://en.wikipedia.org/wiki/Python https://en.wikipedia.org/wiki/Java"
    echo "  $0 start-all           # Use all URLs from data/training_urls.txt"
    echo "  $0 start-file my_urls.txt"
    echo "  $0 stop"
    echo "  $0 status"
    echo ""
    echo "Training URLs file: $TRAINING_URLS_FILE"
    if [ -f "$TRAINING_URLS_FILE" ]; then
        local count=$(grep -v '^#' "$TRAINING_URLS_FILE" | grep -v '^$' | wc -l)
        echo "  Contains $count URLs"
    fi
    echo ""
}

# Main script
case "${1:-}" in
    start)
        shift
        run_indexing "$@"
        ;;
    start-all)
        log_info "Loading ALL training URLs from $TRAINING_URLS_FILE..."
        if [ -f "$TRAINING_URLS_FILE" ]; then
            mapfile -t ALL_URLS < <(grep -v '^#' "$TRAINING_URLS_FILE" | grep -v '^$')
            log_info "Found ${#ALL_URLS[@]} URLs to process"
            run_indexing "${ALL_URLS[@]}"
        else
            log_error "Training URLs file not found: $TRAINING_URLS_FILE"
            exit 1
        fi
        ;;
    start-file)
        FILE="${2:-$TRAINING_URLS_FILE}"
        log_info "Loading URLs from $FILE..."
        if [ -f "$FILE" ]; then
            mapfile -t FILE_URLS < <(grep -v '^#' "$FILE" | grep -v '^$')
            log_info "Found ${#FILE_URLS[@]} URLs to process"
            run_indexing "${FILE_URLS[@]}"
        else
            log_error "File not found: $FILE"
            exit 1
        fi
        ;;
    stop)
        stop_processes
        ;;
    status)
        show_status
        ;;
    wait)
        wait_for_producer
        log_info "Giving consumer 10 seconds to finish processing..."
        sleep 10
        stop_processes
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        if [ -n "${1:-}" ]; then
            # If URLs are provided directly without 'start' command
            run_indexing "$@"
        else
            show_help
        fi
        ;;
esac
