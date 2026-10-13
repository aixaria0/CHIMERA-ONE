use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::{
    fs,
    path::{Component, Path},
};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SourcePin {
    pub path: String,
    pub sha256: String,
}
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SemanticRule {
    pub id: String,
    pub runtime_pattern: String,
    pub claimed_origin: String,
    #[serde(default)]
    pub proof_obligations: Vec<String>,
}
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NexusManifest {
    pub schema: String,
    pub repository: String,
    pub revision: String,
    pub formal_source: SourcePin,
    pub runtime_source: SourcePin,
    pub rules: Vec<SemanticRule>,
}
#[derive(Debug, Clone, Serialize, PartialEq, Eq)]
pub struct AuditIssue {
    pub rule_id: String,
    pub code: &'static str,
    pub detail: String,
}
#[derive(Debug, Clone, Serialize)]
pub struct NexusAuditReport {
    pub schema: &'static str,
    pub repository: String,
    pub revision: String,
    pub source_pins_confirmed: bool,
    pub status: &'static str,
    pub checked_rules: usize,
    pub issues: Vec<AuditIssue>,
}

const MAX_SOURCE_BYTES: u64 = 1_048_576;

fn sha256(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}

fn read_bounded_source(checkout: &Path, relative: &str) -> Result<Vec<u8>, String> {
    let rel = Path::new(relative);
    if rel.as_os_str().is_empty() || rel.is_absolute() {
        return Err("source path must be a non-empty relative path".into());
    }
    if rel.components().any(|c| !matches!(c, Component::Normal(_))) {
        return Err(format!(
            "source path escapes or aliases checkout: {relative}"
        ));
    }
    let path = checkout.join(rel);
    let meta = fs::symlink_metadata(&path).map_err(|e| format!("{}: {e}", path.display()))?;
    if meta.file_type().is_symlink() || !meta.is_file() {
        return Err(format!(
            "source must be a regular non-symlink file: {}",
            path.display()
        ));
    }
    if meta.len() > MAX_SOURCE_BYTES {
        return Err(format!(
            "source exceeds {MAX_SOURCE_BYTES} byte limit: {}",
            path.display()
        ));
    }
    fs::read(&path).map_err(|e| format!("{}: {e}", path.display()))
}

pub fn audit_checkout(
    manifest: &NexusManifest,
    checkout: &Path,
) -> Result<NexusAuditReport, String> {
    if manifest.schema != "chimera-nexus-semantic-audit/v1" {
        return Err("unsupported Nexus audit manifest schema".into());
    }
    if manifest.repository.trim().is_empty() || manifest.revision.trim().is_empty() {
        return Err("repository and revision must not be empty".into());
    }
    let formal_bytes = read_bounded_source(checkout, &manifest.formal_source.path)?;
    let runtime_bytes = read_bounded_source(checkout, &manifest.runtime_source.path)?;
    let formal_pin = sha256(&formal_bytes) == manifest.formal_source.sha256;
    let runtime_pin = sha256(&runtime_bytes) == manifest.runtime_source.sha256;
    if !formal_pin || !runtime_pin {
        return Ok(NexusAuditReport {
            schema: "chimera-nexus-semantic-audit-report/v1",
            repository: manifest.repository.clone(),
            revision: manifest.revision.clone(),
            source_pins_confirmed: false,
            status: "REJECTED",
            checked_rules: 0,
            issues: vec![AuditIssue {
                rule_id: "source-pins".into(),
                code: "SOURCE_PIN_MISMATCH",
                detail: format!("formal_pin={formal_pin} runtime_pin={runtime_pin}"),
            }],
        });
    }
    let formal = String::from_utf8(formal_bytes).map_err(|_| "formal source is not UTF-8")?;
    let runtime = String::from_utf8(runtime_bytes).map_err(|_| "runtime source is not UTF-8")?;
    let mut issues = Vec::new();
    for rule in &manifest.rules {
        if !runtime.contains(&rule.runtime_pattern) {
            issues.push(AuditIssue {
                rule_id: rule.id.clone(),
                code: "RUNTIME_PATTERN_MISSING",
                detail: format!("runtime pattern {:?} was not found", rule.runtime_pattern),
            });
            continue;
        }
        if rule.claimed_origin == "FORMAL_THEOREM" {
            if rule.proof_obligations.is_empty() {
                issues.push(AuditIssue {
                    rule_id: rule.id.clone(),
                    code: "UNBOUND_FORMAL_CLAIM",
                    detail: "formal origin has no explicit proof obligation".into(),
                });
                continue;
            }
            let missing: Vec<_> = rule
                .proof_obligations
                .iter()
                .filter(|p| !formal.contains(p.as_str()))
                .cloned()
                .collect();
            if !missing.is_empty() {
                issues.push(AuditIssue{rule_id:rule.id.clone(),code:"SEMANTIC_OVERPROMOTION",detail:format!("runtime classifies this rule as FORMAL_THEOREM, but pinned Lean source does not satisfy obligations: {}",missing.join(", "))});
            }
        }
    }
    let status = if issues.is_empty() { "PASS" } else { "FAIL" };
    Ok(NexusAuditReport {
        schema: "chimera-nexus-semantic-audit-report/v1",
        repository: manifest.repository.clone(),
        revision: manifest.revision.clone(),
        source_pins_confirmed: true,
        status,
        checked_rules: manifest.rules.len(),
        issues,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::{env, fs};
    #[test]
    fn detects_formal_overpromotion_and_accepts_reclassification() {
        let root = env::temp_dir().join(format!("lattice-nexus-{}", std::process::id()));
        let _ = fs::remove_dir_all(&root);
        fs::create_dir_all(root.join("backend/qlf_math")).unwrap();
        fs::create_dir_all(root.join("backend/backend")).unwrap();
        let formal = b"theorem zfa_implies_null_spectral : c != 0 := by trivial\n";
        let runtime = b"SPECTRAL_MODE_MAX = 1.0\n";
        fs::write(root.join("backend/qlf_math/QLF_NullCone.lean"), formal).unwrap();
        fs::write(root.join("backend/backend/qlf_verification.py"), runtime).unwrap();
        let mut m = NexusManifest {
            schema: "chimera-nexus-semantic-audit/v1".into(),
            repository: "fixture".into(),
            revision: "fixture".into(),
            formal_source: SourcePin {
                path: "backend/qlf_math/QLF_NullCone.lean".into(),
                sha256: sha256(formal),
            },
            runtime_source: SourcePin {
                path: "backend/backend/qlf_verification.py".into(),
                sha256: sha256(runtime),
            },
            rules: vec![SemanticRule {
                id: "spectral-max".into(),
                runtime_pattern: "SPECTRAL_MODE_MAX = 1.0".into(),
                claimed_origin: "FORMAL_THEOREM".into(),
                proof_obligations: vec!["NullCone_implies_Consistency".into(), "c ≤ 1".into()],
            }],
        };
        let bad = audit_checkout(&m, &root).unwrap();
        assert_eq!(bad.status, "FAIL");
        assert_eq!(bad.issues[0].code, "SEMANTIC_OVERPROMOTION");
        m.rules[0].claimed_origin = "ENGINEERING_POLICY".into();
        m.rules[0].proof_obligations.clear();
        let good = audit_checkout(&m, &root).unwrap();
        assert_eq!(good.status, "PASS");
        let _ = fs::remove_dir_all(root);
    }

    #[test]
    fn audit_rejects_checkout_escape_paths() {
        let root = env::temp_dir().join(format!("lattice-nexus-escape-{}", std::process::id()));
        let _ = fs::remove_dir_all(&root);
        fs::create_dir_all(&root).unwrap();
        let m = NexusManifest {
            schema: "chimera-nexus-semantic-audit/v1".into(),
            repository: "fixture".into(),
            revision: "fixture".into(),
            formal_source: SourcePin {
                path: "../outside.lean".into(),
                sha256: "00".into(),
            },
            runtime_source: SourcePin {
                path: "runtime.py".into(),
                sha256: "00".into(),
            },
            rules: vec![],
        };
        assert!(audit_checkout(&m, &root)
            .unwrap_err()
            .contains("escapes or aliases checkout"));
        let _ = fs::remove_dir_all(root);
    }
}
