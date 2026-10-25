#!/usr/bin/env node
'use strict';
const {spawnSync} = require('node:child_process');
const pkg = require('../package.json');
const target = `@techreloaded/websmith-${process.platform}-${process.arch}`;
if (!Object.hasOwn(pkg.optionalDependencies, target)) {
  console.error(`Websmith: piattaforma non supportata: ${process.platform}-${process.arch}`);
  process.exit(1);
}
let executable;
try {
  executable = require.resolve(`${target}/bin/websmith${process.platform === 'win32' ? '.exe' : ''}`);
  if (require(`${target}/package.json`).version !== pkg.version) throw new Error('Version mismatch');
} catch {
  console.error(`Websmith: manca il motore ${target}@${pkg.version}. Reinstalla senza --omit=optional.`);
  process.exit(1);
}
const args = process.argv.slice(2);
if (args[0] === 'version') args[0] = '--version';
const result = spawnSync(executable, args, {stdio: 'inherit', shell: false});
if (result.error) {
  console.error(`Websmith: impossibile avviare il motore: ${result.error.message}`);
  process.exit(1);
}
if (result.signal) process.kill(process.pid, result.signal);
else process.exit(result.status ?? 1);
