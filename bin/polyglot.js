#!/usr/bin/env node

/**
 * Polyglot CLI Wrapper (npx polyglot)
 * Provides true zero-friction onboarding for JavaScript / TypeScript / Frontend developers.
 *
 * Bootstrapping Lifecycle:
 * 1. Validates Python >= 3.10 is installed on the host.
 * 2. Creates a dedicated, isolated Python environment in `~/.polyglot/venv` if not in a dev repo.
 * 3. Ensures required core dependencies (`playwright`, `pydantic`, `python-dotenv`) are installed.
 * 4. Ensures Playwright Chromium headless browser binary is downloaded.
 * 5. Proxies all commands directly to `polyglot.cli`.
 */

const { spawn, execSync } = require('child_process');
const path = require('path');
const fs = require('fs');
const os = require('os');

function getPythonInfo() {
  const candidates = process.platform === 'win32' 
    ? ['python', 'py', 'python3'] 
    : ['python3', 'python'];

  for (const cmd of candidates) {
    try {
      const output = execSync(`${cmd} -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"`, {
        stdio: ['ignore', 'pipe', 'ignore']
      }).toString().trim();
      
      const parts = output.split('.').map(Number);
      if (parts.length >= 2) {
        const [major, minor] = parts;
        if (major === 3 && minor >= 10) {
          return { command: cmd, version: output };
        }
      }
    } catch (e) {
      // candidate not found or failed, continue
    }
  }
  return null;
}

function ensureEnvironment(systemPython, rootDir) {
  // If running inside polyglot source repo with local .venv, use it
  const repoVenvWin = path.join(rootDir, '.venv', 'Scripts', 'python.exe');
  const repoVenvNix = path.join(rootDir, '.venv', 'bin', 'python');
  if (fs.existsSync(repoVenvWin)) return { pythonBin: repoVenvWin, pipBin: path.join(rootDir, '.venv', 'Scripts', 'pip.exe') };
  if (fs.existsSync(repoVenvNix)) return { pythonBin: repoVenvNix, pipBin: path.join(rootDir, '.venv', 'bin', 'pip') };

  // Otherwise, use a persistent global user directory: ~/.polyglot/venv
  const homeDir = os.homedir();
  const polyglotDir = path.join(homeDir, '.polyglot');
  const venvDir = path.join(polyglotDir, 'venv');
  const venvPython = process.platform === 'win32' 
    ? path.join(venvDir, 'Scripts', 'python.exe')
    : path.join(venvDir, 'bin', 'python');
  const venvPip = process.platform === 'win32'
    ? path.join(venvDir, 'Scripts', 'pip.exe')
    : path.join(venvDir, 'bin', 'pip');

  if (!fs.existsSync(venvPython)) {
    console.log('⚡ Polyglot: Initializing isolated local engine runtime in ~/.polyglot/venv...');
    if (!fs.existsSync(polyglotDir)) {
      fs.mkdirSync(polyglotDir, { recursive: true });
    }
    try {
      execSync(`${systemPython} -m venv "${venvDir}"`, { stdio: 'inherit' });
    } catch (err) {
      console.error('❌ Failed to create virtual environment:', err.message);
      process.exit(1);
    }
  }

  // Verify dependencies installed in venv
  let needsDeps = false;
  try {
    execSync(`"${venvPython}" -c "import playwright, pydantic, dotenv"`, { stdio: ['ignore', 'ignore', 'ignore'] });
  } catch (e) {
    needsDeps = true;
  }

  if (needsDeps) {
    console.log('📦 Polyglot: Installing core dependencies (Playwright, Pydantic)...');
    try {
      execSync(`"${venvPip}" install --upgrade pip`, { stdio: 'inherit' });
      execSync(`"${venvPip}" install "${rootDir}"`, { stdio: 'inherit' });
    } catch (e) {
      // If rootDir is not an installable package path, install core packages directly
      execSync(`"${venvPip}" install "playwright>=1.40.0" "pydantic>=2.8.0" "python-dotenv>=1.0.1"`, { stdio: 'inherit' });
    }

    console.log('🌐 Polyglot: Ensuring Chromium browser binary is installed...');
    try {
      execSync(`"${venvPython}" -m playwright install chromium`, { stdio: 'inherit' });
    } catch (err) {
      console.warn('⚠️ Warning: Failed to auto-install Playwright chromium:', err.message);
    }
  }

  return { pythonBin: venvPython, pipBin: venvPip };
}

function main() {
  const args = process.argv.slice(2);
  const rootDir = path.resolve(__dirname, '..');

  const pyInfo = getPythonInfo();
  if (!pyInfo) {
    console.error('❌ Error: Python 3.10+ is required to run Polyglot Engine.');
    console.error('👉 Please install Python from https://www.python.org/downloads/ and ensure it is added to your PATH.');
    process.exit(1);
  }

  const { pythonBin } = ensureEnvironment(pyInfo.command, rootDir);

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
