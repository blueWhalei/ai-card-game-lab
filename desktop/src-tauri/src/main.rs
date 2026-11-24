#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod backend;
mod close_state;
mod export;
mod file_io;
mod lifecycle;
mod window_layout;
mod workspace;

use backend::Backend;
use std::{
    sync::{
        atomic::{AtomicBool, AtomicU64, Ordering},
        Arc, Mutex,
    },
    time::Duration,
};
use tauri::webview::NewWindowResponse;
use tauri::{Manager, WebviewUrl, WebviewWindowBuilder};
use tauri_plugin_dialog::DialogExt;

#[derive(Default)]
struct Runtime {
    backend: Mutex<Option<Backend>>,
    closing: AtomicBool,
    close: Mutex<close_state::Coordinator>,
    origin: Arc<Mutex<Option<String>>>,
    workspace: Mutex<()>,
    exports: Mutex<export::SavedExports>,
}

fn main() {
    let runtime = Arc::new(Runtime::default());
    let setup_runtime = runtime.clone();
    let close_runtime = runtime.clone();
    let app = tauri::Builder::default()
        .manage(runtime.clone())
        .invoke_handler(tauri::generate_handler![lifecycle::complete_close, lifecycle::cancel_close, workspace::read_workspace, workspace::save_workspace, export::save_export, export::reveal_saved_export])
        .plugin(tauri_plugin_single_instance::init(|app, _, _| {
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.unminimize();
                let _ = window.set_focus();
            }
        }))
        .plugin(tauri_plugin_dialog::init())
        .setup(move |app| {
            let origin = setup_runtime.origin.clone();
            let navigation_state = setup_runtime.clone();
            let popup_state = setup_runtime.clone();
            let navigation_origin = origin.clone();
            let popup_origin = origin.clone();
            let popup_app = app.handle().clone();
            let popup_counter = AtomicU64::new(0);
            let window = WebviewWindowBuilder::new(app, "main", WebviewUrl::App("index.html".into()))
                .title("CardLab").inner_size(1280.0, 840.0).min_inner_size(900.0, 640.0)
                .on_navigation(move |url| {
                    !navigation_state.close.lock().unwrap().active() &&
                    (url.scheme() == "tauri" || url.host_str() == Some("tauri.localhost")
                        || navigation_origin.lock().unwrap().as_ref() == Some(&url.origin().ascii_serialization()))
                })
                .on_new_window(move |url, features| {
                    if popup_state.close.lock().unwrap().active() { return NewWindowResponse::Deny; }
                    let evidence_state = popup_state.clone();
                    let allowed = popup_origin.lock().unwrap().clone();
                    if allowed.as_ref() != Some(&url.origin().ascii_serialization()) {
                        return NewWindowResponse::Deny;
                    }
                    let label = format!("evidence-{}", popup_counter.fetch_add(1, Ordering::SeqCst));
                    // Share the opener's WebView environment and session cookies.
                    // A separate window preserves the user's unsaved conclusion draft.
                    match WebviewWindowBuilder::new(&popup_app, label, WebviewUrl::External("about:blank".parse().unwrap()))
                        .window_features(features).title("CardLab · 证据").inner_size(1100.0, 780.0)
                        .on_navigation(move |next| !evidence_state.close.lock().unwrap().active() && (next.as_str() == "about:blank" || allowed.as_ref() == Some(&next.origin().ascii_serialization())))
                        .build() {
                        Ok(window) => NewWindowResponse::Create { window },
                        Err(_) => NewWindowResponse::Deny,
                    }
                })
                .build()?;
            let data = app.path().app_local_data_dir()?.join("research");
            let logs = app.path().app_local_data_dir()?.join("logs");
            std::fs::create_dir_all(&logs)?;
            std::fs::create_dir_all(&data)?;
            let executable = app.path().resource_dir()?.join("backend/cardlab-backend.exe");
            let log = logs.join("backend.log");
            // Keep startup failures visible in the local launcher, not a blank WebView.
            match Backend::start(&executable, &data, &log) {
                Err(_) => {
                    let detail = serde_json::to_string(&format!("无法启动研究服务。请检查安装是否完整；日志：{}", log.display()))?;
                    window.eval(format!("document.getElementById('status').textContent='启动失败';document.getElementById('detail').textContent={detail}"))?;
                }
                Ok((backend, ready)) => {
                    *setup_runtime.backend.lock().unwrap() = Some(backend);
                    let handle = app.handle().clone();
                    let state = setup_runtime.clone();
                    std::thread::spawn(move || {
                        let url = ready.recv_timeout(Duration::from_secs(60)).ok().and_then(Result::ok)
                            .and_then(|raw| raw.parse::<tauri::Url>().ok())
                            .filter(|url| url.scheme() == "http" && url.host_str() == Some("127.0.0.1")
                                && url.port().is_some() && url.path().starts_with("/desktop-session/"));
                        if let Some(url) = url {
                            let allowed_origin = url.origin().ascii_serialization();
                            if lifecycle::grant_origin(&handle, &allowed_origin).is_err() {
                                show_failure(&handle, &state, "无法建立工作台关闭保护，请查看应用日志。");
                                return;
                            }
                            *origin.lock().unwrap() = Some(allowed_origin);
                            // A launcher close confirmation may still be pending.
                            while state.close.lock().unwrap().active() && !state.closing.load(Ordering::SeqCst) {
                                std::thread::sleep(Duration::from_millis(100));
                            }
                            if state.closing.load(Ordering::SeqCst) { return; }
                            if window.navigate(url).is_err() {
                                show_failure(&handle, &state, "无法打开研究工作台，请查看应用日志。");
                                return;
                            }
                        } else {
                            show_failure(&handle, &state, "研究服务未能在 60 秒内就绪，请查看应用数据目录中的 logs/backend.log。");
                            return;
                        }
                        while !state.closing.load(Ordering::SeqCst) {
                            std::thread::sleep(Duration::from_millis(500));
                            let exited = state.backend.lock().unwrap().as_mut().is_some_and(Backend::exited);
                            if exited && !state.closing.load(Ordering::SeqCst) {
                                show_failure(&handle, &state, "研究服务已退出。请重新打开应用检查中断任务；已保存数据仍在应用数据目录中。");
                                break;
                            }
                        }
                    });
                }
            }
            Ok(())
        })
        .on_window_event(move |window, event| {
            if matches!(event, tauri::WindowEvent::Destroyed) {
                close_runtime.exports.lock().unwrap().forget(window.label());
            }
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                api.prevent_close();
                lifecycle::begin(window.app_handle(), &close_runtime, window.label());
            }

        })
        .build(tauri::generate_context!())
        .expect("Unable to initialize CardLab desktop");
    app.run(move |handle, event| {
        if let tauri::RunEvent::ExitRequested { api, .. } = &event {
            if !runtime.closing.load(Ordering::SeqCst) {
                api.prevent_exit();
                lifecycle::begin(handle, &runtime, "main");
            }
        }
        if matches!(event, tauri::RunEvent::Exit) {
            runtime.closing.store(true, Ordering::SeqCst);
            runtime.backend.lock().unwrap().take();
        }
    });
}

fn show_failure(app: &tauri::AppHandle, state: &Arc<Runtime>, message: &str) {
    state.closing.store(true, Ordering::SeqCst);
    state.backend.lock().unwrap().take();
    let handle = app.clone();
    app.dialog()
        .message(message)
        .title("CardLab 服务异常")
        .show(move |_| handle.exit(1));
}
