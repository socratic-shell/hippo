# Installation

Installation has two steps. You have to [configure the MCP server](#configure-the-mcp-server) and [add guidance into your global context](#adding-guidance-to-your-context) that instructs the LLM to use it appropriately.

You may prefer to read the instructions for your client:

* [Claude Code instructions](#claude-code-instructions)
* [Q CLI instructions](#q-cli-instructions)

## Choosing where to store your memories

Right now Hippo stories its data in a JSON file. You can put it anywhere, but I suggest you version it with git. We expect to change how this works later on.

## Configure the MCP server

The MCP server is currently in prototype form. To add it to your system, 

* Checkout the repository into some directory `$HIPPO`.
* Choose a path `$HIPPO_FILE` to store the JSON file with your memories (this should be an absolute path, or relative to `$HIPPO`).
* Add a MCP server named "hippo" with the command show below.

The command to run hippo is

```bash
uv run -d $HIPPO python -m hippo.server --hippo-file $HIPPO_FILE
```

## Adding guidance to your context

Add something like this to your user prompt or system configuration:

```
{{#include ../guidance.md}}
```

## Per-client instructions

### Claude Code instructions

Clone the hippo repository into `$HIPPO` and then:

1. **Create directory for Hippo data:**
   ```bash
   mkdir -p ~/.hippo
   ```

2. **Add MCP server to Claude Code configuration:**
   
   Add this to your Claude Code MCP configuration file (usually `~/.claude/mcp_servers.json`):
   
   ```json
   {
     "mcpServers": {
       "hippo": {
         "command": "uv",
         "args": [
           "run", 
           "--directory", 
           "/path/to/your/hippo/checkout",
           "python", 
           "-m", 
           "hippo.server", 
           "--hippo-file", 
           "~/.hippo/hippo.json"
         ],
         "timeout": 30000
       }
     }
   }
   ```
   
   Replace `/path/to/your/hippo/checkout` with the actual path where you cloned the repository.

3. **Add guidance to your context:**
   
   Add `@$HIPPO/guidance.md` to your CLAUDE.md file.

### Q CLI instructions

```bash
# Create directory for Hippo data
mkdir -p ~/.hippo

# Add Hippo MCP server to Q CLI
q mcp add \
  --name hippo \
  --command "uv" \
  --args "run" \
  --args "--directory" \
  --args "$HIPPO" \
  --args "python" \
  --args "-m" \
  --args "hippo.server" \
  --args "--hippo-file" \
  --args "~/.hippo/hippo.json" \
  --scope global
```

Also run `/context add --global $HIPPO/guidance.md`.

## Frequently asked questions

### Something isn't working, how do I debug?

By default, Hippo only logs ERROR level messages and above to minimize noise during normal operation. To enable full debug logging, set `HIPPO_LOG=/path/to/a/log/file` and it will generate comprehensive debug logs there. This includes all DEBUG, INFO, WARNING, and ERROR messages which can help diagnose issues.