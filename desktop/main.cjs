const { app, BrowserWindow, Menu } = require('electron');
const path = require('node:path');
app.whenReady().then(() => {
  Menu.setApplicationMenu(null);
  const win = new BrowserWindow({width:1366,height:900,backgroundColor:'#11130f',webPreferences:{nodeIntegration:false,contextIsolation:true,sandbox:true}});
  win.webContents.setWindowOpenHandler(()=>({action:'deny'}));
  win.webContents.on('will-navigate',event=>event.preventDefault());
  win.webContents.on('before-input-event',(event,input)=>{if(input.type==='keyDown'&&input.key==='F11'){event.preventDefault();win.setFullScreen(!win.isFullScreen());}});
  win.loadFile(path.join(__dirname,'..','dist','index.html'));
});
app.on('window-all-closed',()=>app.quit());
