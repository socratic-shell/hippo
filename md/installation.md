# Installation

Installation has two steps. You have to [configure the MCP server](#configure-the-mcp-server) and [add guidance into your global context](#adding-guidance-to-your-context) that instructs the LLM to use it appropriately.

You may prefer to read the instructions for your client:

* [Claude Code instructions](#claude-code-instructions)
* [Q CLI instructions](#q-cli-instructions)

## Choosing where to store your memories

Hippo stores its data in a directory structure with individual JSON files for each insight and metadata. You can put this directory anywhere, but I suggest you version it with git for backup purposes.

## Quick Setup (Recommended)

The easiest way to set up Hippo is using the automated setup tool:

```bash
# Clone the repository
git clone https://github.com/socratic-shell/hippo.git
cd hippo

# Automatic setup (production mode - installs to PATH)
cargo setup

# Or development mode (builds to target/ for fast iteration)
cargo setup --dev

# Custom memory location
cargo setup --memory-dir ~/my-project/hippo-memories

# See all options
cargo setup --help
```

This tool will:
- Build/install the Rust Hippo server
- Register Hippo as a global MCP server in your CLI tool
- Create the memory storage directory
- Provide instructions for adding the guidance context

## Manual Setup (Alternative)

If you prefer to set up manually or need custom configuration:

### Prerequisites

- **Rust and Cargo** (install from [rustup.rs](https://rustup.rs/))
- **Q CLI** or **Claude Code**

### Build the Server

```bash
# Clone the repository
git clone https://github.com/socratic-shell/hippo.git
cd hippo

# Build the Rust server
cargo build --release --manifest-path rs/Cargo.toml
```

The command to run hippo is:

```bash
/path/to/hippo/rs/target/release/hippo-server --memory-dir $HIPPO_MEMORY_DIR
```

## Adding guidance to your context

Add something like this to your user prompt or system configuration:

```
{{#include ../guidance.md}}
```

## Per-client instructions

### Claude Code instructions

**Option 1: Use automated setup (recommended)**
```bash
cargo setup --tool claude
```

**Option 2: Manual setup**

1. **Create directory for Hippo data:**
   ```bash
   mkdir -p ~/.hippo
   ```

2. **Build the server:**
   ```bash
   cargo build --release --manifest-path rs/Cargo.toml
   ```

3. **Add MCP server to Claude Code configuration:**
   
   Add this to your Claude Code MCP configuration file (usually `~/.claude/mcp_servers.json`):
   
   ```json
   {
     "mcpServers": {
       "hippo": {
         "command": "/path/to/your/hippo/rs/target/release/hippo-server",
         "args": [
           "--memory-dir", 
           "~/.hippo"
         ],
         "env": {
           "HIPPO_LOG": "info"
         }
       }
     }
   }
   ```
   
   Replace `/path/to/your/hippo` with the actual path where you cloned the repository.

4. **Add guidance to your context:**
   
   Add `@/path/to/your/hippo/guidance.md` to your CLAUDE.md file.

### Q CLI instructions

**Option 1: Use automated setup (recommended)**
```bash
cargo setup --tool q
```

**Option 2: Manual setup**

```bash
# Create directory for Hippo data
mkdir -p ~/.hippo

# Build the server
cargo build --release --manifest-path rs/Cargo.toml

# Add Hippo MCP server to Q CLI
q mcp add \
  --name hippo \
  --command "/path/to/your/hippo/rs/target/release/hippo-server" \
  --args "--memory-dir" \
  --args "~/.hippo" \
  --env "HIPPO_LOG=info" \
  --force
```

Also add `@/path/to/your/hippo/guidance.md` to your agent definition.

## Frequently asked questions

### Something isn't working, how do I debug?

By default, Hippo only logs ERROR level messages and above to minimize noise during normal operation. To enable full debug logging, set `HIPPO_LOG=debug` in your MCP server configuration and it will generate comprehensive debug logs. This includes all DEBUG, INFO, WARNING, and ERROR messages which can help diagnose issues.

### What's the difference between production and development mode?

- **Production mode** (`cargo setup`): Installs the binary to your PATH using `cargo install`. The binary is available system-wide and you can delete the source directory after installation.
- **Development mode** (`cargo setup --dev`): Builds to the `target/` directory. Faster for development iteration but requires keeping the source directory.