use lattice_ir::nexus::{audit_checkout, NexusManifest};
use lattice_ir::omega::import_aether_lineage_report;
use lattice_ir::{
    apply_edge, next_action, validate_claim, AssuranceVector, ClaimRecord, EvidenceEdge,
    EvidenceWitness,
};
use serde::de::DeserializeOwned;
use serde_json::Value;
use std::{
    env, fs,
    io::{self, Write},
    path::Path,
};

fn read<T: DeserializeOwned>(p: &str) -> Result<T, String> {
    let b = fs::read(p).map_err(|e| e.to_string())?;
    serde_json::from_slice(&b).map_err(|e| e.to_string())
}
fn print_json<T: serde::Serialize>(v: &T) -> Result<(), String> {
    let rendered = serde_json::to_string_pretty(v).map_err(|e| e.to_string())?;
    let mut stdout = io::stdout().lock();
    match writeln!(stdout, "{rendered}") {
        Ok(()) => Ok(()),
        Err(e) if e.kind() == io::ErrorKind::BrokenPipe => Ok(()),
        Err(e) => Err(e.to_string()),
    }
}
fn usage() -> ! {
    eprintln!("usage: lattice <validate|explain|compare|next|apply|seal-witness|omega-import|nexus-audit> ...");
    std::process::exit(2)
}

fn run() -> Result<i32, String> {
    let a: Vec<String> = env::args().collect();
    if a.len() < 3 {
        usage()
    }
    match a[1].as_str() {
        "validate" => {
            let c: ClaimRecord = read(&a[2])?;
            let r = validate_claim(&c);
            print_json(&r)?;
            Ok(if r.valid { 0 } else { 3 })
        }
        "explain" => {
            let c: ClaimRecord = read(&a[2])?;
            let validation = validate_claim(&c);
            let next = next_action(&c.assurance)?;
            print_json(
                &serde_json::json!({"validation":validation,"assurance":c.assurance,"next_action":next}),
            )?;
            Ok(if validation.valid { 0 } else { 3 })
        }
        "compare" => {
            if a.len() != 4 {
                usage()
            }
            let x: AssuranceVector = read(&a[2])?;
            let y: AssuranceVector = read(&a[3])?;
            print_json(&serde_json::json!({"relation":x.relation(&y)?}))?;
            Ok(0)
        }
        "next" => {
            let c: ClaimRecord = read(&a[2])?;
            print_json(&next_action(&c.assurance)?)?;
            Ok(0)
        }
        "apply" => {
            if a.len() != 4 {
                usage()
            }
            let v: AssuranceVector = read(&a[2])?;
            let e: EvidenceEdge = read(&a[3])?;
            print_json(&apply_edge(&v, &e)?)?;
            Ok(0)
        }
        "seal-witness" => {
            let w: EvidenceWitness = read(&a[2])?;
            print_json(&w.seal()?)?;
            Ok(0)
        }
        "omega-import" => {
            let r: Value = read(&a[2])?;
            print_json(&import_aether_lineage_report(&r)?)?;
            Ok(0)
        }
        "nexus-audit" => {
            if a.len() != 4 {
                usage()
            }
            let m: NexusManifest = read(&a[2])?;
            let r = audit_checkout(&m, Path::new(&a[3]))?;
            print_json(&r)?;
            Ok(if r.status == "PASS" { 0 } else { 4 })
        }
        _ => usage(),
    }
}
fn main() {
    match run() {
        Ok(code) => std::process::exit(code),
        Err(e) => {
            eprintln!("lattice: {e}");
            std::process::exit(2)
        }
    }
}
