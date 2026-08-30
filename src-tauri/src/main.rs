// ChronoLens Tauri shell: pick a free port, spawn the Python sidecar
// binary, expose the port to the frontend, and kill the sidecar on exit.

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::net::TcpListener;
use std::process::Command;
use std::sync::Mutex;

use tauri::{Manager, RunEvent};
use tauri_plugin_shell::ShellExt;

/// The sidecar child process and its unique port.
struct Sidecar {
    port: u16,
    child: Mutex<Option<u32>>, // pid
}

fn pick_free_port() -> u16 {
    // Bind to an OS-assigned port, read it, and hand it to the sidecar.
    // The listener is dropped immediately, and uvicorn binds within the
    // spawn window, so the OS does not reassign the port in between.
    let listener = TcpListener::bind("127.0.0.1:0").expect("bind 127.0.0.1:0");
    listener.local_addr().expect("local addr").port()
}

fn spawn_sidecar(app: &tauri::AppHandle, port: u16) -> u32 {
    let sidecar = app
        .shell()
        .sidecar("chronolens-backend")
        .expect("sidecar binary declared in tauri.conf.json");
    let (_events, child) = sidecar
        .args(["--port", &port.to_string()])
        .spawn()
        .expect("spawn chronolens-backend");
    let pid = child.pid();
    println!("chronolens: sidecar spawned on port {port} (pid {pid})");
    pid
}

#[tauri::command]
fn backend_port(state: tauri::State<'_, Mutex<u16>>) -> u16 {
    *state.lock().expect("port lock")
}

fn main() {
    let port = pick_free_port();

    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .setup(move |app| {
            let pid = spawn_sidecar(&app.handle(), port);
            app.manage(Sidecar {
                port,
                child: Mutex::new(Some(pid)),
            });
            app.manage(Mutex::new(port));
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![backend_port])
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app_handle, event| {
            if let RunEvent::Exit = event {
                // Reap the sidecar. The tracked pid is the PyInstaller
                // bootloader, which re-execs during onefile extraction,
                // so the pid alone is unreliable — match the unique
                // "--port <port>" command line instead, which catches the
                // real server process regardless of re-exec.
                if let Some(state) = app_handle.try_state::<Sidecar>() {
                    if let Ok(mut guard) = state.child.lock() {
                        if guard.take().is_some() {
                            let port = state.port;
                            let _ = Command::new("/usr/bin/pkill")
                                .args(["-TERM", "-f", &format!("chronolens-backend --port {port}")])
                                .status();
                            let _ = Command::new("/usr/bin/pkill")
                                .args(["-KILL", "-f", &format!("chronolens-backend --port {port}")])
                                .status();
                        }
                    }
                }
            }
        });
}
