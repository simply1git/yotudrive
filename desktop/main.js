const { app, BrowserWindow, shell, ipcMain, Tray, Menu } = require('electron')
const path = require('path')
const { spawn } = require('child_process')
const http = require('http')

let mainWindow = null
let flaskProcess = null
let tray = null
const FLASK_PORT = 5055

// Platform-agnostic method to start the Python Flask backend
function startFlaskBackend() {
    console.log('Starting Python backend...')

    // In production, this would point to a bundled PyInstaller executable.
    // For development (or if Python is expected on path), we run `python app.py`
    // We use a specific port so Electron doesn't collide with a dev server.
    const appPath = app.isPackaged
        ? path.join(process.resourcesPath, 'app.py')
        : path.join(__dirname, '..', 'app.py')

    const pythonExec = process.platform === 'win32' ? 'python' : 'python3'

    flaskProcess = spawn(pythonExec, [appPath], {
        env: { ...process.env, PORT: FLASK_PORT, FLASK_ENV: app.isPackaged ? 'production' : 'development' },
        cwd: app.isPackaged ? process.resourcesPath : path.join(__dirname, '..'),
        detached: false
    })

    flaskProcess.stdout.on('data', (data) => console.log(`[Backend]: ${data}`))
    flaskProcess.stderr.on('data', (data) => console.error(`[Backend Err]: ${data}`))

    flaskProcess.on('close', (code) => {
        console.log(`Backend exited with code ${code}`)
    })
}

// Wait for Flask to boot before showing window
function waitForServer(url, timeoutMs, cb) {
    const start = Date.now()
    const check = () => {
        http.get(url, (res) => {
            if (res.statusCode === 200) cb(true)
            else setTimeout(check, 500)
        }).on('error', () => {
            if (Date.now() - start > timeoutMs) cb(false)
            else setTimeout(check, 500)
        })
    }
    check()
}

function createWindow() {
    mainWindow = new BrowserWindow({
        width: 1280,
        height: 800,
        titleBarStyle: 'hiddenInset',
        backgroundColor: '#050508',
        show: false, // Hide until Flask is ready
        webPreferences: {
            preload: path.join(__dirname, 'preload.js'),
            nodeIntegration: false,
            contextIsolation: true
        }
    })

    // Prevent external links opening inside the app
    mainWindow.webContents.setWindowOpenHandler(({ url }) => {
        if (url.startsWith('http')) {
            shell.openExternal(url)
            return { action: 'deny' }
        }
        return { action: 'allow' }
    })

    mainWindow.on('closed', () => {
        mainWindow = null
    })
}

function createTray() {
    // Use a placeholder icon if real one isn't present
    const iconPath = path.join(__dirname, 'icon.png')
    tray = new Tray(iconPath) // Assume icon.png exists or will be created
    const contextMenu = Menu.buildFromTemplate([
        { label: 'Open YotuDrive', click: () => { if (mainWindow) mainWindow.show() } },
        { type: 'separator' },
        { label: 'Quit', click: () => { app.isQuitting = true; app.quit() } }
    ])
    tray.setToolTip('YotuDrive')
    tray.setContextMenu(contextMenu)

    tray.on('click', () => {
        if (mainWindow) {
            mainWindow.isVisible() ? mainWindow.hide() : mainWindow.show()
        }
    })
}

app.whenReady().then(() => {
    startFlaskBackend()
    createWindow()

    // Try to create tray but don't crash if icon is missing right now
    try { createTray() } catch (e) { console.log("Tray icon missing, skipping tray.") }

    const serverUrl = `http://127.0.0.1:${FLASK_PORT}/api/health`
    console.log('Waiting for backend on', serverUrl)

    waitForServer(serverUrl, 15000, (isUp) => {
        if (isUp) {
            console.log('Backend is up! Loading app...')
            // Point Electron to the Flask server, which serves the Next.js static out folder
            mainWindow.loadURL(`http://127.0.0.1:${FLASK_PORT}`)
        } else {
            console.error('Backend failed to start. Falling back to local error page.')
            mainWindow.loadFile('error.html')
        }
        mainWindow.show()
    })

    app.on('activate', () => {
        if (BrowserWindow.getAllWindows().length === 0) {
            createWindow()
            mainWindow.loadURL(`http://127.0.0.1:${FLASK_PORT}`)
            mainWindow.show()
        }
    })
})

// Cleanup python on exit
app.on('before-quit', () => {
    if (flaskProcess) {
        // Windows taskkill
        if (process.platform === 'win32') {
            spawn('taskkill', ['/pid', flaskProcess.pid, '/f', '/t'])
        } else {
            flaskProcess.kill('SIGTERM')
        }
    }
})

app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') {
        app.quit()
    }
})

// Bridge simple IPCs
ipcMain.handle('get-platform', () => process.platform)
