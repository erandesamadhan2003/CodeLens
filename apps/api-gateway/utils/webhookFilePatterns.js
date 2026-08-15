const DEPENDENCY_MANIFESTS = new Set(['package.json', 'requirements.txt']);

const ROUTE_PATTERNS = [
  /(^|\/)routes\//i,
  /(^|\/)controllers\//i,
  /(^|\/)api\//i,
  /\.controller\./i,
  /\.route\./i,
  /\.routes\./i,
];

function normalizePath(filePath) {
  return String(filePath || '').replace(/\\/g, '/');
}

/**
 * True when the push touches package.json or requirements.txt.
 */
export function touchesDependencyManifest(changedFiles = []) {
  return changedFiles.some((file) => {
    const normalized = normalizePath(file);
    const base = normalized.split('/').pop();
    return DEPENDENCY_MANIFESTS.has(base);
  });
}

/**
 * True when the push touches route/controller/API handler files.
 */
export function touchesRouteFiles(changedFiles = []) {
  return changedFiles.some((file) => {
    const normalized = normalizePath(file);
    return ROUTE_PATTERNS.some((pattern) => pattern.test(normalized));
  });
}
