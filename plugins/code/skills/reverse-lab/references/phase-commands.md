# reverse-lab phase commands

Run from lab root. Replace angle-bracket placeholders.

## Bootstrap

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File lab\start-pipeline.ps1
```

Frida missing:

```powershell
pip install frida-tools==14.10.4
frida --version
```

mitmproxy from this tree:

```powershell
uv run --directory mitmproxy-main mitmdump --version
```

Refresh tools only:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File reverse-skill-main\skills\scripts\refresh-tool-index.ps1
```

## Identify + route + case

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File lab\identify-runtime.ps1 -Sample "C:\path\to\sample.exe"

powershell -NoProfile -ExecutionPolicy Bypass -File lab\route.ps1 -Hint "offline golang binary reverse pclntab"

powershell -NoProfile -ExecutionPolicy Bypass -File reverse-skill-main\skills\scripts\case-init.ps1 `
  -Hint "offline golang binary reverse pclntab" `
  -CaseName "sample-go" `
  -ProjectRoot "D:\\Projects\\Reverse-Engineer" `
  -Preset offline-sample `
  -Sample "C:\path\to\sample.exe"

powershell -NoProfile -ExecutionPolicy Bypass -File reverse-skill-main\skills\scripts\case-guard.ps1 -CaseRoot "work\sample-go"
```

## Capture

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File lab\start-pipeline.ps1 -Capture -ProxyPort 8080
# target proxy 127.0.0.1:8080
powershell -NoProfile -ExecutionPolicy Bypass -File lab\stop-pipeline.ps1
```

## Frida

```powershell
frida-ps
frida -n "sample.exe" -l lab\hooks\trace-exports.js
```

## Review

```powershell
python reverse-skill-main\skills\case-review\scripts\review_case.py work\sample-go --verify-hashes --strict
```

## PRIMARY cheat sheet

| Hint keywords | PRIMARY |
|---------------|---------|
| apk, jadx, smali | `apk-reverse/` |
| golang, rustc, pclntab, go.buildid | `go-rust-reverse/` + `skill co rack.md` |
| dnSpy, ConfuserEx, .NET | `dotnet-reverse/` |
| thick client, electron | `thick-client/` |
| ghidra | `ghidra-reverse/` |
| ida | `ida-reverse/` |
| default binary | `reverse-engineering/` |
