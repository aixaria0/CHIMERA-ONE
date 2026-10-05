use serde::Serialize;
use serde_json::Value;
use sha2::{Digest, Sha256};
use std::collections::{BTreeSet, HashMap, HashSet};

pub const DOMAIN: &[u8] = b"chimera-protocol/v1\0";

#[derive(Debug, Clone, Serialize, PartialEq, Eq)]
pub struct ValidationReport {
    pub schema: &'static str,
    pub valid: bool,
    pub digest: Option<String>,
    pub errors: Vec<String>,
}

fn canonical_write(value: &Value, out: &mut String) -> Result<(), String> {
    match value {
        Value::Null => out.push_str("null"),
        Value::Bool(v) => out.push_str(if *v { "true" } else { "false" }),
        Value::Number(v) => {
            if v.is_f64() {
                return Err("floating-point numbers are not canonical protocol values".into());
            }
            out.push_str(&v.to_string());
        }
        Value::String(v) => out.push_str(&serde_json::to_string(v).map_err(|e| e.to_string())?),
        Value::Array(values) => {
            out.push('[');
            for (index, item) in values.iter().enumerate() {
                if index > 0 {
                    out.push(',');
                }
                canonical_write(item, out)?;
            }
            out.push(']');
        }
        Value::Object(values) => {
            out.push('{');
            let mut keys: Vec<&String> = values.keys().collect();
            keys.sort();
            for (index, key) in keys.iter().enumerate() {
                if index > 0 {
                    out.push(',');
                }
                out.push_str(&serde_json::to_string(key).map_err(|e| e.to_string())?);
                out.push(':');
                canonical_write(&values[*key], out)?;
            }
            out.push('}');
        }
    }
    Ok(())
}

pub fn canonical_json(value: &Value) -> Result<Vec<u8>, String> {
    let mut out = String::new();
    canonical_write(value, &mut out)?;
    Ok(out.into_bytes())
}

pub fn protocol_digest(value: &Value) -> Result<String, String> {
    let bytes = canonical_json(value)?;
    let mut hasher = Sha256::new();
    hasher.update(DOMAIN);
    hasher.update(bytes);
    Ok(format!("sha256:{:x}", hasher.finalize()))
}

fn text<'a>(
    object: &'a serde_json::Map<String, Value>,
    key: &str,
    errors: &mut Vec<String>,
) -> Option<&'a str> {
    match object.get(key).and_then(Value::as_str) {
        Some(value) if !value.trim().is_empty() => Some(value),
        _ => {
            errors.push(format!("{key} must be a non-empty string"));
            None
        }
    }
}

fn detect_cycle(graph: &HashMap<String, Vec<String>>) -> bool {
    fn visit(
        node: &str,
        graph: &HashMap<String, Vec<String>>,
        visiting: &mut HashSet<String>,
        visited: &mut HashSet<String>,
    ) -> bool {
        if visited.contains(node) {
            return false;
        }
        if !visiting.insert(node.to_string()) {
            return true;
        }
        if let Some(deps) = graph.get(node) {
            for dep in deps {
                if visit(dep, graph, visiting, visited) {
                    return true;
                }
            }
        }
        visiting.remove(node);
        visited.insert(node.to_string());
        false
    }

    let mut visiting = HashSet::new();
    let mut visited = HashSet::new();
    graph
        .keys()
        .any(|node| visit(node, graph, &mut visiting, &mut visited))
}

pub fn validate_run(value: &Value) -> ValidationReport {
    let mut errors = Vec::new();
    let digest = match protocol_digest(value) {
        Ok(value) => Some(value),
        Err(err) => {
            errors.push(err);
            None
        }
    };

    let Some(root) = value.as_object() else {
        errors.push("run must be a JSON object".into());
        return ValidationReport {
            schema: "chimera-validation-report/v1",
            valid: false,
            digest,
            errors,
        };
    };

    if root.get("schema").and_then(Value::as_str) != Some("chimera-run/v1") {
        errors.push("schema must equal chimera-run/v1".into());
    }
    text(root, "run_id", &mut errors);
    text(root, "objective", &mut errors);
    match root.get("domain").and_then(Value::as_str) {
        Some("general" | "rchain-audit") => {}
        _ => errors.push("domain must be general or rchain-audit".into()),
    }

    match root.get("policy").and_then(Value::as_object) {
        Some(policy) => {
            for key in [
                "automatic_mutation",
                "automatic_deployment",
                "unrestricted_execution",
            ] {
                if policy.get(key).and_then(Value::as_bool) != Some(false) {
                    errors.push(format!("policy.{key} must be false"));
                }
            }
            if policy
                .get("claim_promotion_requires_evidence")
                .and_then(Value::as_bool)
                != Some(true)
            {
                errors.push("policy.claim_promotion_requires_evidence must be true".into());
            }
        }
        None => errors.push("policy must be an object".into()),
    }

    let mut ids = BTreeSet::new();
    let mut graph: HashMap<String, Vec<String>> = HashMap::new();
    match root.get("steps").and_then(Value::as_array) {
        Some(steps) if !steps.is_empty() => {
            for (index, step) in steps.iter().enumerate() {
                let Some(step) = step.as_object() else {
                    errors.push(format!("steps[{index}] must be an object"));
                    continue;
                };
                let Some(id) = text(step, "id", &mut errors) else {
                    continue;
                };
                if !ids.insert(id.to_string()) {
                    errors.push(format!("duplicate step id: {id}"));
                }
                text(step, "capability", &mut errors);
                text(step, "provider", &mut errors);
                match step.get("state").and_then(Value::as_str) {
                    Some("PLANNED" | "RUNNING" | "COMPLETE" | "BLOCKED" | "FAILED") => {}
                    _ => errors.push(format!("invalid state for step {id}")),
                }
                let deps = match step.get("depends_on").and_then(Value::as_array) {
                    Some(values) => values
                        .iter()
                        .filter_map(|value| value.as_str().map(str::to_owned))
                        .collect::<Vec<_>>(),
                    None => {
                        errors.push(format!("depends_on must be an array for step {id}"));
                        Vec::new()
                    }
                };
                graph.insert(id.to_string(), deps);
            }
            for (id, deps) in &graph {
                for dep in deps {
                    if !ids.contains(dep) {
                        errors.push(format!("step {id} depends on unknown step {dep}"));
                    }
                    if dep == id {
                        errors.push(format!("step {id} depends on itself"));
                    }
                }
            }
            if detect_cycle(&graph) {
                errors.push("step dependency graph contains a cycle".into());
            }
        }
        _ => errors.push("steps must be a non-empty array".into()),
    }

    let allowed_statuses = [
        "HYPOTHESIS",
        "PLAUSIBLE",
        "OBSERVED",
        "REPRODUCED",
        "CORROBORATED",
        "VERIFIED_WITHIN_SCOPE",
        "CONTRADICTED",
        "INCONCLUSIVE",
        "UNKNOWN",
    ];
    match root.get("claims").and_then(Value::as_array) {
        Some(claims) => {
            for (index, claim) in claims.iter().enumerate() {
                let Some(claim) = claim.as_object() else {
                    errors.push(format!("claims[{index}] must be an object"));
                    continue;
                };
                text(claim, "id", &mut errors);
                text(claim, "statement", &mut errors);
                match claim.get("status").and_then(Value::as_str) {
                    Some(status) if allowed_statuses.contains(&status) => {}
                    _ => errors.push(format!("claims[{index}] has invalid status")),
                }
                if !claim.get("evidence").is_some_and(Value::is_array) {
                    errors.push(format!("claims[{index}].evidence must be an array"));
                }
            }
        }
        None => errors.push("claims must be an array".into()),
    }

    ValidationReport {
        schema: "chimera-validation-report/v1",
        valid: errors.is_empty(),
        digest,
        errors,
    }
}

pub fn epistemic_rank(status: &str) -> Option<u8> {
    match status {
        "UNKNOWN" => Some(0),
        "HYPOTHESIS" => Some(1),
        "PLAUSIBLE" => Some(2),
        "OBSERVED" => Some(3),
        "REPRODUCED" => Some(4),
        "CORROBORATED" => Some(5),
        "VERIFIED_WITHIN_SCOPE" => Some(6),
        "INCONCLUSIVE" | "CONTRADICTED" => Some(0),
        _ => None,
    }
}

pub fn promotion_allowed(
    current: &str,
    requested: &str,
    evidence_count: usize,
    reproduced: bool,
    independently_checked: bool,
    pinned_verification: bool,
) -> bool {
    let (Some(current_rank), Some(requested_rank)) =
        (epistemic_rank(current), epistemic_rank(requested))
    else {
        return false;
    };
    if requested_rank <= current_rank {
        return true;
    }
    if evidence_count == 0 {
        return false;
    }
    match requested {
        "OBSERVED" | "PLAUSIBLE" => true,
        "REPRODUCED" => reproduced,
        "CORROBORATED" => reproduced && independently_checked,
        "VERIFIED_WITHIN_SCOPE" => reproduced && independently_checked && pinned_verification,
        _ => false,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn canonicalization_sorts_keys() {
        let a = json!({"z": 2, "a": [3, {"y": true, "x": "v"}]});
        let b = json!({"a": [3, {"x": "v", "y": true}], "z": 2});
        assert_eq!(protocol_digest(&a).unwrap(), protocol_digest(&b).unwrap());
    }

    #[test]
    fn promotion_is_evidence_gated() {
        assert!(!promotion_allowed(
            "HYPOTHESIS",
            "REPRODUCED",
            1,
            false,
            false,
            false
        ));
        assert!(promotion_allowed(
            "HYPOTHESIS",
            "REPRODUCED",
            1,
            true,
            false,
            false
        ));
        assert!(!promotion_allowed(
            "REPRODUCED",
            "VERIFIED_WITHIN_SCOPE",
            2,
            true,
            true,
            false
        ));
        assert!(promotion_allowed(
            "REPRODUCED",
            "VERIFIED_WITHIN_SCOPE",
            2,
            true,
            true,
            true
        ));
    }
}
