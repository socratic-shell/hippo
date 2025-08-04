# Project Detection System Design

## Overview

The project detection system will automatically analyze the working directory to generate structured project context for better insight matching. This replaces abstract situational tags with concrete, project-specific context.

## Detection Checklist

### Configuration Files
- `Cargo.toml` → Rust project (extract name, description, workspace info)
- `pyproject.toml` → Python project (extract name, description, dependencies)
- `package.json` → Node.js/TypeScript project
- `go.mod` → Go project
- `pom.xml` → Java/Maven project
- `build.gradle` → Gradle project
- `composer.json` → PHP project
- `Gemfile` → Ruby project
- `requirements.txt` → Python dependencies (fallback)
- `setup.py` → Python project (legacy)

### Documentation Files
- `book.toml` → mdbook documentation project
- `mkdocs.yml` → MkDocs documentation
- `Sphinx` config → Sphinx documentation
- `README.md` → Project description (extract title/description)
- `SUMMARY.md` → mdbook structure

### Build/Deploy Files
- `Dockerfile` → Containerized project
- `docker-compose.yml` → Multi-service project
- `.github/workflows/` → CI/CD setup
- `Makefile` → Build automation
- `.gitignore` → Version control patterns

### Source Code Extensions
Count files by extension to determine primary languages:
- `.rs` → Rust
- `.py` → Python  
- `.ts`, `.tsx` → TypeScript
- `.js`, `.jsx` → JavaScript
- `.go` → Go
- `.java` → Java
- `.cpp`, `.cc`, `.cxx` → C++
- `.c`, `.h` → C
- `.md` → Documentation
- `.toml`, `.yaml`, `.yml`, `.json` → Configuration

### Special Directories
- `src/` → Source code
- `lib/` → Library code
- `bin/` → Binaries
- `docs/`, `documentation/` → Documentation
- `tests/`, `test/` → Test code
- `examples/` → Example code
- `.git/` → Git repository
- `node_modules/` → Node.js dependencies
- `target/` → Rust build artifacts
- `__pycache__/` → Python cache
- `.venv/`, `venv/` → Python virtual environment

## Project Report Structure

```rust
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProjectReport {
    pub directory: PathBuf,
    pub detected_files: DetectedFiles,
    pub extracted_metadata: ExtractedMetadata,
    pub project_types: Vec<ProjectType>,
    pub summary: String,
    pub git_info: Option<GitInfo>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DetectedFiles {
    pub config_files: Vec<String>,
    pub source_extensions: HashMap<String, u32>, // extension -> count
    pub special_directories: Vec<String>,
    pub documentation_files: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExtractedMetadata {
    pub cargo: Option<CargoMetadata>,
    pub python: Option<PythonMetadata>,
    pub node: Option<NodeMetadata>,
    pub git: Option<GitMetadata>,
    pub readme: Option<ReadmeMetadata>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CargoMetadata {
    pub name: String,
    pub description: Option<String>,
    pub version: String,
    pub workspace_members: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum ProjectType {
    Rust,
    Python,
    TypeScript,
    JavaScript,
    Go,
    Java,
    Documentation,
    Polyglot(Vec<String>), // Multiple primary languages
}
```

## Implementation Plan

### Phase 1: Basic Detection
1. **File System Scanner**: Walk directory tree, collect file patterns
2. **Config Parser**: Extract metadata from common config files
3. **Project Type Classifier**: Determine primary project type(s)
4. **Report Generator**: Create structured project report

### Phase 2: Metadata Extraction
1. **Cargo.toml Parser**: Extract Rust project metadata
2. **pyproject.toml Parser**: Extract Python project metadata  
3. **package.json Parser**: Extract Node.js metadata
4. **Git Info Extractor**: Get repository info, branch, remote
5. **README Parser**: Extract project title and description

### Phase 3: Smart Classification
1. **Monorepo Detection**: Handle multiple project roots
2. **Language Weighting**: Determine primary vs secondary languages
3. **Project Purpose Classification**: Library, application, documentation, etc.
4. **Dependency Analysis**: Extract key dependencies for similarity matching

## Example Output

For the Hippo project, the detection would produce:

```json
{
  "directory": "/Users/nikomat/dev/hippo",
  "detected_files": {
    "config_files": ["Cargo.toml", "pyproject.toml", "book.toml"],
    "source_extensions": {
      ".rs": 6,
      ".py": 8, 
      ".md": 12,
      ".toml": 4,
      ".yml": 2
    },
    "special_directories": ["rs/src/", "py/hippo/", "md/", ".git/", "target/"]
  },
  "extracted_metadata": {
    "cargo": {
      "name": "hippo-server",
      "description": null,
      "workspace_members": ["rs", "setup"]
    },
    "python": {
      "name": "hippo-mcp-server", 
      "description": "AI-Generated Insights Memory System MCP Server"
    },
    "git": {
      "remote": "socratic-shell/hippo",
      "branch": "main"
    }
  },
  "project_types": ["Polyglot(Rust, Python)", "Documentation"],
  "summary": "Rust MCP server with Python components and mdbook documentation for AI memory system"
}
```

## Integration Points

### Storage Schema Update
Add `project_context` field to insight storage:
```rust
pub struct Insight {
    // ... existing fields
    pub project_context: Option<ProjectReport>,
}
```

### Search Enhancement
Modify search algorithm to:
1. **Exact directory match**: Highest relevance for same project
2. **Project type similarity**: Medium relevance for similar tech stacks
3. **Semantic similarity**: Use project descriptions for embedding comparison
4. **Cross-project learning**: Lower relevance for insights from different projects

### MCP Protocol Update
Request structured context from LLM:
- **Project directory**: Auto-detected or user-provided
- **Project description**: LLM-provided semantic context
- **Task description**: What the user is currently working on

## Performance Considerations

### Caching Strategy
- Cache project reports per directory
- Invalidate cache when config files change
- Use file modification times for cache validation

### Scanning Limits
- Respect `.gitignore` patterns
- Skip large directories (node_modules, target, .venv)
- Limit directory depth (default: 3 levels)
- Timeout for large projects (default: 5 seconds)

## Error Handling

### Graceful Degradation
- If detection fails, fall back to directory path only
- Handle permission errors gracefully
- Continue with partial information if some parsers fail

### User Override
- Allow manual project type specification
- Support custom project descriptions
- Enable detection disable for privacy

## Future Extensions

### Advanced Detection
- **Framework Detection**: React, Django, Rails, etc.
- **Architecture Patterns**: Microservices, monolith, etc.
- **Deployment Targets**: AWS, Docker, Kubernetes
- **Testing Frameworks**: pytest, Jest, etc.

### Similarity Metrics
- **Dependency Overlap**: Compare package lists
- **File Structure Similarity**: Compare directory patterns
- **Commit History Analysis**: Extract project evolution patterns
- **Team Size Indicators**: Number of contributors, commit frequency
