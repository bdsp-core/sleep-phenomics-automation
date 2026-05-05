import psutil
import time

def wait_for_memory(threshold_gb, timeout):
    """Wait until at least threshold_gb of memory is available."""
    threshold_bytes = threshold_gb * (1024 ** 3)  # Convert GB to bytes
    print(f"Waiting for at least {threshold_gb} GB of free memory...")
    
    while True:
        available_memory = psutil.virtual_memory().available
        print(f"Available memory: {available_memory / (1024 ** 3):.2f} GB")
        
        if available_memory >= threshold_bytes:
            print("Sufficient memory is available. Proceeding...")
            break
        else:
            time.sleep(timeout)  # Check memory availability every second

# Removed Spikenet-related functions as they are no longer needed