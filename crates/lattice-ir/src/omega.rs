use crate::AssuranceVector;
use serde_json::Value;

fn confirmed(v: &Value, key: &str) -> bool {
    v.get(key).and_then(Value::as_str) == Some("CONFIRMED")
}

pub fn import_aether_lineage_report(report: &Value) -> Result<AssuranceVector, String> {
    if report.get("schema").and_then(Value::as_str) != Some("chimera-aether-lineage-binding/v1") {
        return Err("unsupported OMEGA report schema".into());
    }
    let mut out = AssuranceVector::default();
    if confirmed(report, "signature_integrity") {
        out.integrity = "SIGNED".into();
    }
    if report
        .get("supported_revision")
        .and_then(Value::as_str)
        .is_some()
    {
        out.provenance = "SOURCE_PINNED".into();
    }
    if confirmed(report, "raw_operation_binding")
        && confirmed(report, "current_policy_binding")
        && confirmed(report, "lineage_reference_binding")
    {
        out.implementation_binding = "SOURCE_PINNED".into();
    }
    if let Some("CONFIRMED" | "REPRODUCED") =
        report.get("runtime_reproduction").and_then(Value::as_str)
    {
        out.reproduction = "REPLAY_VERIFIED".into();
    }
    if let Some("CONFIRMED") = report
        .get("independent_observation")
        .and_then(Value::as_str)
    {
        out.independence = "DISTINCT_PROCESS".into();
    }
    // Deliberately do not promote observation/truth from report.status=CONFIRMED.
    // OMEGA's status is scoped binding success, not external truth.
    out.validate()?;
    Ok(out)
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;
    #[test]
    fn omega_import_preserves_unknown_independence_and_reproduction() {
        let r = json!({"schema":"chimera-aether-lineage-binding/v1","status":"CONFIRMED","signature_integrity":"CONFIRMED","raw_operation_binding":"CONFIRMED","current_policy_binding":"CONFIRMED","lineage_reference_binding":"CONFIRMED","runtime_reproduction":"NOT_RUN","independent_observation":"UNKNOWN","supported_revision":"abc"});
        let v = import_aether_lineage_report(&r).unwrap();
        assert_eq!(v.integrity, "SIGNED");
        assert_eq!(v.reproduction, "UNKNOWN");
        assert_eq!(v.independence, "UNKNOWN");
        assert_eq!(v.observation, "UNKNOWN");
    }
}
