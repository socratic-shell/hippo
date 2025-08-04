use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::fs;
use tracing::debug;

/// Complete project analysis report
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProjectReport {
    pub directory: PathBuf,
    pub detected_files: DetectedFiles,
    pub extracted_metadata: ExtractedMetadata,
    pub project_types: Vec<ProjectType>,
    pub summary: String,
    pub git_info: Option<GitInfo>,
}

/// Files and patterns detected during directory scan
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DetectedFiles {
    pub config_files: Vec<String>,
    pub source_extensions: HashMap<String, u32>, // extension -> count
    pub special_directories: Vec<String>,
    pub documentation_files: Vec<String>,
}

/// Metadata extracted from configuration files
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExtractedMetadata {
    pub cargo: Option<CargoMetadata>,
    pub python: Option<PythonMetadata>,
    pub node: Option<NodeMetadata>,
    pub git: Option<GitMetadata>,
    pub readme: Option<ReadmeMetadata>,
}

/// Rust project metadata from Cargo.toml
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CargoMetadata {
    pub name: String,
    pub description: Option<String>,
    pub version: String,
    pub workspace_members: Vec<String>,
}

/// Python project metadata from pyproject.toml
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PythonMetadata {
    pub name: String,
    pub description: Option<String>,
    pub version: Option<String>,
    pub dependencies: Vec<String>,
}

/// Node.js project metadata from package.json
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NodeMetadata {
    pub name: String,
    pub description: Option<String>,
    pub version: String,
    pub dependencies: Vec<String>,
}

/// Git repository information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GitMetadata {
    pub remote: Option<String>,
    pub branch: Option<String>,
    pub is_dirty: bool,
}

/// Git repository information (for project report)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GitInfo {
    pub remote: Option<String>,
    pub branch: Option<String>,
    pub is_dirty: bool,
}

/// README file metadata
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ReadmeMetadata {
    pub title: Option<String>,
    pub description: Option<String>,
}

/// Detected project types
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

/// Project detection configuration
#[derive(Debug, Clone)]
pub struct DetectionConfig {
    pub max_depth: usize,
    pub timeout_seconds: u64,
    pub respect_gitignore: bool,
    pub skip_directories: Vec<String>,
}

impl Default for DetectionConfig {
    fn default() -> Self {
        Self {
            max_depth: 3,
            timeout_seconds: 5,
            respect_gitignore: true,
            skip_directories: vec![
                "node_modules".to_string(),
                "target".to_string(),
                ".venv".to_string(),
                "venv".to_string(),
                "__pycache__".to_string(),
                ".git".to_string(),
                ".mypy_cache".to_string(),
                ".pytest_cache".to_string(),
            ],
        }
    }
}

/// Main project detector
pub struct ProjectDetector {
    config: DetectionConfig,
}

impl ProjectDetector {
    pub fn new(config: DetectionConfig) -> Self {
        Self { config }
    }

    pub fn with_default_config() -> Self {
        Self::new(DetectionConfig::default())
    }

    /// Analyze a directory and generate a project report
    pub fn analyze_directory(&self, directory: &Path) -> Result<ProjectReport> {
        debug!("Analyzing directory: {}", directory.display());

        let detected_files = self.scan_directory(directory)?;
        let extracted_metadata = self.extract_metadata(directory, &detected_files)?;
        let project_types = self.classify_project_types(&detected_files, &extracted_metadata);
        let summary = self.generate_summary(&project_types, &extracted_metadata);
        let git_info = extracted_metadata.git.as_ref().map(|g| GitInfo {
            remote: g.remote.clone(),
            branch: g.branch.clone(),
            is_dirty: g.is_dirty,
        });

        Ok(ProjectReport {
            directory: directory.to_path_buf(),
            detected_files,
            extracted_metadata,
            project_types,
            summary,
            git_info,
        })
    }

    /// Scan directory for files and patterns
    fn scan_directory(&self, directory: &Path) -> Result<DetectedFiles> {
        let mut config_files = Vec::new();
        let mut source_extensions = HashMap::new();
        let mut special_directories = Vec::new();
        let mut documentation_files = Vec::new();

        self.scan_recursive(
            directory,
            0,
            &mut config_files,
            &mut source_extensions,
            &mut special_directories,
            &mut documentation_files,
        )?;

        Ok(DetectedFiles {
            config_files,
            source_extensions,
            special_directories,
            documentation_files,
        })
    }

    /// Recursive directory scanning with depth limit
    fn scan_recursive(
        &self,
        dir: &Path,
        depth: usize,
        config_files: &mut Vec<String>,
        source_extensions: &mut HashMap<String, u32>,
        special_directories: &mut Vec<String>,
        documentation_files: &mut Vec<String>,
    ) -> Result<()> {
        if depth >= self.config.max_depth {
            return Ok(());
        }

        let entries = fs::read_dir(dir)
            .with_context(|| format!("Failed to read directory: {}", dir.display()))?;

        for entry in entries {
            let entry = entry?;
            let path = entry.path();
            let file_name = entry.file_name().to_string_lossy().to_string();

            if path.is_dir() {
                // Check for special directories
                if self.is_special_directory(&file_name) {
                    special_directories.push(file_name.clone());
                }

                // Skip directories we don't want to scan
                if self.should_skip_directory(&file_name) {
                    continue;
                }

                // Recurse into subdirectories
                self.scan_recursive(
                    &path,
                    depth + 1,
                    config_files,
                    source_extensions,
                    special_directories,
                    documentation_files,
                )?;
            } else {
                // Check for configuration files
                if self.is_config_file(&file_name) {
                    config_files.push(file_name.clone());
                }

                // Check for documentation files
                if self.is_documentation_file(&file_name) {
                    documentation_files.push(file_name.clone());
                }

                // Count source file extensions
                if let Some(extension) = path.extension() {
                    let ext = format!(".{}", extension.to_string_lossy());
                    if self.is_source_extension(&ext) {
                        *source_extensions.entry(ext).or_insert(0) += 1;
                    }
                }
            }
        }

        Ok(())
    }

    /// Check if a filename is a configuration file
    fn is_config_file(&self, filename: &str) -> bool {
        matches!(
            filename,
            "Cargo.toml"
                | "pyproject.toml"
                | "package.json"
                | "go.mod"
                | "pom.xml"
                | "build.gradle"
                | "composer.json"
                | "Gemfile"
                | "requirements.txt"
                | "setup.py"
                | "book.toml"
                | "mkdocs.yml"
                | "Dockerfile"
                | "docker-compose.yml"
                | "Makefile"
        )
    }

    /// Check if a filename is a documentation file
    fn is_documentation_file(&self, filename: &str) -> bool {
        matches!(
            filename,
            "README.md"
                | "README.rst"
                | "README.txt"
                | "SUMMARY.md"
                | "CHANGELOG.md"
                | "CONTRIBUTING.md"
                | "LICENSE"
                | "LICENSE.md"
        )
    }

    /// Check if a directory name is special/significant
    fn is_special_directory(&self, dirname: &str) -> bool {
        matches!(
            dirname,
            "src"
                | "lib"
                | "bin"
                | "docs"
                | "documentation"
                | "tests"
                | "test"
                | "examples"
                | ".git"
                | ".github"
                | "target"
                | "__pycache__"
                | ".venv"
                | "venv"
                | "node_modules"
        )
    }

    /// Check if we should skip scanning this directory
    fn should_skip_directory(&self, dirname: &str) -> bool {
        self.config.skip_directories.contains(&dirname.to_string())
    }

    /// Check if a file extension indicates source code
    fn is_source_extension(&self, extension: &str) -> bool {
        matches!(
            extension,
            ".rs" | ".py"
                | ".ts"
                | ".tsx"
                | ".js"
                | ".jsx"
                | ".go"
                | ".java"
                | ".cpp"
                | ".cc"
                | ".cxx"
                | ".c"
                | ".h"
                | ".md"
                | ".toml"
                | ".yaml"
                | ".yml"
                | ".json"
        )
    }

    /// Extract metadata from configuration files
    fn extract_metadata(
        &self,
        directory: &Path,
        detected_files: &DetectedFiles,
    ) -> Result<ExtractedMetadata> {
        let mut metadata = ExtractedMetadata {
            cargo: None,
            python: None,
            node: None,
            git: None,
            readme: None,
        };

        // Extract Cargo.toml metadata
        if detected_files.config_files.contains(&"Cargo.toml".to_string()) {
            metadata.cargo = self.extract_cargo_metadata(directory).ok();
        }

        // Extract pyproject.toml metadata
        if detected_files.config_files.contains(&"pyproject.toml".to_string()) {
            metadata.python = self.extract_python_metadata(directory).ok();
        }

        // Extract package.json metadata
        if detected_files.config_files.contains(&"package.json".to_string()) {
            metadata.node = self.extract_node_metadata(directory).ok();
        }

        // Extract git metadata
        if detected_files.special_directories.contains(&".git".to_string()) {
            metadata.git = self.extract_git_metadata(directory).ok();
        }

        // Extract README metadata
        if detected_files.documentation_files.iter().any(|f| f.starts_with("README")) {
            metadata.readme = self.extract_readme_metadata(directory).ok();
        }

        Ok(metadata)
    }

    /// Extract metadata from Cargo.toml
    fn extract_cargo_metadata(&self, directory: &Path) -> Result<CargoMetadata> {
        let cargo_path = directory.join("Cargo.toml");
        let content = fs::read_to_string(&cargo_path)
            .with_context(|| format!("Failed to read {}", cargo_path.display()))?;

        let cargo_toml: toml::Value = toml::from_str(&content)
            .with_context(|| "Failed to parse Cargo.toml")?;

        let package = cargo_toml.get("package");
        let workspace = cargo_toml.get("workspace");

        let name = if let Some(pkg) = package {
            pkg.get("name")
                .and_then(|n| n.as_str())
                .unwrap_or("unknown")
                .to_string()
        } else {
            "workspace".to_string()
        };

        let description = package
            .and_then(|pkg| pkg.get("description"))
            .and_then(|d| d.as_str())
            .map(|s| s.to_string());

        let version = package
            .and_then(|pkg| pkg.get("version"))
            .and_then(|v| v.as_str())
            .unwrap_or("0.0.0")
            .to_string();

        let workspace_members = workspace
            .and_then(|ws| ws.get("members"))
            .and_then(|m| m.as_array())
            .map(|arr| {
                arr.iter()
                    .filter_map(|v| v.as_str())
                    .map(|s| s.to_string())
                    .collect()
            })
            .unwrap_or_default();

        Ok(CargoMetadata {
            name,
            description,
            version,
            workspace_members,
        })
    }

    /// Extract metadata from pyproject.toml
    fn extract_python_metadata(&self, directory: &Path) -> Result<PythonMetadata> {
        let pyproject_path = directory.join("pyproject.toml");
        let content = fs::read_to_string(&pyproject_path)
            .with_context(|| format!("Failed to read {}", pyproject_path.display()))?;

        let pyproject_toml: toml::Value = toml::from_str(&content)
            .with_context(|| "Failed to parse pyproject.toml")?;

        let project = pyproject_toml
            .get("project")
            .context("No [project] section in pyproject.toml")?;

        let name = project
            .get("name")
            .and_then(|n| n.as_str())
            .unwrap_or("unknown")
            .to_string();

        let description = project
            .get("description")
            .and_then(|d| d.as_str())
            .map(|s| s.to_string());

        let version = project
            .get("version")
            .and_then(|v| v.as_str())
            .map(|s| s.to_string());

        let dependencies = project
            .get("dependencies")
            .and_then(|d| d.as_array())
            .map(|arr| {
                arr.iter()
                    .filter_map(|v| v.as_str())
                    .map(|s| s.to_string())
                    .collect()
            })
            .unwrap_or_default();

        Ok(PythonMetadata {
            name,
            description,
            version,
            dependencies,
        })
    }

    /// Extract metadata from package.json (placeholder)
    fn extract_node_metadata(&self, _directory: &Path) -> Result<NodeMetadata> {
        // TODO: Implement package.json parsing
        Err(anyhow::anyhow!("Node.js metadata extraction not implemented"))
    }

    /// Extract git repository metadata (placeholder)
    fn extract_git_metadata(&self, _directory: &Path) -> Result<GitMetadata> {
        // TODO: Implement git metadata extraction
        Err(anyhow::anyhow!("Git metadata extraction not implemented"))
    }

    /// Extract README metadata (placeholder)
    fn extract_readme_metadata(&self, _directory: &Path) -> Result<ReadmeMetadata> {
        // TODO: Implement README parsing
        Err(anyhow::anyhow!("README metadata extraction not implemented"))
    }

    /// Classify project types based on detected files and metadata
    fn classify_project_types(
        &self,
        detected_files: &DetectedFiles,
        metadata: &ExtractedMetadata,
    ) -> Vec<ProjectType> {
        let mut types = Vec::new();

        // Check for specific project types based on config files and metadata
        if metadata.cargo.is_some() || detected_files.config_files.contains(&"Cargo.toml".to_string()) {
            types.push(ProjectType::Rust);
        }

        if metadata.python.is_some() || detected_files.config_files.contains(&"pyproject.toml".to_string()) {
            types.push(ProjectType::Python);
        }

        if detected_files.config_files.contains(&"package.json".to_string()) {
            // Determine if TypeScript or JavaScript based on file extensions
            let has_ts = detected_files.source_extensions.contains_key(".ts") 
                || detected_files.source_extensions.contains_key(".tsx");
            if has_ts {
                types.push(ProjectType::TypeScript);
            } else {
                types.push(ProjectType::JavaScript);
            }
        }

        if detected_files.config_files.contains(&"go.mod".to_string()) {
            types.push(ProjectType::Go);
        }

        if detected_files.config_files.contains(&"pom.xml".to_string()) 
            || detected_files.config_files.contains(&"build.gradle".to_string()) {
            types.push(ProjectType::Java);
        }

        // Check for documentation projects
        if detected_files.config_files.contains(&"book.toml".to_string()) 
            || detected_files.config_files.contains(&"mkdocs.yml".to_string())
            || detected_files.source_extensions.get(".md").unwrap_or(&0) > &5 {
            types.push(ProjectType::Documentation);
        }

        // If multiple programming languages, classify as polyglot
        let programming_types: Vec<_> = types.iter()
            .filter(|t| !matches!(t, ProjectType::Documentation))
            .collect();

        if programming_types.len() > 1 {
            let lang_names: Vec<String> = programming_types.iter()
                .map(|t| format!("{:?}", t))
                .collect();
            types = vec![ProjectType::Polyglot(lang_names)];
            
            // Keep documentation type if present
            if types.iter().any(|t| matches!(t, ProjectType::Documentation)) {
                types.push(ProjectType::Documentation);
            }
        }

        // Default to detecting based on file extensions if no config files found
        if types.is_empty() {
            if let Some(primary_ext) = self.get_primary_source_extension(&detected_files.source_extensions) {
                match primary_ext.as_str() {
                    ".rs" => types.push(ProjectType::Rust),
                    ".py" => types.push(ProjectType::Python),
                    ".ts" | ".tsx" => types.push(ProjectType::TypeScript),
                    ".js" | ".jsx" => types.push(ProjectType::JavaScript),
                    ".go" => types.push(ProjectType::Go),
                    ".java" => types.push(ProjectType::Java),
                    _ => {}
                }
            }
        }

        types
    }

    /// Get the primary source extension (most common)
    fn get_primary_source_extension(&self, extensions: &HashMap<String, u32>) -> Option<String> {
        extensions.iter()
            .filter(|(ext, _)| matches!(ext.as_str(), ".rs" | ".py" | ".ts" | ".tsx" | ".js" | ".jsx" | ".go" | ".java"))
            .max_by_key(|(_, count)| *count)
            .map(|(ext, _)| ext.clone())
    }

    /// Generate a human-readable project summary
    fn generate_summary(&self, types: &[ProjectType], metadata: &ExtractedMetadata) -> String {
        let type_desc = if types.is_empty() {
            "Unknown project type".to_string()
        } else if types.len() == 1 {
            format!("{:?} project", types[0])
        } else {
            let type_names: Vec<String> = types.iter().map(|t| format!("{:?}", t)).collect();
            format!("{} project", type_names.join(" and "))
        };

        let mut parts = vec![type_desc];

        // Add description from metadata if available
        if let Some(cargo) = &metadata.cargo {
            if let Some(desc) = &cargo.description {
                parts.push(format!("({})", desc));
            }
        } else if let Some(python) = &metadata.python {
            if let Some(desc) = &python.description {
                parts.push(format!("({})", desc));
            }
        }

        // Add git info if available
        if let Some(git) = &metadata.git {
            if let Some(remote) = &git.remote {
                parts.push(format!("from {}", remote));
            }
        }

        parts.join(" ")
    }
}

// Add toml dependency for parsing
// This would need to be added to Cargo.toml dependencies

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::Path;

    #[test]
    fn test_hippo_project_detection() {
        let detector = ProjectDetector::with_default_config();
        let hippo_root = Path::new(env!("CARGO_MANIFEST_DIR")).parent().unwrap();
        
        let report = detector.analyze_directory(hippo_root).unwrap();
        
        // Should detect Rust and Python
        assert!(!report.project_types.is_empty());
        println!("Detected project types: {:?}", report.project_types);
        
        // Should find key config files
        assert!(report.detected_files.config_files.contains(&"Cargo.toml".to_string()));
        assert!(report.detected_files.config_files.contains(&"pyproject.toml".to_string()));
        
        // Should extract Cargo metadata
        assert!(report.extracted_metadata.cargo.is_some());
        let cargo = report.extracted_metadata.cargo.as_ref().unwrap();
        assert!(cargo.workspace_members.contains(&"rs".to_string()));
        
        // Should extract Python metadata
        assert!(report.extracted_metadata.python.is_some());
        let python = report.extracted_metadata.python.as_ref().unwrap();
        assert_eq!(python.name, "hippo-mcp-server");
        
        println!("Project summary: {}", report.summary);
        println!("Detected files: {:#?}", report.detected_files);
    }

    #[test]
    fn test_config_file_detection() {
        let detector = ProjectDetector::with_default_config();
        
        assert!(detector.is_config_file("Cargo.toml"));
        assert!(detector.is_config_file("pyproject.toml"));
        assert!(detector.is_config_file("package.json"));
        assert!(!detector.is_config_file("main.rs"));
        assert!(!detector.is_config_file("README.md"));
    }

    #[test]
    fn test_source_extension_detection() {
        let detector = ProjectDetector::with_default_config();
        
        assert!(detector.is_source_extension(".rs"));
        assert!(detector.is_source_extension(".py"));
        assert!(detector.is_source_extension(".ts"));
        assert!(detector.is_source_extension(".md"));
        assert!(!detector.is_source_extension(".txt"));
        assert!(!detector.is_source_extension(".log"));
    }
}
