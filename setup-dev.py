#!/usr/bin/env python3
"""
Hippo Development Setup Script

Automatically configures Hippo as an MCP server for Q CLI.
"""

import argparse
import subprocess
import sys
from pathlib import Path
import shutil


def check_q_cli():
    """Check if Q CLI is available."""
    if not shutil.which("q"):
        print("❌ Error: Q CLI not found. Please install Q CLI first.")
        print("   Visit: https://docs.aws.amazon.com/amazonq/latest/qdeveloper-ug/q-cli.html")
        return False
    return True


def get_repo_root():
    """Get the repository root directory."""
    return Path(__file__).parent.absolute()


def setup_mcp_server(memory_path: Path, force: bool = False):
    """Register Hippo as an MCP server with Q CLI."""
    repo_root = get_repo_root()
    
    # Build the command arguments
    cmd = [
        "q", "mcp", "add",
        "--name", "hippo",
        "--command", "uv",
        "--args", "run",
        "--args", "--directory",
        "--args", str(repo_root),
        "--args", "python",
        "--args", "-m",
        "--args", "hippo.server",
        "--args", "--hippo-file",
        "--args", str(memory_path),
        "--scope", "global"
    ]
    
    if force:
        cmd.append("--force")
    
    try:
        print(f"🔧 Registering Hippo MCP server...")
        print(f"   Memory path: {memory_path}")
        print(f"   Repository: {repo_root}")
        
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print("✅ MCP server 'hippo' registered successfully!")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to register MCP server:")
        print(f"   Command: {' '.join(cmd)}")
        print(f"   Error: {e.stderr.strip()}")
        
        if "already exists" in e.stderr and not force:
            print("\n💡 Tip: Use --force to overwrite existing server")
        
        return False


def print_next_steps(memory_path: Path):
    """Print instructions for completing the setup."""
    repo_root = get_repo_root()
    guidance_path = repo_root / "guidance.md"
    
    print("\n🎉 Setup complete!")
    print("\n📝 Next step: Add guidance to your Q CLI context")
    print("   Add this line to your CLAUDE.md or global context file:")
    print(f"   @{guidance_path}")
    print("\n🧪 Test your setup:")
    print("   q chat \"Record an insight: Setup script works great!\"")
    print(f"\n💾 Your memories will be stored at: {memory_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Set up Hippo for development with Q CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python setup-dev.py                    # Use default memory path
  python setup-dev.py --memory-path ~/my-hippo.json
  python setup-dev.py --force            # Overwrite existing server
        """
    )
    
    parser.add_argument(
        "--memory-path",
        type=Path,
        default=Path.home() / ".hippo" / "hippo.json",
        help="Path to store Hippo memories (default: ~/.hippo/hippo.json)"
    )
    
    parser.add_argument(
        "--skip-mcp",
        action="store_true",
        help="Skip MCP server registration"
    )
    
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing MCP server configuration"
    )
    
    args = parser.parse_args()
    
    print("🦛 Hippo Development Setup")
    print("=" * 30)
    
    # Check prerequisites
    if not args.skip_mcp and not check_q_cli():
        sys.exit(1)
    
    # Ensure memory directory exists
    memory_path = args.memory_path.expanduser().resolve()
    memory_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"📁 Ensured memory directory exists: {memory_path.parent}")
    
    # Setup MCP server
    success = True
    if not args.skip_mcp:
        success = setup_mcp_server(memory_path, args.force)
    else:
        print("⏭️  Skipping MCP server registration")
    
    if success:
        print_next_steps(memory_path)
    else:
        print("\n❌ Setup incomplete. Please fix the errors above and try again.")
        sys.exit(1)


if __name__ == "__main__":
    main()
