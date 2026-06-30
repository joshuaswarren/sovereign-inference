// SPDX-License-Identifier: AGPL-3.0-or-later
//
// Desktop shell for Sovereign Inference (scaffold). On launch it starts the
// bundled `sip-openai-proxy` Python sidecar on http://localhost:11435 and opens
// the dashboard window. Build with the Tauri toolchain (see ../README.md).
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use tauri_plugin_shell::process::CommandEvent;
use tauri_plugin_shell::ShellExt;

const PROXY_PORT: &str = "11435";

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            // Start the OpenAI-compatible proxy as a sidecar so the dashboard (and
            // any local OpenAI client) can reach http://localhost:11435/v1.
            let sidecar = app
                .shell()
                .sidecar("sip-openai-proxy")
                .expect("the sip-openai-proxy sidecar binary was not bundled")
                .args(["--host", "127.0.0.1", "--port", PROXY_PORT]);

            let (mut rx, _child) = sidecar.spawn().expect("failed to start the proxy sidecar");
            tauri::async_runtime::spawn(async move {
                while let Some(event) = rx.recv().await {
                    match event {
                        CommandEvent::Stderr(line) | CommandEvent::Stdout(line) => {
                            eprintln!("[proxy] {}", String::from_utf8_lossy(&line));
                        }
                        _ => {}
                    }
                }
            });
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running the Sovereign Inference desktop app");
}
