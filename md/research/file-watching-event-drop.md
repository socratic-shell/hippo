# Watchdog Event Handling: Coalescing and Dropping Reference

## Event Data Structure

Watchdog provides structured event objects with these key attributes:

```python
# Example of what you receive in event handlers
FileSystemEvent:
├── event_type: str          # 'created', 'modified', 'deleted', 'moved'
├── src_path: str           # Full path to the file
├── is_directory: bool      # Whether it's a directory or file
└── timestamp: float        # When the event occurred (if available)

# For move events specifically:
FileMovedEvent:
├── dest_path: str          # Destination path for moves
└── (all above attributes)
```

## Critical Limitation: Event Coalescing and Dropping

**⚠️ WARNING: Events are frequently coalesced and can be dropped entirely**

This is a fundamental limitation that affects reliability, especially for high-frequency file operations like Hippo's concurrent memory storage.

### 1. Rapid Modification Coalescing

When a file is modified multiple times quickly, the OS often combines these into fewer events:

```python
# What actually happens:
write_to_file("uuid1.json", data_v1)  # Event 1
write_to_file("uuid1.json", data_v2)  # Event 2  
write_to_file("uuid1.json", data_v3)  # Event 3

# What watchdog might deliver:
# Only: FileModifiedEvent for uuid1.json (final state)
# Missing: The intermediate v1 and v2 states
```

### 2. Platform-Specific Dropping Behavior

**Linux (inotify)**:
- Can drop events when kernel buffer overflows
- Common with >1000 events/second or large directories
- Buffer exhaustion leads to `IN_Q_OVERFLOW` errors
- High-frequency operations cause event loss

**macOS (FSEvents)**:
- Deliberately coalesces events by design
- Optimized for "something changed in this directory" notifications
- Less granular per-file tracking
- May batch multiple file changes into single events

**Windows (ReadDirectoryChangesW)**:
- Can miss events under high system load
- Particularly problematic during bulk operations
- Buffer limitations cause event dropping

### 3. Real-World Impact for UUID-Based Storage

This creates specific challenges for concurrent memory operations:

```python
# Dangerous scenario for Hippo:
Session_A: Creates uuid1.json with memory_data_A
Session_B: Immediately modifies uuid1.json with memory_data_B  
Session_C: Deletes uuid1.json

# Possible watchdog outcome:
# You might only see: "deleted" event
# Missing: The creation and modification events
# Result: Other sessions never learn about memory_data_A or memory_data_B
```

## Mitigation Strategies

### 1. Event Debouncing

Collect rapid events and process them after a quiet period:

```python
class DebouncedHandler:
    def __init__(self):
        self.debounce_seconds = 0.5  # Wait for quiet period
        self.pending_events = {}
        
    def on_any_event(self, event):
        # Cancel previous timer for this file
        if event.src_path in self.pending_events:
            self.pending_events[event.src_path].cancel()
        
        # Schedule new processing after debounce period
        timer = threading.Timer(
            self.debounce_seconds,
            self._process_event,
            args=[event]
        )
        self.pending_events[event.src_path] = timer
        timer.start()
```

### 2. Periodic Reconciliation

Compare filesystem state vs in-memory cache to catch missed events:

```python
def periodic_sync_check(self):
    """Detect and correct missed events"""
    # Get current filesystem state
    current_files = set(self.storage_directory.glob("*.json"))
    current_uuids = {f.stem for f in current_files}
    
    # Compare with cached state
    cached_uuids = set(self.memory_cache.keys())
    
    # Handle discrepancies
    missing_from_cache = current_uuids - cached_uuids
    deleted_from_filesystem = cached_uuids - current_uuids
    
    # Load missing files
    for uuid_str in missing_from_cache:
        filepath = self.storage_directory / f"{uuid_str}.json"
        self._load_memory_file(str(filepath))
    
    # Remove deleted entries
    for uuid_str in deleted_from_filesystem:
        self.memory_cache.pop(uuid_str, None)

# Run every 30-60 seconds as safety net
```

### 3. File Content Verification

Use checksums or timestamps to detect missed modifications:

```python
import hashlib
from pathlib import Path

class FileIntegrityChecker:
    def __init__(self):
        self.file_hashes = {}  # uuid -> content_hash
        
    def verify_file_integrity(self, uuid_str: str):
        """Detect missed modification events"""
        filepath = self.storage_directory / f"{uuid_str}.json"
        
        if not filepath.exists():
            return False
            
        # Calculate current file hash
        current_hash = hashlib.md5(filepath.read_bytes()).hexdigest()
        stored_hash = self.file_hashes.get(uuid_str)
        
        if stored_hash and stored_hash != current_hash:
            # We missed a modification event - reload file
            print(f"Detected missed modification for {uuid_str}")
            self._load_memory_file(str(filepath))
            
        # Update stored hash
        self.file_hashes[uuid_str] = current_hash
        return True
```

### 4. Hybrid Architecture

Combine real-time events with periodic safety checks:

```python
class HybridFileWatcher:
    def __init__(self, storage_directory):
        self.storage_directory = Path(storage_directory)
        self.memory_cache = {}
        
        # Fast path: Real-time events via watchdog
        self.observer = Observer()
        self.observer.schedule(
            DebouncedHandler(self), 
            str(storage_directory)
        )
        
        # Safety net: Periodic reconciliation
        self.sync_timer = threading.Timer(30.0, self.periodic_sync_check)
        
    def start(self):
        """Start both real-time watching and periodic sync"""
        self.observer.start()
        self.sync_timer.start()
        
    def stop(self):
        """Clean shutdown"""
        self.observer.stop()
        self.sync_timer.cancel()
        self.observer.join()
```

## Implementation Recommendations for Hippo

### Architecture Decision

**Use watchdog as primary mechanism with safety nets:**

1. **Primary**: Watchdog for sub-100ms real-time updates
2. **Secondary**: 30-second periodic reconciliation scans  
3. **Verification**: Content hashing for critical operations
4. **Fallback**: Polling observer for network filesystems

### Code Pattern

```python
class RobustHippoWatcher:
    def __init__(self, storage_directory):
        self.primary_events = 0
        self.reconciliation_fixes = 0
        
    def on_file_event(self, event):
        """Fast path - process immediately"""
        self.primary_events += 1
        self._process_file_change(event.src_path)
        
    def periodic_reconciliation(self):
        """Safety net - catch missed events"""
        fixes = self._sync_filesystem_with_cache()
        if fixes > 0:
            self.reconciliation_fixes += fixes
            print(f"Reconciliation fixed {fixes} missed events")
            
    def get_reliability_stats(self):
        """Monitor system health"""
        total_events = self.primary_events + self.reconciliation_fixes
        if total_events > 0:
            miss_rate = self.reconciliation_fixes / total_events
            return {
                'primary_events': self.primary_events,
                'missed_events': self.reconciliation_fixes,
                'miss_rate_percent': miss_rate * 100
            }
```

### Key Takeaways

1. **Never rely solely on watchdog events** - always implement reconciliation
2. **Use debouncing** (500ms) to handle rapid file changes gracefully
3. **Plan for eventual consistency** rather than immediate consistency
4. **Monitor miss rates** to tune reconciliation frequency
5. **Consider file locking** for critical write operations
6. **Test under load** to understand your specific miss patterns

### Performance vs Reliability Trade-offs

- **Real-time events**: Sub-100ms latency, but ~1-5% miss rate under load
- **Periodic scanning**: 100% reliable, but 30-60 second latency
- **Hybrid approach**: Best of both - fast updates with guaranteed consistency

The hybrid approach is recommended for Hippo's use case where both responsiveness and data integrity are critical.