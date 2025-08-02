//! MCP Integration Tests
//!
//! Tests that verify the MCP server can start up and handle basic tool calls.
//! These tests use the child process transport to spawn the server and communicate with it.

use rmcp::{
    model::CallToolRequestParam,
    transport::{ConfigureCommandExt, TokioChildProcess},
    ServiceExt,
};
use serde_json::{json, Value};
use std::time::Duration;
use tempfile::TempDir;
use tokio::time::timeout;

/// Test that the MCP server starts up and can list tools
#[tokio::test]
async fn test_mcp_server_startup_and_list_tools() {
    // Create a temporary directory for the test
    let temp_dir = TempDir::new().unwrap();
    let memory_dir = temp_dir.path().to_string_lossy();
    
    // Build the server binary path
    let server_path = std::env::current_dir()
        .unwrap()
        .join("target/debug/hippo-server");
    
    // Ensure the server binary exists
    if !server_path.exists() {
        panic!("Server binary not found at {:?}. Run 'cargo build' first.", server_path);
    }
    
    // Create transport to spawn the server as a child process
    let transport = TokioChildProcess::new(
        tokio::process::Command::new(&server_path).configure(|cmd| {
            cmd.arg("--memory-dir")
                .arg(memory_dir.as_ref());
        })
    ).expect("Failed to create child process transport");
    
    // Connect to the server with a timeout
    let client = timeout(
        Duration::from_secs(10),
        ().serve(transport)
    ).await
    .expect("Server startup timed out")
    .expect("Failed to connect to server");
    
    // Test 1: List tools - this verifies the server started and can respond
    let tools = timeout(
        Duration::from_secs(5),
        client.list_all_tools()
    ).await
    .expect("List tools timed out")
    .expect("Failed to list tools");
    
    // Verify we have the expected 4 tools
    assert_eq!(tools.len(), 4, "Expected 4 tools, got {}", tools.len());
    
    let tool_names: Vec<&str> = tools.iter().map(|t| t.name.as_ref()).collect();
    assert!(tool_names.contains(&"hippo_record_insight"), "Missing hippo_record_insight tool");
    assert!(tool_names.contains(&"hippo_search_insights"), "Missing hippo_search_insights tool");
    assert!(tool_names.contains(&"hippo_modify_insight"), "Missing hippo_modify_insight tool");
    assert!(tool_names.contains(&"hippo_reinforce_insight"), "Missing hippo_reinforce_insight tool");
    
    // Clean shutdown
    client.cancel().await.expect("Failed to cancel client");
}

/// Test basic tool functionality - record and search an insight
#[tokio::test]
async fn test_mcp_basic_tool_functionality() {
    // Create a temporary directory for the test
    let temp_dir = TempDir::new().unwrap();
    let memory_dir = temp_dir.path().to_string_lossy();
    
    // Build the server binary path
    let server_path = std::env::current_dir()
        .unwrap()
        .join("target/debug/hippo-server");
    
    // Create transport to spawn the server
    let transport = TokioChildProcess::new(
        tokio::process::Command::new(&server_path).configure(|cmd| {
            cmd.arg("--memory-dir")
                .arg(memory_dir.as_ref());
        })
    ).expect("Failed to create child process transport");
    
    // Connect to the server
    let client = timeout(
        Duration::from_secs(10),
        ().serve(transport)
    ).await
    .expect("Server startup timed out")
    .expect("Failed to connect to server");
    
    // Test 1: Record an insight
    let record_params = json!({
        "content": "MCP integration test insight",
        "situation": ["testing", "mcp integration"],
        "importance": 0.8
    });
    
    let record_result = timeout(
        Duration::from_secs(5),
        client.call_tool(CallToolRequestParam {
            name: "hippo_record_insight".into(),
            arguments: record_params.as_object().cloned(),
        })
    ).await
    .expect("Record insight timed out")
    .expect("Failed to record insight");
    
    // Verify the response indicates success
    assert_eq!(record_result.is_error, Some(false), "Record insight returned error: {:?}", record_result.content);
    
    // Extract the response text to verify it contains "Recorded insight with UUID"
    if let Some(content) = record_result.content.first() {
        if let Some(text_content) = content.raw.as_text() {
            assert!(text_content.text.contains("Recorded insight with UUID"), 
                   "Expected success message, got: {}", text_content.text);
        }
    }
    
    // Test 2: Search for the insight
    let search_params = json!({
        "query": "MCP integration test"
    });
    
    let search_result = timeout(
        Duration::from_secs(5),
        client.call_tool(CallToolRequestParam {
            name: "hippo_search_insights".into(),
            arguments: search_params.as_object().cloned(),
        })
    ).await
    .expect("Search insights timed out")
    .expect("Failed to search insights");
    
    // Verify the search response
    assert_eq!(search_result.is_error, Some(false), "Search insights returned error: {:?}", search_result.content);
    
    // Parse the search response to verify it contains our insight
    if let Some(content) = search_result.content.first() {
        if let Some(text_content) = content.raw.as_text() {
            let search_response: Value = serde_json::from_str(&text_content.text)
                .expect("Failed to parse search response JSON");
            
            // Verify we got results
            let total_count = search_response["total_count"].as_u64()
                .expect("Missing total_count in search response");
            assert!(total_count > 0, "Expected at least 1 search result, got {}", total_count);
            
            // Verify the result contains our test content
            let results = search_response["results"].as_array()
                .expect("Missing results array in search response");
            assert!(!results.is_empty(), "Expected non-empty results array");
            
            let first_result = &results[0];
            let insight_content = first_result["insight"]["content"].as_str()
                .expect("Missing content in search result");
            assert_eq!(insight_content, "MCP integration test insight", 
                      "Search result content doesn't match");
        }
    }
    
    // Clean shutdown
    client.cancel().await.expect("Failed to cancel client");
}

/// Test error handling - try to call a tool with invalid parameters
#[tokio::test]
async fn test_mcp_error_handling() {
    // Create a temporary directory for the test
    let temp_dir = TempDir::new().unwrap();
    let memory_dir = temp_dir.path().to_string_lossy();
    
    // Build the server binary path
    let server_path = std::env::current_dir()
        .unwrap()
        .join("target/debug/hippo-server");
    
    // Create transport to spawn the server
    let transport = TokioChildProcess::new(
        tokio::process::Command::new(&server_path).configure(|cmd| {
            cmd.arg("--memory-dir")
                .arg(memory_dir.as_ref());
        })
    ).expect("Failed to create child process transport");
    
    // Connect to the server
    let client = timeout(
        Duration::from_secs(10),
        ().serve(transport)
    ).await
    .expect("Server startup timed out")
    .expect("Failed to connect to server");
    
    // Test: Try to record an insight with invalid importance (> 1.0)
    let invalid_params = json!({
        "content": "Test insight",
        "situation": ["testing"],
        "importance": 1.5  // Invalid: > 1.0
    });
    
    let result = timeout(
        Duration::from_secs(5),
        client.call_tool(CallToolRequestParam {
            name: "hippo_record_insight".into(),
            arguments: invalid_params.as_object().cloned(),
        })
    ).await
    .expect("Tool call timed out");
    
    // Verify we get an error response (should be Err, not Ok with is_error=true)
    assert!(result.is_err(), "Expected error response for invalid importance, got: {:?}", result);
    
    // Clean shutdown
    client.cancel().await.expect("Failed to cancel client");
}
