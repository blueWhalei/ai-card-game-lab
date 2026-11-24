use crate::{
    close_state::{Request, Scope},
    Runtime,
};
use serde::{Deserialize, Serialize};
use std::{
    collections::BTreeSet,
    sync::{atomic::Ordering, Arc},
    time::Duration,
};
use tauri::{Emitter, Manager};
use tauri_plugin_dialog::{DialogExt, MessageDialogButtons};

#[derive(Clone, Serialize)]
#[serde(rename_all = "camelCase")]
struct Prepare {
    id: u64,
    app_exit: bool,
}

#[derive(Clone, Serialize)]
struct Cancelled {
    id: u64,
    reason: Option<String>,
}

#[derive(Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Outcome {
    Saved,
    SaveFailed,
    UnfinishedDesign,
    WorkspaceFailed,
}

pub fn grant_origin(app: &tauri::AppHandle, origin: &str) -> tauri::Result<()> {
    app.add_capability(serde_json::json!({
        "identifier": "research-lifecycle",
        "local": false,
        "remote": {"urls": [format!("{origin}/*")]},
        "windows": ["main", "evidence-*"],
        "permissions": ["allow-complete-close", "allow-cancel-close", "allow-save-export", "allow-reveal-saved-export", "core:event:allow-listen", "core:event:allow-unlisten"]
    }).to_string())?;
    app.add_capability(
        serde_json::json!({
            "identifier": "research-workspace",
            "local": false,
            "remote": {"urls": [format!("{origin}/*")]},
            "windows": ["main"],
            "permissions": ["allow-read-workspace", "allow-save-workspace"]
        })
        .to_string(),
    )
}

pub(crate) fn authorize(window: &tauri::WebviewWindow, state: &Runtime) -> Result<(), String> {
    let url = window.url().map_err(|e| e.to_string())?;
    if state.origin.lock().unwrap().as_ref() != Some(&url.origin().ascii_serialization()) {
        return Err("Native research commands require the owned research origin".into());
    }
    Ok(())
}

fn release(app: &tauri::AppHandle, request: Request, reason: Option<&str>) {
    for label in request.members {
        if let Some(window) = app.get_webview_window(&label) {
            let _ = app.emit_to(
                window.label(),
                "cardlab-close-cancelled",
                Cancelled {
                    id: request.id,
                    reason: reason.map(String::from),
                },
            );
        }
    }
}

fn cancel(app: &tauri::AppHandle, state: &Runtime, id: u64, reason: Option<&str>) {
    let request = state.close.lock().unwrap().cancel(id);
    if let Some(request) = request {
        release(app, request, reason);
    }
}

pub fn begin(app: &tauri::AppHandle, state: &Arc<Runtime>, label: &str) {
    if state.closing.load(Ordering::SeqCst) {
        return;
    }
    let scope = if label == "main" {
        Scope::App
    } else {
        Scope::Window(label.into())
    };
    let origin = state.origin.lock().unwrap().clone();
    let members: BTreeSet<String> = app
        .webview_windows()
        .into_iter()
        .filter(|(name, _)| scope == Scope::App || name == label)
        .filter(|(_, w)| {
            w.url()
                .ok()
                .is_some_and(|url| origin.as_ref() == Some(&url.origin().ascii_serialization()))
        })
        .map(|(name, _)| name)
        .collect();
    let request = state.close.lock().unwrap().begin(scope, members);
    let Some(request) = request else {
        return;
    };
    if request.members.is_empty() {
        confirm(app, state, request.id);
        return;
    }
    for member in &request.members {
        let sent = app.get_webview_window(member).is_some_and(|w| {
            app.emit_to(
                w.label(),
                "cardlab-close-requested",
                Prepare {
                    id: request.id,
                    app_exit: request.scope == Scope::App,
                },
            )
            .is_ok()
        });
        if !sent {
            cancel(app, state, request.id, Some("unresponsive"));
            return;
        }
    }
    let app = app.clone();
    let state = state.clone();
    std::thread::spawn(move || {
        std::thread::sleep(Duration::from_secs(45));
        let expired = state.close.lock().unwrap().timeout(request.id);
        if let Some(expired) = expired {
            release(&app, expired, Some("unresponsive"));
            app.dialog()
                .message("有窗口未能确认保存，应用和研究服务仍在运行。请返回窗口检查后重试关闭。")
                .title("暂未退出 CardLab")
                .show(|_| {});
        }
    });
}

fn finish(app: &tauri::AppHandle, state: &Runtime, id: u64) {
    let mut coordinator = state.close.lock().unwrap();
    let scope = coordinator.finish(id);
    if scope == Some(Scope::App) {
        state.closing.store(true, Ordering::SeqCst);
    }
    drop(coordinator);
    match scope {
        Some(Scope::App) => {
            app.exit(0);
        }
        Some(Scope::Window(label)) => {
            if let Some(window) = app.get_webview_window(&label) {
                let _ = window.destroy();
            }
        }
        None => {}
    }
}

fn confirm(app: &tauri::AppHandle, state: &Arc<Runtime>, id: u64) {
    let request = state.close.lock().unwrap().current();
    if !request.as_ref().is_some_and(|r| r.id == id) {
        return;
    }
    if matches!(request.unwrap().scope, Scope::Window(_)) {
        finish(app, state, id);
        return;
    }
    let handle = app.clone();
    let runtime = state.clone();
    let dialog = app
        .get_webview_window("main")
        .map(|w| w.dialog().clone())
        .unwrap_or_else(|| app.dialog().clone());
    dialog
        .message("草稿保存检查已完成。退出将停止本地服务，并中断尚未完成的任务；已保存数据会保留。")
        .title("退出 CardLab？")
        .buttons(MessageDialogButtons::OkCancelCustom(
            "退出".into(),
            "继续使用".into(),
        ))
        .show(move |confirmed| {
            if confirmed {
                finish(&handle, &runtime, id);
            } else {
                cancel(&handle, &runtime, id, None);
            }
        });
}

#[tauri::command]
pub fn complete_close(
    window: tauri::WebviewWindow,
    state: tauri::State<'_, Arc<Runtime>>,
    id: u64,
    outcome: Outcome,
) -> Result<(), String> {
    authorize(&window, &state)?;
    if !state.close.lock().unwrap().accepts(id, window.label()) {
        return Err("No pending close response for this window".into());
    }
    match outcome {
        Outcome::Saved => {
            let ready = state
                .close
                .lock()
                .unwrap()
                .acknowledge(id, window.label())?;
            if ready {
                confirm(window.app_handle(), &state, id);
            }
        }
        Outcome::SaveFailed | Outcome::UnfinishedDesign | Outcome::WorkspaceFailed => {
            let reason = match outcome {
                Outcome::SaveFailed => "save_failed",
                Outcome::UnfinishedDesign => "unfinished_design",
                _ => "workspace_failed",
            };
            cancel(window.app_handle(), &state, id, Some(reason));
            let _ = window.unminimize();
            let _ = window.set_focus();
        }
    }
    Ok(())
}

#[tauri::command]
pub fn cancel_close(
    window: tauri::WebviewWindow,
    state: tauri::State<'_, Arc<Runtime>>,
    id: u64,
) -> Result<(), String> {
    authorize(&window, &state)?;
    let current = state.close.lock().unwrap().current();
    if let Some(request) = current {
        if request.id != id || !request.members.contains(window.label()) {
            return Err("Cannot cancel another close request".into());
        }
        cancel(window.app_handle(), &state, id, None);
    }
    Ok(())
}
