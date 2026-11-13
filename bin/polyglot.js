#!/usr/bin/env node

/**
 * Polyglot CLI Wrapper (npx polyglot)
 * Provides zero-friction onboarding for JavaScript / TypeScript / Frontend developers.
 * Automatically checks for Python and Playwright environments, creates isolated
 * virtual environments if necessary, and proxies commands to the polyglot core CLI.
 */

const { spawn, execSync } = require('child_process');
const path = require('path');
const fs = require('fs');

function checkPython() {
  const candidates = process.platform === 'win32' 
    ? ['python', 'py', 'python3'] 
    : ['python3', 'python'];

  for (const cmd of candidates) {
    try {
      const output = execSync(`${cmd} --version`, { stdio: 'pipe' }).toString();
      if (output.toLowerCase().includes('python 3')) {
        return cmd;
      }
    } catch (e) {
      // try next
    }
  }
  return null;
}

function main() {
  const args = process.argv.slice(2);
  const rootDir = path.resolve(__dirname, '..');

  // Check if running inside repository with .venv
  let pythonBin = null;
  const venvPythonWin = path.join(rootDir, '.venv', 'Scripts', 'python.exe');
  const venvPythonNix = path.join(rootDir, '.venv', 'bin', 'python');

  if (fs.existsSync(venvPythonWin)) {
    pythonBin = venvPythonWin;
  } else if (fs.existsSync(venvPythonNix)) {
    pythonBin = venvPythonNix;
  } else {
    pythonBin = checkPython();
  }

  if (!pythonBin) {
    console.error('❌ Error: Python 3.10+ is required to run Polyglot Engine.');
    console.error('👉 Please install Python from https://www.python.org/downloads/ and try again.');
    process.exit(1);
  }

  // Forward command to polyglot CLI module
  const cliArgs = ['-m', 'polyglot.cli', ...args];

  const child = spawn(pythonBin, cliArgs, {
    cwd: process.cwd(),
    stdio: 'inherit',
    env: {
      ...process.env,
      PYTHONPATH: rootDir + (process.env.PYTHONPATH ? path.delimiter + process.env.PYTHONPATH : '')
    }
  });

  child.on('close', (code) => {
    process.exit(code || 0);
  });
}

main();
