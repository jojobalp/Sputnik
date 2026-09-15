const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

test('desktop opens compiled local game with isolated renderer', async () => {
  let loaded, options, ready;
  class Window {
    constructor(config) { options=config; this.webContents={setWindowOpenHandler(){},on(){}}; }
    loadFile(file) { loaded=file; }
  }
  const electron = {app:{whenReady:()=>({then:fn=>{ready=fn;}}),on(){}},BrowserWindow:Window,Menu:{setApplicationMenu(){}}};
  vm.runInNewContext(fs.readFileSync('desktop/main.cjs','utf8'), {
    require:name=>name==='electron'?electron:require(name),__dirname:path.resolve('desktop'),
  });
  ready();
  assert.equal(loaded,path.resolve('dist/index.html'));
  assert.equal(options.webPreferences.nodeIntegration,false);
  assert.equal(options.webPreferences.contextIsolation,true);
  assert.equal(options.webPreferences.sandbox,true);
});
test('build includes game and both Windows distribution formats', () => {
  const pkg=JSON.parse(fs.readFileSync('package.json'));
  assert.equal(pkg.main,'desktop/main.cjs');
  assert.ok(pkg.build.files.includes('dist/**/*'));
  assert.deepEqual(pkg.build.win.target.map(x=>x.target),['portable','zip']);
  assert.ok(!fs.readFileSync('style.css','utf8').includes('fonts.googleapis.com'));
});
