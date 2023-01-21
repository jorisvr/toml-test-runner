#![deny(warnings)]

/*
 * toml-rs-decoder
 *
 * Read a TOML file, decode it and write decoded data to stdout as tagged JSON
 * in the format expected by https://github.com/BurntSushi/toml-test
 *
 * This code is based on
 *   https://github.com/toml-rs/toml/blob/main/crates/toml/examples/toml2json.rs
 *   written by Ed Page.
 *
 * Modified by Joris van Rantwijk:
 *  - Implement "tagging" of JSON output in the format expected by the
 *    toml-test framework.
 *  - Exit with non-zero status if the TOML parser encounters an error.
 */

use std::env;
use std::fs::File;
use std::io;
use std::io::prelude::*;

use serde_json::Value as Json;
use serde_json::json;
use toml::Value as Toml;

fn main() {
    let mut args = env::args();
    let mut input = String::new();
    if args.len() > 1 {
        let name = args.nth(1).unwrap();
        File::open(&name)
            .and_then(|mut f| f.read_to_string(&mut input))
            .unwrap();
    } else {
        io::stdin().read_to_string(&mut input).unwrap();
    }

    match input.parse() {
        Ok(toml) => {
            let json = convert(toml);
            println!("{}", serde_json::to_string_pretty(&json).unwrap());
        }
        Err(error) => {
            println!("failed to parse TOML: {}", error);
            std::process::exit(1);
        }
    }
}

fn convert(toml: Toml) -> Json {
    match toml {
        Toml::String(s) =>
          json!({
            "type": "string",
            "value": s
          }),
        Toml::Integer(i) => 
          json!({
            "type": "integer",
            "value": i.to_string()
          }),
        Toml::Float(f) =>
          json!({
            "type": "float",
            "value": f.to_string().to_lowercase()
          }),
        Toml::Boolean(b) =>
          json!({
            "type": "bool",
            "value": b.to_string()
          }),
        Toml::Array(arr) => Json::Array(arr.into_iter().map(convert).collect()),
        Toml::Table(table) => {
            Json::Object(table.into_iter().map(|(k, v)| (k, convert(v))).collect())
        }
        Toml::Datetime(dt) => 
          if dt.date.is_none() {
            json!({
              "type": "time-local",
              "value": dt.to_string()
            })
          } else if dt.time.is_none() {
            json!({
              "type": "date-local",
              "value": dt.to_string()
            })
          } else if dt.offset.is_none() {
            json!({
              "type": "datetime-local",
              "value": dt.to_string()
            })
          } else {
            json!({
              "type": "datetime",
              "value": dt.to_string()
            })
          },
    }
}
