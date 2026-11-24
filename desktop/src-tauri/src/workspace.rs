//! Desktop location and main-window layout. Research content stays in the shared backend.
use crate::{file_io::replace_file, lifecycle::authorize, window_layout::Layout, Runtime};
use serde::{Deserialize, Serialize};
use std::{fs, io::Read, path::Path, sync::Arc};
use tauri::Manager;

const MAX_RECORD_BYTES: u64 = 8192;

#[derive(Debug, Deserialize, PartialEq, Serialize)]
#[serde(deny_unknown_fields)]
struct Record {
    route: String,
    window: Layout,
}

fn valid_route(route: &str) -> bool {
    route.len() <= 4096
        && route.starts_with('/')
        && !route.starts_with("//")
        && !route.contains(['\\', '#'])
        && !route.chars().any(char::is_control)
}

fn read(root: &Path) -> Result<Option<Record>, String> {
    let file = match fs::File::open(root.join("workspace.json")) {
        Ok(file) => file,
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => return Ok(None),
        Err(error) => return Err(error.to_string()),
    };
    let mut bytes = Vec::new();
    file.take(MAX_RECORD_BYTES + 1)
        .read_to_end(&mut bytes)
        .map_err(|e| e.to_string())?;
    if bytes.len() as u64 > MAX_RECORD_BYTES {
        return Err("Workspace record is too large".into());
    }
    let record: Record = serde_json::from_slice(&bytes).map_err(|e| e.to_string())?;
    if !valid_route(&record.route) {
        return Err("Workspace route must be an application-relative location".into());
    }
    record.window.validate()?;
    Ok(Some(record))
}

fn write(root: &Path, record: Record) -> Result<(), String> {
    if !valid_route(&record.route) {
        return Err("Workspace route must be an application-relative location".into());
    }
    record.window.validate()?;
    let bytes = serde_json::to_vec(&record).map_err(|e| e.to_string())?;
    if bytes.len() as u64 > MAX_RECORD_BYTES {
        return Err("Workspace record is too large".into());
    }
    fs::create_dir_all(root).map_err(|e| e.to_string())?;
    replace_file(&root.join("workspace.json"), &bytes).map_err(|e| e.to_string())
}

fn authorize_main(window: &tauri::WebviewWindow, state: &Runtime) -> Result<(), String> {
    authorize(window, state)?;
    if window.label() != "main" {
        return Err("Only the main research window owns the workspace location".into());
    }
    Ok(())
}

#[tauri::command]
pub fn read_workspace(
    window: tauri::WebviewWindow,
    state: tauri::State<'_, Arc<Runtime>>,
) -> Result<Option<String>, String> {
    authorize_main(&window, &state)?;
    let _guard = state.workspace.lock().unwrap();
    let record = read(
        &window
            .app_handle()
            .path()
            .app_local_data_dir()
            .map_err(|e| e.to_string())?,
    )?;
    if let Some(record) = record {
        record.window.restore(&window)?;
        Ok(Some(record.route))
    } else {
        Ok(None)
    }
}

#[tauri::command]
pub fn save_workspace(
    window: tauri::WebviewWindow,
    state: tauri::State<'_, Arc<Runtime>>,
    route: String,
) -> Result<(), String> {
    authorize_main(&window, &state)?;
    let _guard = state.workspace.lock().unwrap();
    write(
        &window
            .app_handle()
            .path()
            .app_local_data_dir()
            .map_err(|e| e.to_string())?,
        Record {
            route,
            window: Layout::capture(&window)?,
        },
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::{AtomicUsize, Ordering};
    static NEXT: AtomicUsize = AtomicUsize::new(0);

    fn record(route: &str) -> Record {
        serde_json::from_value(serde_json::json!({
            "route": route,
            "window": {"left": 40, "top": 60, "right": 1320, "bottom": 900, "maximized": true}
        }))
        .unwrap()
    }

    fn in_directory(test: impl FnOnce(&Path)) {
        let root = std::env::temp_dir().join(format!(
            "cardlab-workspace-{}-{}",
            std::process::id(),
            NEXT.fetch_add(1, Ordering::Relaxed)
        ));
        fs::create_dir_all(&root).unwrap();
        test(&root);
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn missing_then_replaced_record_round_trips_without_an_origin() {
        in_directory(|root| {
            assert_eq!(read(root).unwrap(), None);
            write(root, record("/research/study-1")).unwrap();
            write(
                root,
                record("/experiments/compare?snapshot=c1&seed=12&turn=3"),
            )
            .unwrap();
            assert_eq!(
                read(root).unwrap(),
                Some(record("/experiments/compare?snapshot=c1&seed=12&turn=3"))
            );
            assert_eq!(fs::read_dir(root).unwrap().count(), 1);
        });
    }

    #[test]
    fn invalid_routes_do_not_overwrite_the_saved_location() {
        in_directory(|root| {
            write(root, record("/")).unwrap();
            for route in [
                "https://example.com",
                "//example.com",
                "/\\example.com",
                "/\n",
                "/#fragment",
                "",
            ] {
                assert!(write(root, record(route)).is_err());
            }
            assert!(write(root, record(&format!("/{}", "a".repeat(4096)))).is_err());
            assert_eq!(read(root).unwrap(), Some(record("/")));
        });
    }

    #[test]
    fn malformed_and_oversized_records_are_errors_not_empty_successes() {
        in_directory(|root| {
            for bytes in [
                b"{".to_vec(),
                br#"{"route":"/"}"#.to_vec(),
                br#"{"route":"/","unexpected":true}"#.to_vec(),
                br#"{"route":"//example.com"}"#.to_vec(),
                vec![b' '; 8193],
            ] {
                fs::write(root.join("workspace.json"), bytes).unwrap();
                assert!(read(root).is_err());
            }
        });
    }

    #[test]
    fn invalid_layout_is_rejected_without_replacing_the_current_record() {
        in_directory(|root| {
            write(root, record("/research/kept")).unwrap();
            let mut raw = serde_json::to_value(record("/research/new")).unwrap();
            raw["window"]["right"] = serde_json::json!(0);
            let invalid: Record = serde_json::from_value(raw.clone()).unwrap();
            assert!(write(root, invalid).is_err());
            assert_eq!(read(root).unwrap(), Some(record("/research/kept")));
            fs::write(
                root.join("workspace.json"),
                serde_json::to_vec(&raw).unwrap(),
            )
            .unwrap();
            assert!(read(root).is_err());
            raw["window"]["unexpected"] = serde_json::json!(true);
            assert!(serde_json::from_value::<Record>(raw).is_err());
        });
    }

    #[test]
    fn unreadable_record_is_not_reported_as_missing() {
        in_directory(|root| {
            fs::create_dir(root.join("workspace.json")).unwrap();
            assert!(read(root).is_err());
        });
    }
}
