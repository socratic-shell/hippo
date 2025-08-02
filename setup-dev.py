#!/usr/bin/env python3
"""
Hippo Development Setup Script

Automatically builds the Rust Hippo server and configures it as an MCP server 
for Q CLI or Claude Code.
"""

import argparse
import shutil
import subprocess
import sys
from enum import Enum, auto
from pathlib import Path


class CLITool(Enum):
    Q_CLI = auto()
    CLAUDE_CODE = auto()
    BOTH = auto()


def check_rust():
    """Check if Rust and Cargo are available."""
    if not shutil.which("cargo"):
        print("❌ Error: Cargo not found. Please install Rust first.")
        print("   Visit: https://rustup.rs/")
        return False
    return True


def check_q_cli():
    """Check if Q CLI is available."""
    if not shutil.which("q"):
        print("❌ Error: Q CLI not found. Please install Q CLI first.")
        print("   Visit: https://docs.aws.amazon.com/amazonq/latest/qdeveloper-ug/q-cli.html")
        return False
    return True


def check_claude_code():
    """Check if Claude Code is available."""
    if not _is_claude_available():
        print("❌ Error: Claude Code not found. Please install Claude Code first.")
        print("   Visit: https://claude.ai/code")
        return False
    return True


def _is_claude_available():
    """Check if Claude Code is available via binary or config directory."""
    # 💡: Check both binary and config directory since claude might be an alias
    return shutil.which("claude") is not None or (Path.home() / ".claude").exists()


def detect_available_tools():
    """Detect which CLI tools are available."""
    has_q = shutil.which("q") is not None
    has_claude = _is_claude_available()

    if has_q and has_claude:
        return CLITool.BOTH
    elif has_q:
        return CLITool.Q_CLI
    elif has_claude:
        return CLITool.CLAUDE_CODE
    else:
        return None


def get_repo_root():
    """Get the repository root directory."""
    return Path(__file__).parent.absolute()


def build_rust_server(repo_root: Path):
    """Build the Rust Hippo server."""
    rust_dir = repo_root / "rs"
    
    try:
        print("🔨 Building Rust Hippo server...")
        print(f"   Building in: {rust_dir}")
        
        # Build the Rust server
        result = subprocess.run(
            ["cargo", "build", "--release"],
            cwd=rust_dir,
            capture_output=True,
            text=True,
            check=True
        )
        
        # Verify the binary exists
        binary_path = rust_dir / "target" / "release" / "hippo-server"
        if not binary_path.exists():
            raise FileNotFoundError(f"Built binary not found at {binary_path}")
            
        print("✅ Rust server built successfully!")
        return binary_path
        
    except subprocess.CalledProcessError as e:
        print("❌ Failed to build Rust server:")
        print(f"   Error: {e.stderr.strip()}")
        return None
    except FileNotFoundError as e:
        print(f"❌ Build verification failed: {e}")
        return None


def setup_q_cli_mcp(memory_dir: Path, force: bool = False):
    """Register Hippo as an MCP server with Q CLI."""
    repo_root = get_repo_root()
    
    # Build the Rust server first
    binary_path = build_rust_server(repo_root)
    if not binary_path:
        return False

    # Build the command arguments for the Rust binary
    cmd = [
        "q", "mcp", "add",
        "--name", "hippo",
        "--command", str(binary_path),
        "--args", "--memory-dir",
        "--args", str(memory_dir),
        "--env", "HIPPO_LOG=info"
    ]

    if force:
        cmd.append("--force")

    try:
        print("🔧 Registering Rust Hippo MCP server with Q CLI...")
        print(f"   Memory path: {memory_dir}")
        print(f"   Binary path: {binary_path}")  
        print(f"   Logging: INFO level to {memory_dir}/hippo.log")

        subprocess.run(cmd, capture_output=True, text=True, check=True)
        print("✅ MCP server 'hippo' registered successfully with Q CLI!")
        return True

    except subprocess.CalledProcessError as e:
        print("❌ Failed to register MCP server with Q CLI:")
        print(f"   Command: {' '.join(cmd)}")
        print(f"   Error: {e.stderr.strip()}")

        if "already exists" in e.stderr and not force:
            print("\n💡 Tip: Use --force to overwrite existing server")

        return False


def setup_claude_code_mcp(memory_dir: Path, scope: str = "user"):
    """Register Hippo as an MCP server with Claude Code."""
    repo_root = get_repo_root()
    
    # Build the Rust server first
    binary_path = build_rust_server(repo_root)
    if not binary_path:
        return False

    # Claude Code uses -- to separate command from its arguments
    cmd_args = [
        "mcp", "add",
        "--scope", scope,
        "--env", "HIPPO_LOG=info",
        "hippo",
        str(binary_path),
        "--",
        "--memory-dir",
        str(memory_dir)
    ]

    try:
        print("🔧 Registering Rust Hippo MCP server with Claude Code...")
        print(f"   Memory path: {memory_dir}")
        print(f"   Binary path: {binary_path}")
        print(f"   Scope: {scope}")
        print(f"   Logging: INFO level to {memory_dir}/hippo.log")

        # Use shell=True to handle bash aliases properly
        cmd_str = f"claude {' '.join(cmd_args)}"
        result = subprocess.run(
            cmd_str, 
            shell=True, 
            capture_output=True, 
            text=True, 
            check=True
        )
        print("✅ MCP server 'hippo' registered successfully with Claude Code!")
        return True

    except subprocess.CalledProcessError as e:
        print("❌ Failed to register MCP server with Claude Code:")
        print(f"   Command: {cmd_str}")
        print(f"   Error: {e.stderr.strip()}")

        if "already exists" in e.stderr:
            print("\n💡 Tip: Remove existing server with: claude mcp remove hippo")

        return False
    except FileNotFoundError:
        print("❌ Failed to register MCP server with Claude Code:")
        print("   'claude' command not found. Please ensure Claude Code is properly installed")
        print("   and accessible in your shell.")
        return False


def print_next_steps(memory_dir: Path, tool: CLITool):
    """Print instructions for completing the setup."""
    repo_root = get_repo_root()
    guidance_path = repo_root / "guidance.md"

    print("\n🎉 Setup complete! Rust Hippo server is ready.")

    if tool in (CLITool.Q_CLI, CLITool.BOTH):
        print("\n📝 For Q CLI:")
        print("   Add this line to your CLAUDE.md or global context file:")
        print(f"   @{guidance_path}")
        print("\n🧪 Test with Q CLI:")
        print("   q chat \"Record an insight: Rust server works great!\"")

    if tool in (CLITool.CLAUDE_CODE, CLITool.BOTH):
        print("\n📝 For Claude Code:")
        print("   Add this line to your CLAUDE.md or project instructions:")
        print(f"   @{guidance_path}")
        print("\n🧪 Test with Claude Code:")
        print("   claude chat \"Record an insight: Rust server works great!\"")

    print(f"\n💾 Your memories will be stored at: {memory_dir}")
    print(f"🚀 Performance: ~100-500ms startup vs 6s Python version")


def main():
    parser = argparse.ArgumentParser(
        description="Build Rust Hippo server and set up for development with Q CLI or Claude Code",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python setup-dev.py                    # Auto-detect and use available CLI
  python setup-dev.py --tool q           # Setup for Q CLI only
  python setup-dev.py --tool claude      # Setup for Claude Code only
  python setup-dev.py --tool both        # Setup for both tools
  python setup-dev.py --memory-dir ~/my-hippo
  python setup-dev.py --force            # Overwrite existing Q CLI config

Prerequisites:
  - Rust and Cargo (https://rustup.rs/)
  - Q CLI or Claude Code
        """
    )

    parser.add_argument(
        "--memory-dir",
        type=Path,
        default=Path.home() / ".hippo",
        help="Path to store Hippo memories (default: ~/.hippo)"
    )

    parser.add_argument(
        "--tool",
        choices=["q", "claude", "both", "auto"],
        default="auto",
        help="Which CLI tool to configure (default: auto-detect)"
    )

    parser.add_argument(
        "--claude-scope",
        choices=["user", "local", "project"],
        default="user",
        help="Scope for Claude Code MCP configuration (default: user)"
    )

    parser.add_argument(
        "--skip-mcp",
        action="store_true",
        help="Skip MCP server registration"
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing Q CLI configuration"
    )

    args = parser.parse_args()

    print("🦛 Hippo Development Setup")
    print("=" * 30)

    # Determine which tool to use
    if args.tool == "auto":
        available = detect_available_tools()
        if available is None:
            print(
                "❌ No supported CLI tools found. "
                "Please install Q CLI or Claude Code."
            )
            print("   Q CLI: https://docs.aws.amazon.com/amazonq/latest/qdeveloper-ug/q-cli.html")
            print("   Claude Code: https://claude.ai/code")
            print("   Rust: https://rustup.rs/")
            sys.exit(1)
        tool = available
    else:
        tool_map = {
            "q": CLITool.Q_CLI,
            "claude": CLITool.CLAUDE_CODE,
            "both": CLITool.BOTH
        }
        tool = tool_map[args.tool]

    # Check prerequisites
    if not check_rust():
        sys.exit(1)
        
    if not args.skip_mcp:
        if tool in (CLITool.Q_CLI, CLITool.BOTH) and not check_q_cli():
            sys.exit(1)
        if tool in (CLITool.CLAUDE_CODE, CLITool.BOTH) and not check_claude_code():
            sys.exit(1)

    # Ensure memory directory exists
    memory_dir = args.memory_dir.expanduser().resolve()
    memory_dir.parent.mkdir(parents=True, exist_ok=True)
    print(f"📁 Ensured memory directory exists: {memory_dir.parent}")

    # Setup MCP server(s)
    success = True
    if not args.skip_mcp:
        if tool in (CLITool.Q_CLI, CLITool.BOTH):
            success = setup_q_cli_mcp(memory_dir, args.force) and success
        if tool in (CLITool.CLAUDE_CODE, CLITool.BOTH):
            success = setup_claude_code_mcp(memory_dir, args.claude_scope) and success
    else:
        print("⏭️  Skipping MCP server registration")

    if success:
        print_next_steps(memory_dir, tool)
    else:
        print("\n❌ Setup incomplete. Please fix the errors above and try again.")
        sys.exit(1)


if __name__ == "__main__":
    main()
