use crate::{file_io::replace_file, lifecycle::authorize, Runtime};
use std::{
    collections::BTreeMap,
    os::windows::ffi::OsStrExt,
    path::{Path, PathBuf},
    sync::{atomic::Ordering, Arc},
};
use tauri_plugin_dialog::DialogExt;
use windows_sys::Win32::{
    System::Com::{CoInitializeEx, CoUninitialize, COINIT_APARTMENTTHREADED},
    UI::Shell::{ILCreateFromPathW, ILFree, SHOpenFolderAndSelectItems},
};

const MAX_EXPORT_BYTES: usize = 32 * 1024 * 1024;

/// Paths stay in the host; each window owns only its latest successful export.
#[derive(Default)]
pub struct SavedExports {
    next: u64,
    files: BTreeMap<String, (String, PathBuf)>,
}

impl SavedExports {
    fn remember(&mut self, owner: &str, path: PathBuf) -> String {
        self.next += 1;
        let id = self.next.to_string();
        self.files.insert(owner.into(), (id.clone(), path));
        id
    }

    fn resolve(&self, owner: &str, id: &str) -> Result<PathBuf, String> {
        self.files
            .get(owner)
            .filter(|(saved_id, _)| saved_id == id)
            .map(|(_, path)| path.clone())
            .ok_or_else(|| "No matching saved export for this window".into())
    }

    pub fn forget(&mut self, owner: &str) {
        self.files.remove(owner);
    }
}

#[derive(Clone, Copy, serde::Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum ExportFormat {
    Json,
    Html,
}
impl ExportFormat {
    fn extension(self) -> &'static str {
        match self {
            Self::Json => "json",
            Self::Html => "html",
        }
    }
}

fn validate(filename: &str, content: &str, format: ExportFormat) -> Result<(), String> {
    if filename.len() > 200
        || !filename.ends_with(&format!(".{}", format.extension()))
        || filename.len() <= 5
        || filename
            .chars()
            .any(|c| c.is_control() || "<>:\"/\\|?*".contains(c))
    {
        return Err("Invalid export filename".into());
    }
    if content.len() > MAX_EXPORT_BYTES {
        return Err("Export exceeds 32 MiB".into());
    }
    if matches!(format, ExportFormat::Json) {
        serde_json::from_str::<serde_json::Value>(content).map_err(|_| "Invalid JSON content")?;
    }
    Ok(())
}

fn save(path: &Path, content: &str, format: ExportFormat) -> Result<(), String> {
    if !path
        .extension()
        .is_some_and(|extension| extension.eq_ignore_ascii_case(format.extension()))
    {
        return Err("Choose a file matching the export format".into());
    }
    replace_file(path, content.as_bytes()).map_err(|_| "Unable to save the export".into())
}

struct ExportGuard(Arc<Runtime>);
impl Drop for ExportGuard {
    fn drop(&mut self) {
        self.0.close.lock().unwrap().finish_export();
    }
}

fn reserve(state: &Arc<Runtime>) -> Result<ExportGuard, String> {
    let mut coordinator = state.close.lock().unwrap();
    if state.closing.load(Ordering::SeqCst) || !coordinator.begin_export() {
        return Err("Finish the current export or close request first".into());
    }
    Ok(ExportGuard(state.clone()))
}

fn reveal(path: &Path) -> Result<(), String> {
    if !path.is_file() {
        return Err("The saved export is no longer a file at this location".into());
    }
    let wide: Vec<u16> = path.as_os_str().encode_wide().chain(Some(0)).collect();
    // This worker owns its COM initialization; balance even an already initialized STA.
    if unsafe { CoInitializeEx(std::ptr::null(), COINIT_APARTMENTTHREADED as u32) } < 0 {
        return Err("Unable to initialize file location services".into());
    }
    struct Apartment;
    impl Drop for Apartment {
        fn drop(&mut self) {
            unsafe { CoUninitialize() };
        }
    }
    let _apartment = Apartment;
    // The null-terminated path lives through conversion; release the returned PIDL once.
    let item = unsafe { ILCreateFromPathW(wide.as_ptr()) };
    if item.is_null() {
        return Err("Unable to resolve the saved export".into());
    }
    // cidl = 0 takes one absolute item PIDL, opens its parent and selects that item.
    let result = unsafe { SHOpenFolderAndSelectItems(item, 0, std::ptr::null(), 0) };
    unsafe { ILFree(item) };
    if result < 0 {
        return Err("Unable to reveal the saved export".into());
    }
    Ok(())
}

#[tauri::command]
pub async fn save_export(
    window: tauri::WebviewWindow,
    state: tauri::State<'_, Arc<Runtime>>,
    filename: String,
    content: String,
    format: ExportFormat,
) -> Result<Option<String>, String> {
    authorize(&window, &state)?;
    validate(&filename, &content, format)?;
    let guard = reserve(state.inner())?;
    // Never block the native event loop while showing a system dialog or writing a file.
    tauri::async_runtime::spawn_blocking(move || {
        let selected = window
            .dialog()
            .file()
            .set_parent(&window)
            .set_file_name(filename)
            .add_filter(format.extension().to_uppercase(), &[format.extension()])
            .blocking_save_file();
        let Some(selected) = selected else {
            return Ok(None);
        };
        let path = selected
            .into_path()
            .map_err(|_| "Choose a local export file")?;
        save(&path, &content, format)?;
        let id = guard
            .0
            .exports
            .lock()
            .unwrap()
            .remember(window.label(), path);
        Ok(Some(id))
    })
    .await
    .map_err(|_| "Export could not finish".to_string())?
}

#[tauri::command]
pub async fn reveal_saved_export(
    window: tauri::WebviewWindow,
    state: tauri::State<'_, Arc<Runtime>>,
    id: String,
) -> Result<(), String> {
    authorize(&window, &state)?;
    let guard = reserve(state.inner())?;
    let path = state.exports.lock().unwrap().resolve(window.label(), &id)?;
    tauri::async_runtime::spawn_blocking(move || {
        let _guard = guard;
        reveal(&path)
    })
    .await
    .map_err(|_| "Revealing the export could not finish".to_string())?
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn reveal_rejects_missing_files_and_directories_before_calling_the_shell() {
        let root = tempfile::tempdir().unwrap();
        assert!(reveal(&root.path().join("missing.json")).is_err());
        assert!(reveal(root.path()).is_err());
    }

    #[test]
    fn saved_exports_are_window_scoped_and_only_keep_the_latest_success() {
        let mut exports = SavedExports::default();
        let first = exports.remember("main", PathBuf::from("first.json"));
        let evidence = exports.remember("evidence-0", PathBuf::from("evidence.json"));
        assert!(exports.resolve("evidence-0", &first).is_err());
        assert!(exports.resolve("main", "arbitrary-path.json").is_err());
        let second = exports.remember("main", PathBuf::from("second.json"));
        assert!(exports.resolve("main", &first).is_err());
        assert_eq!(
            exports.resolve("main", &second).unwrap(),
            PathBuf::from("second.json")
        );
        exports.forget("main");
        assert!(exports.resolve("main", &second).is_err());
        assert_eq!(
            exports.resolve("evidence-0", &evidence).unwrap(),
            PathBuf::from("evidence.json")
        );
        exports.forget("evidence-0");
        assert!(exports.files.is_empty());
    }

    #[test]
    fn reservation_rejects_overlap_and_final_shutdown() {
        let runtime = Arc::new(Runtime::default());
        let guard = reserve(&runtime).unwrap();
        assert!(reserve(&runtime).is_err());
        drop(guard);
        assert!(reserve(&runtime).is_ok());
        runtime.closing.store(true, Ordering::SeqCst);
        assert!(reserve(&runtime).is_err());
    }

    #[test]
    fn rejects_path_suggestions_invalid_json_and_oversized_payloads() {
        assert!(validate("研究.json", "{\"notes\":\"中文\"}", ExportFormat::Json).is_ok());
        for filename in ["../x.json", "C:\\x.json", "x.txt", ".json", "bad\n.json"] {
            assert!(validate(filename, "{}", ExportFormat::Json).is_err());
        }
        assert!(validate("report.json", "{bad", ExportFormat::Json).is_err());
        assert!(validate(
            "report.json",
            &" ".repeat(MAX_EXPORT_BYTES + 1),
            ExportFormat::Json
        )
        .is_err());
    }

    #[test]
    fn saves_exact_utf8_content_and_never_writes_other_extensions() {
        let root = tempfile::tempdir().unwrap();
        let path = root.path().join("研究.JSON");
        let content = "{\"notes\":\"中文\"}\n";
        save(&path, content, ExportFormat::Json).unwrap();
        assert_eq!(std::fs::read_to_string(path).unwrap(), content);
        let forbidden = root.path().join("keep.txt");
        std::fs::write(&forbidden, "kept").unwrap();
        assert!(save(&forbidden, content, ExportFormat::Json).is_err());
        assert_eq!(std::fs::read_to_string(forbidden).unwrap(), "kept");
    }

    #[test]
    fn html_uses_the_same_save_boundary_and_rejects_other_formats() {
        let root = tempfile::tempdir().unwrap();
        let path = root.path().join("report.html");
        let content = "<!doctype html><html lang=\"zh-CN\"><body>研究</body></html>";
        assert!(validate("report.html", content, ExportFormat::Html).is_ok());
        assert!(validate("report.exe", content, ExportFormat::Html).is_err());
        assert!(validate("report.json", content, ExportFormat::Html).is_err());
        assert!(serde_json::from_str::<ExportFormat>("\"exe\"").is_err());
        save(&path, content, ExportFormat::Html).unwrap();
        assert_eq!(std::fs::read_to_string(&path).unwrap(), content);
        assert!(save(&path, "{}", ExportFormat::Json).is_err());
        assert_eq!(std::fs::read_to_string(&path).unwrap(), content);
    }

    #[test]
    fn guard_releases_export_reservation_on_failure_or_cancel() {
        let runtime = Arc::new(Runtime::default());
        assert!(runtime.close.lock().unwrap().begin_export());
        drop(ExportGuard(runtime.clone()));
        assert!(!runtime.close.lock().unwrap().active());
    }
}
