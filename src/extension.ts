import * as childProcess from 'child_process';
import * as fs from 'fs';
import * as path from 'path';
import * as readline from 'readline';
import * as vscode from 'vscode';

type PendingRequest = {
  resolve: (value: object) => void;
  reject: (reason: Error) => void;
  timeout: NodeJS.Timeout;
};

type SupportedLanguage = 'c' | 'cpp' | 'rust';

type StructAnalysis = {
  name: string;
  line: number;
  fields?: AnalysisField[];
  layout: LayoutResult;
  analysis: AnalysisResult;
};

type AnalysisField = {
  name: string;
  raw_type?: string;
  type?: string;
  size: number;
  alignment: number;
  line?: number;
  offset?: number;
  padding_after?: number;
};

type LayoutResult = {
  fields: AnalysisField[];
  total_size: number;
  total_padding: number;
  alignment: number;
};

type AnalysisResult = {
  waste_bytes: number;
  waste_ratio: number;
  optimal_size: number;
  savings: number;
  cache_line_splits: Array<{ field_name: string; offset: number; size: number; line_size: number }>;
  warnings: string[];
  optimal_order?: AnalysisField[];
};

type AnalyseResponse = {
  structs?: StructAnalysis[];
  error?: string;
};

type AnalysisContext = {
  uri: vscode.Uri;
  source: string;
  language: SupportedLanguage;
  cursorLine: number;
};

export class PythonServer {
  private proc?: childProcess.ChildProcessWithoutNullStreams;
  private rl?: readline.Interface;
  private pending: PendingRequest[] = [];
  private stderrBuffer = '';

  start(pythonPath: string, serverScript: string): Promise<void> {
    return new Promise((resolve, reject) => {
      const proc = childProcess.spawn(pythonPath, [serverScript], {
        cwd: path.dirname(path.dirname(serverScript)),
        stdio: ['pipe', 'pipe', 'pipe']
      });
      this.proc = proc;

      const failStart = (error: Error) => {
        reject(error);
      };

      proc.once('error', failStart);
      proc.once('spawn', () => {
        proc.off('error', failStart);
        this.rl = readline.createInterface({ input: proc.stdout });
        this.rl.on('line', (line) => this.handleLine(line));
        proc.stderr.on('data', (chunk: Buffer) => {
          this.stderrBuffer += chunk.toString('utf8');
          if (this.stderrBuffer.length > 8192) {
            this.stderrBuffer = this.stderrBuffer.slice(-8192);
          }
        });
        proc.once('exit', (code, signal) => this.rejectAll(new Error(`Python server exited (${code ?? signal ?? 'unknown'}): ${this.stderrBuffer}`)));
        resolve();
      });
    });
  }

  send(request: object): Promise<object> {
    if (!this.proc || !this.proc.stdin.writable) {
      return Promise.reject(new Error('Python server is not running'));
    }

    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        const index = this.pending.findIndex((entry) => entry.resolve === resolve);
        if (index >= 0) {
          this.pending.splice(index, 1);
        }
        reject(new Error(`Python server request timed out. stderr: ${this.stderrBuffer}`));
      }, 5000);

      this.pending.push({ resolve, reject, timeout });
      this.proc!.stdin.write(`${JSON.stringify(request)}\n`, 'utf8', (error) => {
        if (error) {
          clearTimeout(timeout);
          const index = this.pending.findIndex((entry) => entry.resolve === resolve);
          if (index >= 0) {
            this.pending.splice(index, 1);
          }
          reject(error);
        }
      });
    });
  }

  dispose(): void {
    this.rejectAll(new Error('Python server disposed'));
    this.rl?.close();
    this.proc?.kill();
    this.proc = undefined;
    this.rl = undefined;
  }

  private handleLine(line: string): void {
    const next = this.pending.shift();
    if (!next) {
      return;
    }
    clearTimeout(next.timeout);
    try {
      next.resolve(JSON.parse(line));
    } catch (error) {
      next.reject(error instanceof Error ? error : new Error(String(error)));
    }
  }

  private rejectAll(error: Error): void {
    for (const entry of this.pending.splice(0)) {
      clearTimeout(entry.timeout);
      entry.reject(error);
    }
  }
}

let outputChannel: vscode.OutputChannel | undefined;
let currentPanel: vscode.WebviewPanel | undefined;
let diagnosticCollection: vscode.DiagnosticCollection | undefined;
let selectedPlatform = 'x86_64';
let selectedCacheLine = 64;
let lastAnalysisContext: AnalysisContext | undefined;
let lastStructName: string | undefined;
let lastKnownStructs: StructAnalysis[] | undefined;
let selectionDebounce: NodeJS.Timeout | undefined;

export async function activate(context: vscode.ExtensionContext) {
  outputChannel = vscode.window.createOutputChannel('StructScope');
  diagnosticCollection = vscode.languages.createDiagnosticCollection('structscope');
  context.subscriptions.push(outputChannel);
  context.subscriptions.push(diagnosticCollection);

  const server = new PythonServer();
  const serverScript = context.asAbsolutePath(path.join('python', 'server.py'));
  const pythonCandidates = getPythonCandidates();

  let started = false;
  const errors: string[] = [];
  for (const pythonPath of pythonCandidates) {
    try {
      await server.start(pythonPath, serverScript);
      outputChannel.appendLine(`Started Python server with ${pythonPath}`);
      started = true;
      break;
    } catch (error) {
      errors.push(`${pythonPath}: ${error instanceof Error ? error.message : String(error)}`);
    }
  }

  if (!started) {
    const message = `StructScope could not start Python. ${errors.join(' | ')}`;
    outputChannel.appendLine(message);
    vscode.window.showErrorMessage(message);
    return;
  }

  try {
    const ping = await server.send({ method: 'ping' });
    outputChannel.appendLine(`Ping response: ${JSON.stringify(ping)}`);
  } catch (error) {
    outputChannel.appendLine(`Ping failed: ${error instanceof Error ? error.message : String(error)}`);
  }

  context.subscriptions.push(
    vscode.commands.registerCommand('structscope.analyzeStruct', async () => {
      await analyzeActiveDocument(context, server);
    }),
    vscode.window.onDidChangeTextEditorSelection((event) => {
      if (!currentPanel) {
        return;
      }
      if (!languageFromDocument(event.textEditor.document)) {
        return;
      }
      if (selectionDebounce) {
        clearTimeout(selectionDebounce);
      }
      selectionDebounce = setTimeout(() => {
        void handleSelectionSettled(context, server, event.textEditor);
      }, 500);
    }),
    {
      dispose: () => {
        if (selectionDebounce) {
          clearTimeout(selectionDebounce);
        }
      }
    },
    { dispose: () => server.dispose() }
  );
}

export function deactivate() {
  // VS Code disposes subscriptions registered during activation.
}

function getPythonCandidates(): string[] {
  const configured = vscode.workspace.getConfiguration('structscope').get<string>('pythonPath')?.trim();
  if (configured) {
    return [configured, 'python3', 'python'];
  }
  return ['python3', 'python'];
}

export function openStructScopePanel(context: vscode.ExtensionContext, server: PythonServer): vscode.WebviewPanel {
  if (currentPanel) {
    currentPanel.reveal(vscode.ViewColumn.Beside);
    return currentPanel;
  }

  const panel = vscode.window.createWebviewPanel(
    'structscope',
    'StructScope',
    vscode.ViewColumn.Beside,
    {
      enableScripts: true,
      localResourceRoots: [vscode.Uri.joinPath(context.extensionUri, 'webview')]
    }
  );

  panel.webview.html = getWebviewHtml(context, panel.webview);
  panel.webview.onDidReceiveMessage(async (message) => {
    outputChannel?.appendLine(`Webview message: ${JSON.stringify(message)}`);
    if (message?.type === 'platform-change' && typeof message.platform === 'string') {
      selectedPlatform = message.platform;
      await rerunLastAnalysis(context, server);
    }
    if (message?.type === 'cache-line-change') {
      const cacheLine = Number(message.cacheLine);
      if (Number.isFinite(cacheLine) && cacheLine > 0) {
        selectedCacheLine = cacheLine;
        await rerunLastAnalysis(context, server);
      }
    }
  });
  panel.onDidDispose(() => {
    currentPanel = undefined;
  });

  currentPanel = panel;
  return panel;
}

function getWebviewHtml(context: vscode.ExtensionContext, webview: vscode.Webview): string {
  const htmlPath = vscode.Uri.joinPath(context.extensionUri, 'webview', 'index.html');
  const styleUri = webview.asWebviewUri(vscode.Uri.joinPath(context.extensionUri, 'webview', 'styles.css'));
  const scriptUri = webview.asWebviewUri(vscode.Uri.joinPath(context.extensionUri, 'webview', 'byteMap.js'));
  const nonce = getNonce();

  return fs
    .readFileSync(htmlPath.fsPath, 'utf8')
    .replace(/\{\{cspSource\}\}/g, webview.cspSource)
    .replace(/\{\{styleUri\}\}/g, styleUri.toString())
    .replace(/\{\{scriptUri\}\}/g, scriptUri.toString())
    .replace(/\{\{nonce\}\}/g, nonce);
}

function getNonce(): string {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
  let value = '';
  for (let i = 0; i < 32; i += 1) {
    value += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return value;
}

function languageFromDocument(document: vscode.TextDocument): SupportedLanguage | undefined {
  if (document.languageId === 'c') {
    return 'c';
  }
  if (document.languageId === 'cpp') {
    return 'cpp';
  }
  if (document.languageId === 'rust') {
    return 'rust';
  }
  const ext = path.extname(document.fileName).toLowerCase();
  if (ext === '.c' || ext === '.h') {
    return 'c';
  }
  if (ext === '.cc' || ext === '.cpp' || ext === '.cxx' || ext === '.hpp' || ext === '.hh' || ext === '.hxx') {
    return 'cpp';
  }
  if (ext === '.rs') {
    return 'rust';
  }
  return undefined;
}

async function analyzeActiveDocument(context: vscode.ExtensionContext, server: PythonServer): Promise<void> {
  const editor = vscode.window.activeTextEditor;
  if (!editor) {
    vscode.window.showErrorMessage('No active editor to analyse.');
    return;
  }

  const language = languageFromDocument(editor.document);
  if (!language) {
    vscode.window.showInformationMessage('StructScope supports C, C++, and Rust.');
    return;
  }

  const analysisContext: AnalysisContext = {
    uri: editor.document.uri,
    source: editor.document.getText(),
    language,
    cursorLine: editor.selection.active.line + 1
  };
  await runAnalysis(context, server, analysisContext, true);
}

async function rerunLastAnalysis(context: vscode.ExtensionContext, server: PythonServer): Promise<void> {
  const editor = vscode.window.activeTextEditor;
  if (editor) {
    const language = languageFromDocument(editor.document);
    if (language) {
      lastAnalysisContext = {
        uri: editor.document.uri,
        source: editor.document.getText(),
        language,
        cursorLine: editor.selection.active.line + 1
      };
    }
  }
  if (!lastAnalysisContext) {
    return;
  }
  await runAnalysis(context, server, lastAnalysisContext, false);
}

async function runAnalysis(
  context: vscode.ExtensionContext,
  server: PythonServer,
  analysisContext: AnalysisContext,
  revealPanel: boolean
): Promise<void> {
  const request = {
    method: 'analyse',
    source: analysisContext.source,
    language: analysisContext.language,
    platform: selectedPlatform,
    cache_line: selectedCacheLine
  };

  let response: AnalyseResponse;
  try {
    response = (await server.send(request)) as AnalyseResponse;
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    outputChannel?.appendLine(`Analysis request failed: ${message}`);
    vscode.window.showErrorMessage(`StructScope analysis failed: ${message}`);
    return;
  }

  outputChannel?.appendLine(`Analysis response: ${JSON.stringify(response)}`);
  if (response.error) {
    outputChannel?.appendLine(`Python error: ${response.error}`);
    vscode.window.showErrorMessage(`StructScope analysis failed: ${response.error}`);
    return;
  }
  if (!response.structs || response.structs.length === 0) {
    clearDiagnostics(analysisContext.uri);
    lastKnownStructs = undefined;
    vscode.window.showInformationMessage('No structs found in the active document.');
    return;
  }
  lastKnownStructs = response.structs;

  const document = vscode.workspace.textDocuments.find((candidate) => candidate.uri.toString() === analysisContext.uri.toString());
  if (document) {
    updateDiagnostics(document, response.structs);
  }

  const selected = findNearestStruct(response.structs, analysisContext.cursorLine);
  if (!selected) {
    vscode.window.showInformationMessage('No structs found near the cursor.');
    return;
  }

  lastAnalysisContext = analysisContext;
  lastStructName = selected.name;
  const panel = openStructScopePanel(context, server);
  if (revealPanel) {
    panel.reveal(vscode.ViewColumn.Beside);
  }

  await panel.webview.postMessage({
    type: 'layout',
    data: {
      ...selected,
      platform: selectedPlatform,
      cache_line: selectedCacheLine
    }
  });
  await panel.webview.postMessage({ type: 'platform', value: selectedPlatform, cacheLine: selectedCacheLine });
}

async function handleSelectionSettled(
  context: vscode.ExtensionContext,
  server: PythonServer,
  editor: vscode.TextEditor
): Promise<void> {
  if (!currentPanel) {
    return;
  }
  const language = languageFromDocument(editor.document);
  if (!language) {
    return;
  }
  const cursorLine = editor.selection.active.line + 1;
  const nearest = lastKnownStructs && lastAnalysisContext?.uri.toString() === editor.document.uri.toString()
    ? findNearestStruct(lastKnownStructs, cursorLine)
    : undefined;

  if (nearest && nearest.name === lastStructName) {
    return;
  }

  await runAnalysis(
    context,
    server,
    {
      uri: editor.document.uri,
      source: editor.document.getText(),
      language,
      cursorLine
    },
    false
  );
}

function findNearestStruct(structs: StructAnalysis[], cursorLine: number): StructAnalysis | undefined {
  return structs.reduce<StructAnalysis | undefined>((best, candidate) => {
    if (!best) {
      return candidate;
    }
    const bestDistance = Math.abs((best.line ?? 1) - cursorLine);
    const candidateDistance = Math.abs((candidate.line ?? 1) - cursorLine);
    return candidateDistance < bestDistance ? candidate : best;
  }, undefined);
}

function updateDiagnostics(document: vscode.TextDocument, structs: StructAnalysis[]): void {
  const diagnostics: vscode.Diagnostic[] = [];

  for (const struct of structs) {
    const fields = struct.layout?.fields || [];
    for (const field of fields) {
      const fieldLine = field.line ?? struct.line;
      if (Number(field.padding_after || 0) > 0) {
        diagnostics.push(
          new vscode.Diagnostic(
            rangeForLine(document, fieldLine),
            `${field.padding_after} bytes of padding after this field`,
            vscode.DiagnosticSeverity.Hint
          )
        );
      }
    }

    for (const split of struct.analysis?.cache_line_splits || []) {
      const field = fields.find((candidate) => candidate.name === split.field_name);
      diagnostics.push(
        new vscode.Diagnostic(
          rangeForLine(document, field?.line ?? struct.line),
          'This field straddles a cache line boundary',
          vscode.DiagnosticSeverity.Warning
        )
      );
    }

    if (Number(struct.analysis?.waste_ratio || 0) > 0.2) {
      diagnostics.push(
        new vscode.Diagnostic(
          rangeForLine(document, struct.line),
          `Struct is ${Math.round(struct.analysis.waste_ratio * 100)}% padding — consider reordering fields`,
          vscode.DiagnosticSeverity.Hint
        )
      );
    }
  }

  diagnosticCollection?.set(document.uri, diagnostics);
}

function clearDiagnostics(uri: vscode.Uri): void {
  diagnosticCollection?.set(uri, []);
}

function rangeForLine(document: vscode.TextDocument, oneBasedLine: number | undefined): vscode.Range {
  const line = Math.min(Math.max((oneBasedLine ?? 1) - 1, 0), Math.max(document.lineCount - 1, 0));
  const textLine = document.lineAt(line);
  return new vscode.Range(line, 0, line, textLine.range.end.character);
}
