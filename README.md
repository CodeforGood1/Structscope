# StructScope

StructScope is a VS Code extension for inspecting the byte-level memory layout of C, C++, and Rust struct-like types. It parses source locally, computes field offsets, field sizes, padding bytes, total size, cache-line split risks, and field reorder suggestions, then renders the result as an interactive byte map with a field table and summary metrics. It is aimed at systems programmers who want quick feedback on data layout without compiling code, launching a debugger, or sending source to a service.

## Requirements

You need Python 3.8 or newer, `pip`, VS Code 1.85 or newer, and Node.js with npm for development builds.

Install the Python dependencies before using the extension backend:

```sh
pip install -r python/requirements.txt
```

## Installation

Build or download the VSIX package, then install it manually in VS Code:

```sh
code --install-extension structscope-0.1.0.vsix
```

For local development, install npm dependencies and build the extension bundle:

```sh
npm install
npx esbuild src/extension.ts --bundle --platform=node --external:vscode --outfile=out/extension.js
```

The extension starts a local Python JSON-RPC process when VS Code activates it for C, C++, or Rust files. If Python is not available as `python3` or `python`, set `StructScope: Python Path` in VS Code settings to the full Python executable path.

## Usage

Open a C, C++, header, or Rust source file and place the cursor near a struct, class, or Rust struct definition. Then run `StructScope: Analyze Struct` from the Command Palette, or press `Ctrl+Shift+M` on Windows and Linux, or `Cmd+Shift+M` on macOS. StructScope opens a side panel with the selected layout.

The panel shows a colored byte map for each field, striped padding bytes, a cache line ruler, a field table with offsets and sizes, summary metrics, and reorder suggestions when the current field order wastes space.

Changing the platform or cache line dropdown reruns the analysis and updates the panel. Moving the cursor to a different struct while the panel is open refreshes the view after a short debounce.

## What It Checks

StructScope reports byte offsets, field sizes, inter-field padding, trailing padding, total struct size, overall alignment, padding waste ratio, cache-line splits, and greedy reorder suggestions. It also publishes VS Code diagnostics for padding after fields, cache-line split warnings, and high-padding structs.

## Supported Languages and Platforms

Supported languages are C structs, C++ structs and classes with data members, and Rust structs. Supported platforms are `x86_64`, `arm64`, `arm32`, `avr`, and `riscv32`.

The current release focuses on common scalar, pointer, array, nested struct, and Rust primitive cases. Unknown types are preserved in the output and marked unresolved instead of being guessed.

## How It Works

The extension is split into a TypeScript VS Code frontend and a Python analysis backend. The frontend spawns `python/server.py` and communicates over newline-delimited JSON-RPC on stdio. The Python backend uses tree-sitter grammars for C, C++, and Rust, resolves known primitive and pointer sizes from ABI platform tables, computes layout using standard alignment arithmetic, and returns JSON to the webview. The webview renders everything from local HTML, CSS, and JavaScript.

StructScope does not call cloud services, LLM APIs, compiler toolchains, or external analysis servers. Source text stays on the local machine.

## Development

Run the Python tests:

```sh
pytest tests/ -v
```

Run the server integration test:

```sh
python tests/test_server_integration.py
```

Run TypeScript checks and build:

```sh
npx tsc --noEmit
npx esbuild src/extension.ts --bundle --platform=node --external:vscode --outfile=out/extension.js
```

Package the extension:

```sh
npx @vscode/vsce package
```

## Contributing

Keep changes local first and testable. Parser changes should include fixtures and pytest coverage. Layout changes should include explicit expected offsets, padding, and total sizes. Webview changes should preserve VS Code theme variables and avoid external scripts.

## License

MIT

