fn main() {
    tauri_build::try_build(tauri_build::Attributes::new().app_manifest(
        tauri_build::AppManifest::new().commands(&[
            "complete_close",
            "cancel_close",
            "read_workspace",
            "save_workspace",
            "save_export",
            "reveal_saved_export",
        ]),
    ))
    .expect("Unable to build CardLab command permissions")
}
