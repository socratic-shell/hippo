#!/usr/bin/env python3

import json
import subprocess
import sys

def test_record_insight():
    """Test recording an insight via MCP"""
    
    # Create MCP request
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "hippo_record_insight",
            "arguments": {
                "content": "Debug test insight to check metadata system",
                "importance": 0.8,
                "situation": ["debug test", "metadata verification"]
            }
        }
    }
    
    # Send request to server
    try:
        result = subprocess.run(
            ["hippo-server", "--memory-dir", "/Users/nikomat/.hippo"],
            input=json.dumps(request),
            text=True,
            capture_output=True,
            timeout=10
        )
        
        print("STDOUT:", result.stdout)
        print("STDERR:", result.stderr)
        print("Return code:", result.returncode)
        
    except subprocess.TimeoutExpired:
        print("Server timed out")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_record_insight()
