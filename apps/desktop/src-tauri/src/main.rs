// SPDX-License-Identifier: AGPL-3.0-or-later
//
// Desktop shell for Sovereign Inference. On launch it:
//   1. generates a per-install admin token,
//   2. starts the bundled `sip-app-server` Python sidecar on http://127.0.0.1:11435,
//      pointed at the OS app-data dir for persisted config,
//   3. injects { apiBase, token } into the webview (so the dashboard can reach the
//      token-guarded admin API), and shows the window once the server is healthy,
//   4. kills the sidecar when the app exits.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::net::TcpStream;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::time::Duration;

use tauri::{Manager, RunEvent, WebviewUrl, WebviewWindowBuilder};
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;

const HOST: &str = "127.0.0.1";
const PORT: u16 = 11435;

/// Holds the running sidecar so we can kill it on exit.
struct Sidecar(Mutex<Option<CommandChild>>);

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(Sidecar(Mutex::new(None)))
        .setup(|app| {
            let config_dir = app
                .path()
                .app_data_dir()
                .expect("could not resolve the app data dir");
            std::fs::create_dir_all(&config_dir).ok();
            let config_dir = config_dir.to_string_lossy().to_string();

            // A fresh per-install token gates the admin API; it is injected into
            // the webview below and never written to disk by the shell.
            let token = uuid::Uuid::new_v4().to_string();
            let port = PORT.to_string();
            let parent_pid = std::process::id().to_string();

            let (mut rx, child) = app
                .shell()
                .sidecar("sip-app-server")
                .expect("the sip-app-server sidecar binary was not bundled")
                .args([
                    "--config-dir",
                    &config_dir,
                    "--admin-token",
                    &token,
                    "--host",
                    HOST,
                    "--port",
                    &port,
                    // Exit if this shell dies by any means (signal/crash), not just a
                    // graceful quit — belt-and-suspenders with the kill on exit below.
                    "--parent-pid",
                    &parent_pid,
                ])
                .spawn()
                .expect("failed to start the app-server sidecar");
            app.state::<Sidecar>().0.lock().unwrap().replace(child);

            // Tracks whether the sidecar exited, so the window-show poll below can
            // stop waiting immediately if the server died (e.g. port in use) rather
            // than blanking for the full timeout.
            let exited = Arc::new(AtomicBool::new(false));
            let exited_writer = exited.clone();

            // Forward sidecar logs to the app's stderr for debugging.
            tauri::async_runtime::spawn(async move {
                while let Some(event) = rx.recv().await {
                    match event {
                        CommandEvent::Stderr(line) | CommandEvent::Stdout(line) => {
                            eprintln!("[server] {}", String::from_utf8_lossy(&line));
                        }
                        CommandEvent::Terminated(payload) => {
                            eprintln!("[server] exited: {:?}", payload);
                            exited_writer.store(true, Ordering::SeqCst);
                        }
                        _ => {}
                    }
                }
            });

            // Create the window hidden, with the token injected BEFORE page scripts
            // run, then reveal it once the server accepts connections. The token and
            // base URL are JSON-serialized (not string-interpolated) so no value can
            // break out of the script literal.
            let api_base = format!("http://{HOST}:{PORT}");
            let init_script = format!(
                "window.__SOVEREIGN__={{apiBase:{},token:{}}};",
                serde_json::to_string(&api_base).expect("serialize api base"),
                serde_json::to_string(&token).expect("serialize token"),
            );
            let window = WebviewWindowBuilder::new(app, "main", WebviewUrl::default())
                .title("Sovereign Inference")
                .inner_size(1100.0, 760.0)
                .resizable(true)
                .initialization_script(&init_script)
                .visible(false)
                .build()?;

            std::thread::spawn(move || {
                let addr = format!("{HOST}:{PORT}").parse().expect("valid loopback addr");
                // Wait up to ~30s for the sidecar to start listening, but bail early
                // if it exited. Either way the window is shown (the dashboard surfaces
                // an "unreachable" state itself) so it is never left permanently hidden.
                for _ in 0..120 {
                    if exited.load(Ordering::SeqCst) {
                        break;
                    }
                    if TcpStream::connect_timeout(&addr, Duration::from_millis(250)).is_ok() {
                        break;
                    }
                    std::thread::sleep(Duration::from_millis(250));
                }
                let _ = window.show();
                let _ = window.set_focus();
            });

            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building the Sovereign Inference desktop app")
        .run(|app, event| {
            if let RunEvent::ExitRequested { .. } = event {
                if let Some(child) = app.state::<Sidecar>().0.lock().unwrap().take() {
                    let _ = child.kill();
                }
            }
        });
}
