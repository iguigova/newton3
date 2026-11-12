// Pyodide, off the page's thread: the page stays live while a command runs,
// and a page that frames this one is never held up by it. The files that
// demo/files.txt names are fetched from this site and written into Pyodide's
// file system as the repo lays them out, and demo/page.py answers each
// message: {id, name, args} in, {id, result} or {id, error} out.

import { loadPyodide } from 'https://cdn.jsdelivr.net/pyodide/v314.0.7/full/pyodide.mjs';

const ROOT = '/home/pyodide/newton3';

const fetched = async (path, as = 'text') => {
  const response = await fetch(`../${path.split('/').map(encodeURIComponent).join('/')}`);
  if (!response.ok) throw new Error(`${path} answered ${response.status}`);
  return response[as]();
};

const ready = (async () => {
  const [pyodide, manifest, page] = await Promise.all([
    loadPyodide(), fetched('demo/files.txt'), fetched('demo/page.py')]);
  const files = manifest.split('\n').filter(Boolean);
  const bodies = await Promise.all(files.map(f => fetched(f, 'arrayBuffer')));
  files.forEach((f, i) => {
    pyodide.FS.mkdirTree(`${ROOT}/${f.slice(0, f.lastIndexOf('/') + 1)}`);
    pyodide.FS.writeFile(`${ROOT}/${f}`, new Uint8Array(bodies[i]));
  });
  pyodide.FS.writeFile(`${ROOT}/demo/page.py`, page);
  pyodide.runPython(`
import os, sys
os.chdir(${JSON.stringify(ROOT)})
sys.path[:0] = ['src', '.', 'demo']
import page`);
  return { pyodide, page: pyodide.globals.get('page') };
})();

onmessage = async ({ data: { id, name, args } }) => {
  try {
    const { pyodide, page } = await ready;
    if (name === 'run' && args[0][0] === 'pytest') await pyodide.loadPackage('pytest');
    postMessage({ id, result: JSON.parse(page[name](...args.map(a => JSON.stringify(a)))) });
  } catch (e) {
    postMessage({ id, error: e.message });
  }
};
