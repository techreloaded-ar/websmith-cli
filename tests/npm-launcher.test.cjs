const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawnSync} = require('node:child_process');
test('missing native engine gives an actionable error', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'websmith-launcher-'));
  try {
    fs.cpSync(path.resolve('npm/websmith'), dir, {recursive:true});
    const result = spawnSync(process.execPath,[path.join(dir,'bin/websmith.cjs'),'version'],{encoding:'utf8'});
    assert.equal(result.status,1);
    assert.match(result.stderr,/manca il motore|piattaforma non supportata/);
  } finally {fs.rmSync(dir,{recursive:true,force:true});}
});
test('native engine receives arguments and exit status', {skip: process.platform === 'win32'}, () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'websmith-forward-'));
  try {
    fs.cpSync(path.resolve('npm/websmith'), dir, {recursive:true});
    const name = `websmith-${process.platform}-${process.arch}`;
    const dependency = path.join(dir,'node_modules','@techreloaded',name);
    fs.mkdirSync(path.join(dependency,'bin'),{recursive:true});
    fs.writeFileSync(path.join(dependency,'package.json'),JSON.stringify({version:require('../npm/websmith/package.json').version}));
    fs.writeFileSync(path.join(dependency,'bin/websmith'),'#!/bin/sh\nprintf "%s\\n" "$@"\nexit 7\n',{mode:0o755});
    const result=spawnSync(process.execPath,[path.join(dir,'bin/websmith.cjs'),'version','path with spaces'],{encoding:'utf8'});
    assert.equal(result.status,7);
    assert.equal(result.stdout,'--version\npath with spaces\n');
  } finally {fs.rmSync(dir,{recursive:true,force:true});}
});
