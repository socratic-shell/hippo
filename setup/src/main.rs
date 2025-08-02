#!/usr/bin/env cargo
//! Hippo Development Setup Tool
//!
//! Automatically builds the Rust Hippo server and configures it as an MCP server
//! for Q CLI or Claude Code.

use anyhow::{anyhow, Context, Result};
use clap::{Parser, ValueEnum};
use std::path::{Path, PathBuf};
use std::process::Command;

#[derive(Debug, Clone, ValueEnum)]
enum CLITool {
    #[value(name = "q")]
    QCli,
    #[value(name = "claude")]
    ClaudeCode,
    #[value(name = "both")]
    Both,
    #[value(name = "auto")]
    Auto,
}

#[derive(Debug, Clone, ValueEnum)]
enum ClaudeScope {
    #[value(name = "user")]
    User,
    #[value(name = "local")]
    Local,
    #[value(name = "project")]
    Project,
}

#[derive(Parser)]
#[command(
    name = "setup",
    about = "Build Rust Hippo server and set up for development with Q CLI or Claude Code",
    long_about = r#"
Build Rust Hippo server and set up for development with Q CLI or Claude Code

Examples:
  cargo setup                           # Install to PATH and setup for production use
  cargo setup --dev                     # Build in target/ for development
  cargo setup --tool q                  # Setup for Q CLI only
  cargo setup --tool claude             # Setup for Claude Code only
  cargo setup --tool both               # Setup for both tools
  cargo setup --memory-dir ~/my-hippo

Prerequisites:
  - Rust and Cargo (https://rustup.rs/)
  - Q CLI or Claude Code
"#
)]
struct Args {
    /// Path to store Hippo memories
    #[arg(long, default_value_os_t = default_memory_dir())]
    memory_dir: PathBuf,

    /// Which CLI tool to configure
    #[arg(long, default_value = "auto")]
    tool: CLITool,

    /// Scope for Claude Code MCP configuration
    #[arg(long, default_value = "user")]
    claude_scope: ClaudeScope,

    /// Skip MCP server registration
    #[arg(long)]
    skip_mcp: bool,

    /// Use development mode (build in target/ directory instead of installing to PATH)
    #[arg(long)]
    dev: bool,


}

fn default_memory_dir() -> PathBuf {
    home::home_dir()
        .unwrap_or_else(|| PathBuf::from("."))
        .join(".hippo")
}

fn main() -> Result<()> {
    let args = Args::parse();

    println!("🦛 Hippo Development Setup");
    println!("{}", "=".repeat(30));

    // Determine which tool to use
    let tool = match args.tool {
        CLITool::Auto => detect_available_tools()?,
        other => other,
    };

    // Check prerequisites
    check_rust()?;

    if !args.skip_mcp {
        match tool {
            CLITool::QCli => check_q_cli()?,
            CLITool::ClaudeCode => check_claude_code()?,
            CLITool::Both => {
                check_q_cli()?;
                check_claude_code()?;
            }
            CLITool::Auto => unreachable!("Auto should have been resolved earlier"),
        }
    }

    let memory_dir = args.memory_dir;

    // Setup MCP server(s)
    let mut success = true;
    if !args.skip_mcp {
        match tool {
            CLITool::QCli => {
                success = setup_q_cli_mcp(&memory_dir, args.dev)?;
            }
            CLITool::ClaudeCode => {
                success = setup_claude_code_mcp(&memory_dir, &args.claude_scope, args.dev)?;
            }
            CLITool::Both => {
                success = setup_q_cli_mcp(&memory_dir, args.dev)?
                    && setup_claude_code_mcp(&memory_dir, &args.claude_scope, args.dev)?;
            }
            CLITool::Auto => unreachable!("Auto should have been resolved earlier"),
        }
    } else {
        println!("⏭️  Skipping MCP server registration");
    }

    if success {
        print_next_steps(&memory_dir, &tool, args.dev)?;
    } else {
        println!("\n❌ Setup incomplete. Please fix the errors above and try again.");
        std::process::exit(1);
    }

    Ok(())
}

fn check_rust() -> Result<()> {
    if which::which("cargo").is_err() {
        return Err(anyhow!(
            "❌ Error: Cargo not found. Please install Rust first.\n   Visit: https://rustup.rs/"
        ));
    }
    Ok(())
}

fn check_q_cli() -> Result<()> {
    if which::which("q").is_err() {
        return Err(anyhow!(
            "❌ Error: Q CLI not found. Please install Q CLI first.\n   Visit: https://docs.aws.amazon.com/amazonq/latest/qdeveloper-ug/q-cli.html"
        ));
    }
    Ok(())
}

fn check_claude_code() -> Result<()> {
    if !is_claude_available() {
        return Err(anyhow!(
            "❌ Error: Claude Code not found. Please install Claude Code first.\n   Visit: https://claude.ai/code"
        ));
    }
    Ok(())
}

fn is_claude_available() -> bool {
    // Check both binary and config directory since claude might be an alias
    which::which("claude").is_ok() || home::home_dir().map_or(false, |home| home.join(".claude").exists())
}

fn detect_available_tools() -> Result<CLITool> {
    let has_q = which::which("q").is_ok();
    let has_claude = is_claude_available();

    match (has_q, has_claude) {
        (true, true) => Ok(CLITool::Both),
        (true, false) => Ok(CLITool::QCli),
        (false, true) => Ok(CLITool::ClaudeCode),
        (false, false) => Err(anyhow!(
            "❌ No supported CLI tools found. Please install Q CLI or Claude Code.\n   Q CLI: https://docs.aws.amazon.com/amazonq/latest/qdeveloper-ug/q-cli.html\n   Claude Code: https://claude.ai/code\n   Rust: https://rustup.rs/"
        )),
    }
}

fn get_repo_root() -> Result<PathBuf> {
    let current_exe = std::env::current_exe()
        .context("Failed to get current executable path")?;
    
    // Navigate up from target/debug/setup or target/release/setup to repo root
    let mut path = current_exe.parent()
        .and_then(|p| p.parent()) // target/
        .and_then(|p| p.parent()) // repo root
        .ok_or_else(|| anyhow!("Could not determine repository root"))?;
    
    // If we're running via cargo run, we might be in a different location
    // Try to find Cargo.toml in current dir or parents
    let mut current = std::env::current_dir().context("Failed to get current directory")?;
    loop {
        if current.join("Cargo.toml").exists() && current.join("rs").exists() {
            path = &current;
            break;
        }
        if let Some(parent) = current.parent() {
            current = parent.to_path_buf();
        } else {
            break;
        }
    }
    
    Ok(path.to_path_buf())
}

fn install_rust_server(repo_root: &Path) -> Result<PathBuf> {
    let rust_dir = repo_root.join("rs");
    
    println!("📦 Installing Rust Hippo server to PATH...");
    println!("   Installing from: {}", rust_dir.display());
    
    // Install the Rust server to ~/.cargo/bin
    let output = Command::new("cargo")
        .args(["install", "--path", ".", "--force"])
        .current_dir(&rust_dir)
        .output()
        .context("Failed to execute cargo install")?;
    
    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(anyhow!("❌ Failed to install Rust server:\n   Error: {}", stderr.trim()));
    }
    
    // The binary should now be available as 'hippo-server' in PATH
    let binary_name = "hippo-server";
    
    // Verify the binary is accessible
    if which::which(binary_name).is_err() {
        println!("⚠️  Warning: hippo-server not found in PATH after installation");
        
        // Try to give helpful guidance about PATH
        if let Some(home) = home::home_dir() {
            let cargo_bin = home.join(".cargo").join("bin");
            println!("   Make sure {} is in your PATH environment variable", cargo_bin.display());
            
            // Check if ~/.cargo/bin exists but isn't in PATH
            if cargo_bin.exists() {
                println!("   Add this to your shell profile (.bashrc, .zshrc, etc.):");
                println!("   export PATH=\"$HOME/.cargo/bin:$PATH\"");
            }
        } else {
            println!("   Make sure ~/.cargo/bin is in your PATH environment variable");
        }
    }
    
    println!("✅ Rust server installed successfully!");
    Ok(PathBuf::from(binary_name))
}

fn build_rust_server(repo_root: &Path) -> Result<PathBuf> {
    let rust_dir = repo_root.join("rs");
    
    println!("🔨 Building Rust Hippo server for development...");
    println!("   Building in: {}", rust_dir.display());
    
    // Build the Rust server
    let output = Command::new("cargo")
        .args(["build", "--release"])
        .current_dir(&rust_dir)
        .output()
        .context("Failed to execute cargo build")?;
    
    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(anyhow!("❌ Failed to build Rust server:\n   Error: {}", stderr.trim()));
    }
    
    // Verify the binary exists
    let binary_path = rust_dir.join("target").join("release").join("hippo-server");
    if !binary_path.exists() {
        return Err(anyhow!("❌ Build verification failed: Built binary not found at {}", binary_path.display()));
    }
    
    println!("✅ Rust server built successfully!");
    Ok(binary_path)
}

fn setup_q_cli_mcp(memory_dir: &Path, dev_mode: bool) -> Result<bool> {
    let repo_root = get_repo_root()?;
    
    // Choose build method based on mode
    let binary_path = if dev_mode {
        build_rust_server(&repo_root)?
    } else {
        install_rust_server(&repo_root)?
    };
    
    // Build the command arguments for the Rust binary
    let mut cmd = Command::new("q");
    cmd.args([
        "mcp", "add",
        "--name", "hippo",
        "--command", &binary_path.to_string_lossy(),
        "--args", "--memory-dir",
        "--args", &memory_dir.to_string_lossy(),
        "--env", "HIPPO_LOG=info",
        "--force",  // Always overwrite existing configuration
    ]);
    
    println!("🔧 Registering Rust Hippo MCP server with Q CLI...");
    println!("   Memory path: {}", memory_dir.display());
    println!("   Binary path: {}", binary_path.display());
    println!("   Logging: INFO level to {}/hippo.log", memory_dir.display());
    
    let output = cmd.output().context("Failed to execute q mcp add")?;
    
    if output.status.success() {
        println!("✅ MCP server 'hippo' registered successfully with Q CLI!");
        Ok(true)
    } else {
        let stderr = String::from_utf8_lossy(&output.stderr);
        println!("❌ Failed to register MCP server with Q CLI:");
        println!("   Error: {}", stderr.trim());
        Ok(false)
    }
}

fn setup_claude_code_mcp(memory_dir: &Path, scope: &ClaudeScope, dev_mode: bool) -> Result<bool> {
    let repo_root = get_repo_root()?;
    
    // Choose build method based on mode
    let binary_path = if dev_mode {
        build_rust_server(&repo_root)?
    } else {
        install_rust_server(&repo_root)?
    };
    
    let scope_str = match scope {
        ClaudeScope::User => "user",
        ClaudeScope::Local => "local",
        ClaudeScope::Project => "project",
    };
    
    // Claude Code uses -- to separate command from its arguments
    let mut cmd = Command::new("claude");
    cmd.args([
        "mcp", "add",
        "--scope", scope_str,
        "--env", "HIPPO_LOG=info",
        "hippo",
        &binary_path.to_string_lossy(),
        "--",
        "--memory-dir",
        &memory_dir.to_string_lossy(),
    ]);
    
    println!("🔧 Registering Rust Hippo MCP server with Claude Code...");
    println!("   Memory path: {}", memory_dir.display());
    println!("   Binary path: {}", binary_path.display());
    println!("   Scope: {}", scope_str);
    println!("   Logging: INFO level to {}/hippo.log", memory_dir.display());
    
    let output = cmd.output().context("Failed to execute claude mcp add")?;
    
    if output.status.success() {
        println!("✅ MCP server 'hippo' registered successfully with Claude Code!");
        Ok(true)
    } else {
        let stderr = String::from_utf8_lossy(&output.stderr);
        println!("❌ Failed to register MCP server with Claude Code:");
        println!("   Error: {}", stderr.trim());
        
        if stderr.contains("already exists") {
            println!("\n💡 Tip: Remove existing server with: claude mcp remove hippo");
        }
        
        Ok(false)
    }
}

fn print_next_steps(memory_dir: &Path, tool: &CLITool, dev_mode: bool) -> Result<()> {
    let repo_root = get_repo_root()?;
    let guidance_path = repo_root.join("guidance.md");
    
    if dev_mode {
        println!("\n🎉 Development setup complete! Rust Hippo server is ready.");
        println!("🔧 Running in development mode - server will use target/release/hippo-server");
    } else {
        println!("\n🎉 Production setup complete! Rust Hippo server is installed.");
        println!("📦 Server installed to PATH as 'hippo-server'");
    }
    
    match tool {
        CLITool::QCli | CLITool::Both => {
            println!("\n📝 For Q CLI:");
            println!("   Add guidance.md to your agent definition:");
            println!("   @{}", guidance_path.display());
            println!("\n🧪 Test with Q CLI:");
            println!("   q chat \"Record an insight: Rust server works great!\"");
        }
        _ => {}
    }
    
    match tool {
        CLITool::ClaudeCode | CLITool::Both => {
            println!("\n📝 For Claude Code:");
            println!("   Add this line to your CLAUDE.md or project instructions:");
            println!("   @{}", guidance_path.display());
            println!("\n🧪 Test with Claude Code:");
            println!("   claude chat \"Record an insight: Rust server works great!\"");
        }
        _ => {}
    }
    
    println!("\n💾 Your memories will be stored at: {}", memory_dir.display());
    println!("🚀 Performance: ~100-500ms startup vs 6s Python version");
    
    Ok(())
}
