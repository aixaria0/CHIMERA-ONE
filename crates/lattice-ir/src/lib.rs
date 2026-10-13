use serde::{Deserialize, Serialize};
use serde_json::Value;
use sha2::{Digest, Sha256};
use std::cmp::Ordering;

pub mod nexus;
pub mod omega;

pub const ASSURANCE_SCHEMA: &str = "chimera-assurance-vector/v1";
pub const CLAIM_SCHEMA: &str = "chimera-epistemic-claim/v1";
pub const EDGE_SCHEMA: &str = "chimera-evidence-edge/v1";
pub const WITNESS_SCHEMA: &str = "chimera-evidence-witness/v1";

fn unknown() -> String {
    "UNKNOWN".into()
}
fn assurance_schema() -> String {
    ASSURANCE_SCHEMA.into()
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq, Hash)]
#[serde(rename_all = "snake_case")]
pub enum Dimension {
    Observation,
    Integrity,
    Reproduction,
    Provenance,
    Authorization,
    Independence,
    Freshness,
    AdversarialCoverage,
    FormalProof,
    ImplementationBinding,
}

pub const DIMENSIONS: [Dimension; 10] = [
    Dimension::Observation,
    Dimension::Integrity,
    Dimension::Reproduction,
    Dimension::Provenance,
    Dimension::Authorization,
    Dimension::Independence,
    Dimension::Freshness,
    Dimension::AdversarialCoverage,
    Dimension::FormalProof,
    Dimension::ImplementationBinding,
];

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct AssuranceVector {
    #[serde(default = "assurance_schema")]
    pub schema: String,
    #[serde(default = "unknown")]
    pub observation: String,
    #[serde(default = "unknown")]
    pub integrity: String,
    #[serde(default = "unknown")]
    pub reproduction: String,
    #[serde(default = "unknown")]
    pub provenance: String,
    #[serde(default = "unknown")]
    pub authorization: String,
    #[serde(default = "unknown")]
    pub independence: String,
    #[serde(default = "unknown")]
    pub freshness: String,
    #[serde(default = "unknown")]
    pub adversarial_coverage: String,
    #[serde(default = "unknown")]
    pub formal_proof: String,
    #[serde(default = "unknown")]
    pub implementation_binding: String,
}

impl Default for AssuranceVector {
    fn default() -> Self {
        Self {
            schema: ASSURANCE_SCHEMA.into(),
            observation: unknown(),
            integrity: unknown(),
            reproduction: unknown(),
            provenance: unknown(),
            authorization: unknown(),
            independence: unknown(),
            freshness: unknown(),
            adversarial_coverage: unknown(),
            formal_proof: unknown(),
            implementation_binding: unknown(),
        }
    }
}

impl AssuranceVector {
    pub fn get(&self, d: Dimension) -> &str {
        match d {
            Dimension::Observation => &self.observation,
            Dimension::Integrity => &self.integrity,
            Dimension::Reproduction => &self.reproduction,
            Dimension::Provenance => &self.provenance,
            Dimension::Authorization => &self.authorization,
            Dimension::Independence => &self.independence,
            Dimension::Freshness => &self.freshness,
            Dimension::AdversarialCoverage => &self.adversarial_coverage,
            Dimension::FormalProof => &self.formal_proof,
            Dimension::ImplementationBinding => &self.implementation_binding,
        }
    }

    fn set(&mut self, d: Dimension, value: String) {
        match d {
            Dimension::Observation => self.observation = value,
            Dimension::Integrity => self.integrity = value,
            Dimension::Reproduction => self.reproduction = value,
            Dimension::Provenance => self.provenance = value,
            Dimension::Authorization => self.authorization = value,
            Dimension::Independence => self.independence = value,
            Dimension::Freshness => self.freshness = value,
            Dimension::AdversarialCoverage => self.adversarial_coverage = value,
            Dimension::FormalProof => self.formal_proof = value,
            Dimension::ImplementationBinding => self.implementation_binding = value,
        }
    }

    pub fn validate(&self) -> Result<(), String> {
        if self.schema != ASSURANCE_SCHEMA {
            return Err(format!("schema must equal {ASSURANCE_SCHEMA}"));
        }
        for d in DIMENSIONS {
            rank_for(d, self.get(d))?;
        }
        Ok(())
    }

    pub fn relation(&self, other: &Self) -> Result<Relation, String> {
        self.validate()?;
        other.validate()?;
        let mut greater = false;
        let mut less = false;
        for d in DIMENSIONS {
            match rank_for(d, self.get(d))?.cmp(&rank_for(d, other.get(d))?) {
                Ordering::Greater => greater = true,
                Ordering::Less => less = true,
                Ordering::Equal => {}
            }
        }
        Ok(match (greater, less) {
            (false, false) => Relation::Equal,
            (true, false) => Relation::Dominates,
            (false, true) => Relation::DominatedBy,
            (true, true) => Relation::Incomparable,
        })
    }
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum Relation {
    Dominates,
    DominatedBy,
    Equal,
    Incomparable,
}

pub fn rank_for(d: Dimension, state: &str) -> Result<u8, String> {
    let rank = match d {
        Dimension::Observation => match state {
            "UNKNOWN" => 0,
            "CLAIMED" => 1,
            "LOCAL" => 2,
            "EXTERNAL" => 3,
            _ => return invalid(d, state),
        },
        Dimension::Integrity => match state {
            "UNKNOWN" => 0,
            "DIGEST_BOUND" => 1,
            "SIGNED" => 2,
            _ => return invalid(d, state),
        },
        Dimension::Reproduction => match state {
            "UNKNOWN" => 0,
            "REPLAY_VERIFIED" => 1,
            "REEXECUTED" => 2,
            _ => return invalid(d, state),
        },
        Dimension::Provenance => match state {
            "UNKNOWN" => 0,
            "SOURCE_DECLARED" => 1,
            "SOURCE_PINNED" => 2,
            "CONTENT_PINNED" => 3,
            _ => return invalid(d, state),
        },
        Dimension::Authorization => match state {
            "UNKNOWN" => 0,
            "POLICY_BOUND" => 1,
            "CONFIRMED" => 2,
            _ => return invalid(d, state),
        },
        Dimension::Independence => match state {
            "UNKNOWN" => 0,
            "DISTINCT_PROCESS" => 1,
            "DISTINCT_HOST" => 2,
            "DISTINCT_ORGANIZATION" => 3,
            _ => return invalid(d, state),
        },
        Dimension::Freshness => match state {
            "UNKNOWN" => 0,
            "TIMESTAMPED" => 1,
            "CHALLENGE_BOUND" => 2,
            _ => return invalid(d, state),
        },
        Dimension::AdversarialCoverage => match state {
            "UNKNOWN" => 0,
            "NEGATIVE_CONTROL" => 1,
            "MUTATION_TESTED" => 2,
            "FAULT_INJECTED" => 3,
            _ => return invalid(d, state),
        },
        Dimension::FormalProof => match state {
            "UNKNOWN" => 0,
            "DECLARED" => 1,
            "MODEL_CHECKED" => 2,
            _ => return invalid(d, state),
        },
        Dimension::ImplementationBinding => match state {
            "UNKNOWN" => 0,
            "DECLARED" => 1,
            "SOURCE_PINNED" => 2,
            "SEMANTICS_BOUND" => 3,
            _ => return invalid(d, state),
        },
    };
    Ok(rank)
}

fn invalid<T>(d: Dimension, state: &str) -> Result<T, String> {
    Err(format!("invalid state {state:?} for dimension {d:?}"))
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum WitnessKind {
    ArtifactObservation,
    DigestBinding,
    SignatureVerification,
    DeterministicReplay,
    Reexecution,
    SourcePin,
    PolicyAuthorization,
    IndependentObservation,
    FreshnessChallenge,
    NegativeControl,
    FaultInjection,
    FormalSourceDeclaration,
    ModelCheckedProof,
    ImplementationBinding,
}

impl WitnessKind {
    fn authorizes(self, d: Dimension) -> bool {
        matches!(
            (self, d),
            (Self::ArtifactObservation, Dimension::Observation)
                | (Self::DigestBinding, Dimension::Integrity)
                | (Self::SignatureVerification, Dimension::Integrity)
                | (Self::DeterministicReplay, Dimension::Reproduction)
                | (Self::Reexecution, Dimension::Reproduction)
                | (Self::SourcePin, Dimension::Provenance)
                | (Self::PolicyAuthorization, Dimension::Authorization)
                | (Self::IndependentObservation, Dimension::Independence)
                | (Self::FreshnessChallenge, Dimension::Freshness)
                | (Self::NegativeControl, Dimension::AdversarialCoverage)
                | (Self::FaultInjection, Dimension::AdversarialCoverage)
                | (Self::FormalSourceDeclaration, Dimension::FormalProof)
                | (Self::ModelCheckedProof, Dimension::FormalProof)
                | (
                    Self::ImplementationBinding,
                    Dimension::ImplementationBinding
                )
        )
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct EvidenceWitness {
    pub schema: String,
    pub kind: WitnessKind,
    pub source: String,
    pub authorized_dimensions: Vec<Dimension>,
    pub payload: Value,
    #[serde(default)]
    pub digest: String,
}

impl EvidenceWitness {
    pub fn seal(mut self) -> Result<Self, String> {
        self.schema = WITNESS_SCHEMA.into();
        self.digest.clear();
        self.digest = witness_digest(&self)?;
        Ok(self)
    }

    pub fn verify(&self) -> Result<(), String> {
        if self.schema != WITNESS_SCHEMA {
            return Err(format!("witness schema must equal {WITNESS_SCHEMA}"));
        }
        if self.source.trim().is_empty() {
            return Err("witness source must not be empty".into());
        }
        if self.authorized_dimensions.is_empty() {
            return Err("witness must authorize at least one dimension".into());
        }
        for d in &self.authorized_dimensions {
            if !self.kind.authorizes(*d) {
                return Err(format!(
                    "witness kind {:?} cannot authorize {d:?}",
                    self.kind
                ));
            }
        }
        let expected = witness_digest(self)?;
        if self.digest != expected {
            return Err("witness digest mismatch".into());
        }
        Ok(())
    }
}

pub fn witness_digest(w: &EvidenceWitness) -> Result<String, String> {
    let mut value = serde_json::to_value(w).map_err(|e| e.to_string())?;
    let obj = value
        .as_object_mut()
        .ok_or("witness must serialize as object")?;
    obj.insert("digest".into(), Value::String(String::new()));
    domain_digest("chimera-evidence-witness/v1", &value)
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct EvidenceEdge {
    pub schema: String,
    pub dimension: Dimension,
    pub from: String,
    pub to: String,
    pub witness: EvidenceWitness,
}

pub fn apply_edge(
    current: &AssuranceVector,
    edge: &EvidenceEdge,
) -> Result<AssuranceVector, String> {
    current.validate()?;
    if edge.schema != EDGE_SCHEMA {
        return Err(format!("edge schema must equal {EDGE_SCHEMA}"));
    }
    edge.witness.verify()?;
    if !edge.witness.authorized_dimensions.contains(&edge.dimension) {
        return Err("witness does not authorize the promoted dimension".into());
    }
    if current.get(edge.dimension) != edge.from {
        return Err(format!(
            "edge from {:?} does not match current state {:?}",
            edge.from,
            current.get(edge.dimension)
        ));
    }
    let before = rank_for(edge.dimension, &edge.from)?;
    let after = rank_for(edge.dimension, &edge.to)?;
    if after <= before {
        return Err("evidence edge must strictly promote exactly one dimension".into());
    }
    target_guard(edge.dimension, &edge.to, edge.witness.kind)?;
    let mut next = current.clone();
    next.set(edge.dimension, edge.to.clone());
    Ok(next)
}

fn target_guard(d: Dimension, to: &str, kind: WitnessKind) -> Result<(), String> {
    let ok = match (d, to) {
        (Dimension::Integrity, "SIGNED") => kind == WitnessKind::SignatureVerification,
        (Dimension::Reproduction, "REPLAY_VERIFIED") => kind == WitnessKind::DeterministicReplay,
        (Dimension::Reproduction, "REEXECUTED") => kind == WitnessKind::Reexecution,
        (Dimension::FormalProof, "MODEL_CHECKED") => kind == WitnessKind::ModelCheckedProof,
        (Dimension::ImplementationBinding, "SOURCE_PINNED" | "SEMANTICS_BOUND") => {
            kind == WitnessKind::ImplementationBinding
        }
        (
            Dimension::Independence,
            "DISTINCT_PROCESS" | "DISTINCT_HOST" | "DISTINCT_ORGANIZATION",
        ) => kind == WitnessKind::IndependentObservation,
        _ => true,
    };
    if ok {
        Ok(())
    } else {
        Err(format!(
            "witness kind {kind:?} is insufficient for {d:?} -> {to}"
        ))
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct ClaimRecord {
    pub schema: String,
    pub id: String,
    pub statement: String,
    pub assurance: AssuranceVector,
    #[serde(default)]
    pub evidence: Vec<EvidenceEdge>,
}

#[derive(Debug, Clone, Serialize, PartialEq, Eq)]
pub struct ClaimValidation {
    pub schema: &'static str,
    pub valid: bool,
    pub claim_id: String,
    pub evidence_edges: usize,
    pub errors: Vec<String>,
}

pub fn validate_claim(claim: &ClaimRecord) -> ClaimValidation {
    let mut errors = Vec::new();
    if claim.schema != CLAIM_SCHEMA {
        errors.push(format!("claim schema must equal {CLAIM_SCHEMA}"));
    }
    if claim.id.trim().is_empty() {
        errors.push("claim id must not be empty".into());
    }
    if claim.statement.trim().is_empty() {
        errors.push("claim statement must not be empty".into());
    }
    if let Err(e) = claim.assurance.validate() {
        errors.push(e);
    }
    let mut state = AssuranceVector::default();
    for (index, edge) in claim.evidence.iter().enumerate() {
        match apply_edge(&state, edge) {
            Ok(next) => state = next,
            Err(e) => {
                errors.push(format!("evidence[{index}]: {e}"));
                break;
            }
        }
    }
    if state != claim.assurance {
        errors.push(
            "declared assurance vector is not reproduced by the supplied evidence edges".into(),
        );
    }
    ClaimValidation {
        schema: "chimera-claim-validation/v1",
        valid: errors.is_empty(),
        claim_id: claim.id.clone(),
        evidence_edges: claim.evidence.len(),
        errors,
    }
}

#[derive(Debug, Clone, Serialize, PartialEq, Eq)]
pub struct NextAction {
    pub schema: &'static str,
    pub action: &'static str,
    pub target_dimension: Option<Dimension>,
    pub from: Option<String>,
    pub to: Option<&'static str>,
    pub reason: String,
    pub cost_class: &'static str,
}

pub fn next_action(v: &AssuranceVector) -> Result<NextAction, String> {
    v.validate()?;
    if v.formal_proof == "DECLARED" {
        return Ok(action(
            "ACQUIRE_MACHINE_CHECK",
            Dimension::FormalProof,
            &v.formal_proof,
            "MODEL_CHECKED",
            "A formal source is declared, but no accepted machine-check witness has promoted it.",
            "MEDIUM",
        ));
    }
    if v.formal_proof == "MODEL_CHECKED" && v.implementation_binding != "SEMANTICS_BOUND" {
        return Ok(action(
            "BIND_IMPLEMENTATION",
            Dimension::ImplementationBinding,
            &v.implementation_binding,
            "SEMANTICS_BOUND",
            "A machine-checked model exists, but runtime semantics are not yet bound to it.",
            "MEDIUM",
        ));
    }
    if v.integrity == "SIGNED" && v.reproduction == "UNKNOWN" {
        return Ok(action(
            "REPLAY_TARGET",
            Dimension::Reproduction,
            &v.reproduction,
            "REPLAY_VERIFIED",
            "Signature integrity does not establish reproducibility.",
            "LOW",
        ));
    }
    if v.observation == "LOCAL" && v.independence == "UNKNOWN" {
        return Ok(action(
            "ACQUIRE_SECOND_OBSERVER",
            Dimension::Independence,
            &v.independence,
            "DISTINCT_PROCESS",
            "Local observation does not establish observer independence.",
            "MEDIUM",
        ));
    }
    if rank_for(Dimension::Provenance, &v.provenance)?
        < rank_for(Dimension::Provenance, "CONTENT_PINNED")?
    {
        return Ok(action(
            "PIN_PROVENANCE",
            Dimension::Provenance,
            &v.provenance,
            "CONTENT_PINNED",
            "Exact content provenance is still weaker than a byte pin.",
            "LOW",
        ));
    }
    Ok(NextAction {
        schema: "chimera-next-evidence-action/v1",
        action: "NO_ACTION",
        target_dimension: None,
        from: None,
        to: None,
        reason: "No v1 scheduler rule found a justified promotion target.".into(),
        cost_class: "NONE",
    })
}

fn action(
    name: &'static str,
    d: Dimension,
    from: &str,
    to: &'static str,
    reason: &str,
    cost: &'static str,
) -> NextAction {
    NextAction {
        schema: "chimera-next-evidence-action/v1",
        action: name,
        target_dimension: Some(d),
        from: Some(from.into()),
        to: Some(to),
        reason: reason.into(),
        cost_class: cost,
    }
}

pub fn domain_digest(domain: &str, value: &Value) -> Result<String, String> {
    let bytes = canonical_json(value)?;
    let mut h = Sha256::new();
    h.update(domain.as_bytes());
    h.update([0]);
    h.update(bytes);
    Ok(format!("sha256:{:x}", h.finalize()))
}

pub fn canonical_json(value: &Value) -> Result<Vec<u8>, String> {
    fn write(v: &Value, out: &mut String) -> Result<(), String> {
        match v {
            Value::Null => out.push_str("null"),
            Value::Bool(b) => out.push_str(if *b { "true" } else { "false" }),
            Value::Number(n) => {
                if n.is_f64() {
                    return Err("floating-point numbers are not canonical lattice values".into());
                }
                out.push_str(&n.to_string());
            }
            Value::String(s) => out.push_str(&serde_json::to_string(s).map_err(|e| e.to_string())?),
            Value::Array(xs) => {
                out.push('[');
                for (i, x) in xs.iter().enumerate() {
                    if i > 0 {
                        out.push(',');
                    }
                    write(x, out)?;
                }
                out.push(']');
            }
            Value::Object(m) => {
                out.push('{');
                let mut keys: Vec<_> = m.keys().collect();
                keys.sort();
                for (i, k) in keys.iter().enumerate() {
                    if i > 0 {
                        out.push(',');
                    }
                    out.push_str(&serde_json::to_string(k).map_err(|e| e.to_string())?);
                    out.push(':');
                    write(&m[*k], out)?;
                }
                out.push('}');
            }
        }
        Ok(())
    }
    let mut out = String::new();
    write(value, &mut out)?;
    Ok(out.into_bytes())
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn witness(kind: WitnessKind, d: Dimension) -> EvidenceWitness {
        EvidenceWitness {
            schema: WITNESS_SCHEMA.into(),
            kind,
            source: "test-fixture".into(),
            authorized_dimensions: vec![d],
            payload: json!({"fixture":"v1"}),
            digest: String::new(),
        }
        .seal()
        .unwrap()
    }

    #[test]
    fn product_order_has_incomparable_states() {
        let a = AssuranceVector {
            integrity: "SIGNED".into(),
            ..Default::default()
        };
        let b = AssuranceVector {
            reproduction: "REPLAY_VERIFIED".into(),
            ..Default::default()
        };
        assert_eq!(a.relation(&b).unwrap(), Relation::Incomparable);
    }

    #[test]
    fn promotion_requires_authorized_witness() {
        let v = AssuranceVector::default();
        let edge = EvidenceEdge {
            schema: EDGE_SCHEMA.into(),
            dimension: Dimension::Reproduction,
            from: "UNKNOWN".into(),
            to: "REPLAY_VERIFIED".into(),
            witness: witness(WitnessKind::SignatureVerification, Dimension::Integrity),
        };
        assert!(apply_edge(&v, &edge)
            .unwrap_err()
            .contains("does not authorize"));
    }

    #[test]
    fn tampered_witness_is_rejected() {
        let v = AssuranceVector::default();
        let mut w = witness(WitnessKind::DeterministicReplay, Dimension::Reproduction);
        w.payload = json!({"fixture":"tampered-after-seal"});
        let edge = EvidenceEdge {
            schema: EDGE_SCHEMA.into(),
            dimension: Dimension::Reproduction,
            from: "UNKNOWN".into(),
            to: "REPLAY_VERIFIED".into(),
            witness: w,
        };
        assert_eq!(
            apply_edge(&v, &edge).unwrap_err(),
            "witness digest mismatch"
        );
    }

    #[test]
    fn formal_declaration_cannot_self_promote_to_model_checked() {
        let v = AssuranceVector::default();
        let w = witness(WitnessKind::FormalSourceDeclaration, Dimension::FormalProof);
        let declared = EvidenceEdge {
            schema: EDGE_SCHEMA.into(),
            dimension: Dimension::FormalProof,
            from: "UNKNOWN".into(),
            to: "DECLARED".into(),
            witness: w.clone(),
        };
        assert_eq!(apply_edge(&v, &declared).unwrap().formal_proof, "DECLARED");
        let checked = EvidenceEdge {
            to: "MODEL_CHECKED".into(),
            ..declared
        };
        assert!(apply_edge(&v, &checked)
            .unwrap_err()
            .contains("insufficient"));
    }

    #[test]
    fn scheduler_does_not_treat_declared_formal_source_as_model_checked() {
        let v = AssuranceVector {
            formal_proof: "DECLARED".into(),
            ..Default::default()
        };
        let next = next_action(&v).unwrap();
        assert_eq!(next.action, "ACQUIRE_MACHINE_CHECK");
        assert_eq!(next.target_dimension, Some(Dimension::FormalProof));
    }

    #[test]
    fn scheduler_prefers_proof_runtime_binding_gap() {
        let v = AssuranceVector {
            formal_proof: "MODEL_CHECKED".into(),
            implementation_binding: "DECLARED".into(),
            ..Default::default()
        };
        assert_eq!(next_action(&v).unwrap().action, "BIND_IMPLEMENTATION");
    }
}
