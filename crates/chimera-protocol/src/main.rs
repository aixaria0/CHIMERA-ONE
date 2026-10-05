use chimera_protocol::{protocol_digest, validate_run};
use serde_json::Value;
use std::{env, fs, process::ExitCode};

fn usage() -> ExitCode {
    eprintln!("usage: chimera-protocol <validate-run|digest> FILE");
    ExitCode::from(2)
}

fn load(path: &str) -> Result<Value, String> {
    let bytes = fs::read(path).map_err(|e| format!("read {path}: {e}"))?;
    serde_json::from_slice(&bytes).map_err(|e| format!("parse {path}: {e}"))
}

fn main() -> ExitCode {
    let args: Vec<String> = env::args().collect();
    if args.len() != 3 {
        return usage();
    }
    let value = match load(&args[2]) {
        Ok(value) => value,
        Err(err) => {
            eprintln!("{err}");
            return ExitCode::from(2);
        }
    };
    match args[1].as_str() {
        "validate-run" => {
            let report = validate_run(&value);
            println!(
                "{}",
                serde_json::to_string_pretty(&report).expect("serialize report")
            );
            if report.valid {
                ExitCode::SUCCESS
            } else {
                ExitCode::from(3)
            }
        }
        "digest" => match protocol_digest(&value) {
            Ok(digest) => {
                println!("{digest}");
                ExitCode::SUCCESS
            }
            Err(err) => {
                eprintln!("{err}");
                ExitCode::from(3)
            }
        },
        _ => usage(),
    }
}
