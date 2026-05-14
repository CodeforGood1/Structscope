# Struct Scope

Struct Scope is a local-first Visual Studio Code extension and command-line tool for inspecting the memory layout of C, C++, and Rust data structures. It parses source files, extracts struct-like definitions, computes ABI-aware field placement, and presents byte offsets, field sizes, alignment, padding, cache-line split risks, and reorder opportunities without requiring a compiler invocation.

The extension is intended for systems programming, embedded development, performance tuning, protocol design, and low-level code review workflows where object layout affects memory footprint, binary compatibility, cache behavior, or wire-format design.

## Core Capabilities

- Static layout analysis for C structs, C++ structs/classes with data members, and Rust structs
- ABI-aware size and alignment calculations for supported target platforms
- Visual byte map with colored field regions and distinct padding cells
- Field table with offsets, sizes, padding-after values, and cache-line notes
- Padding waste metrics and greedy field reorder suggestions
- Cache-line boundary detection for fields that straddle configured line sizes
- VS Code diagnostics for padding hotspots and cache-line split fields
- Analyze-on-save workflow for supported source files
- Activity Bar dashboard, status bar command, editor title action, context menu command, and Command Palette command
- Terminal CLI for scripting, CI checks, and non-editor workflows
- Fully local execution with no network services or external analysis APIs

## Version 2.0 Highlights

Struct Scope 2.0 expands the original dashboard workflow into a more complete tool surface:

- Host ABI auto-detection with manual platform override
- Configurable default platform and cache-line size
- Optional automatic dashboard opening after save-triggered analysis
- Activity Bar dashboard with quick actions for analysis, output logs, and JSON export
- Terminal CLI with table and JSON output modes
- Improved webview accessibility labels and clearer UI text
- Additional test coverage for CLI usage, host platform detection, local C analysis, cache-line splits, and server integration

## Requirements

- Visual Studio Code 1.85 or newer
- Python 3.8 or newer
- `pip`
- Node.js and npm for development, testing, or packaging

Install Python dependencies before running the backend or CLI:

```sh
pip install -r python/requirements.txt
```

## VS Code Usage

Open a supported C, C++, header, or Rust source file. Struct Scope can be invoked through any of the following entry points:

- Save the file when `structscope.analyzeOnSave` is enabled
- Select `StructScope: Analyze Struct` from the Command Palette
- Use `Ctrl+Shift+M` on Windows/Linux or `Cmd+Shift+M` on macOS
- Click the Struct Scope status bar item
- Use the editor title action or editor context menu
- Use the Struct Scope Activity Bar dashboard

The dashboard renders the selected structure as a byte map, field table, metrics panel, cache-line ruler, and reorder suggestion panel. The platform selector can be changed manually. The Detect control re-runs host ABI detection and refreshes the layout.

## Terminal Usage

Analyze a source file from the command line:

```sh
python python/cli.py tests/fixtures/v2_local_demo.c --platform x86_64
```

Filter output to a specific struct:

```sh
python python/cli.py tests/fixtures/v2_local_demo.c --platform x86_64 --struct TelemetryPacket
```

Emit JSON for scripts or CI tooling:

```sh
python python/cli.py tests/fixtures/v2_local_demo.c --platform auto --json
```

Example output for the included local C fixture:

```text
TelemetryPacket: total=40B padding=18B (45.0%) optimal=24B savings=16B
CacheSplitDemo: total=68B padding=0B (0.0%) optimal=68B savings=0B
warning: Field value straddles cache line boundary
```

## Configuration

The extension contributes the following settings:

| Setting | Description |
| --- | --- |
| `structscope.pythonPath` | Optional Python executable path for the analysis backend |
| `structscope.defaultPlatform` | Default ABI platform: `auto`, `x86_64`, `arm64`, `arm32`, `avr`, or `riscv32` |
| `structscope.cacheLine` | Cache-line size in bytes: 32, 64, or 128 |
| `structscope.analyzeOnSave` | Runs analysis when supported files are saved |
| `structscope.autoOpenPanel` | Opens the dashboard automatically during save-triggered analysis |
| `structscope.showStatusBar` | Shows or hides the Struct Scope status bar command |

## Supported Inputs

Languages:

- C structs
- C++ structs and classes with data members
- Rust structs

ABI platforms:

- `x86_64`
- `arm64`
- `arm32`
- `avr`
- `riscv32`

The `auto` platform option detects the host ABI. Cross-compilation targets cannot be inferred reliably from source text alone, so embedded and firmware projects should select the intended target ABI explicitly.

## Architecture

Struct Scope is split into a TypeScript VS Code extension and a Python analysis backend.

- The VS Code extension manages commands, diagnostics, status bar state, Activity Bar actions, webview rendering, and the Python child process.
- The Python backend uses tree-sitter grammars to parse source text and extract structure definitions.
- Layout computation is performed with deterministic ABI tables and standard alignment arithmetic.
- Communication between VS Code and Python uses newline-delimited JSON over stdio.
- The webview uses local HTML, CSS, and JavaScript assets only.

No source code is sent to cloud services, telemetry endpoints, model APIs, compiler services, or third-party analysis systems.

## Development

Run the Python test suite:

```sh
pytest tests/ -v
```

Run the server integration script:

```sh
python tests/test_server_integration.py
```

Run TypeScript checks and build the extension bundle:

```sh
npx tsc --noEmit
npx esbuild src/extension.ts --bundle --platform=node --external:vscode --outfile=out/extension.js
```

Package the extension:

```sh
npx @vscode/vsce package
```

Install the generated VSIX:

```sh
code --install-extension struct-scope-2.0.0.vsix
```

## Repository Contents

- `src/extension.ts`: VS Code extension entry point
- `python/server.py`: JSON-RPC analysis server
- `python/cli.py`: command-line interface
- `python/parser_c.py`: C/C++ parser
- `python/parser_rust.py`: Rust parser
- `python/layout_engine.py`: ABI layout engine
- `python/analyser.py`: padding, cache-line, and warning analysis
- `python/platforms.py`: platform ABI tables and host detection
- `webview/`: dashboard UI assets
- `tests/`: parser, layout, analyser, CLI, and integration tests

## License

MIT

