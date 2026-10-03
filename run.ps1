param([ValidateSet('serve','demo','test')][string]$Action = 'serve')
$ErrorActionPreference = 'Stop'
$taskPython = Get-Command python -ErrorAction SilentlyContinue
if ($taskPython) { $taskExecutable = $taskPython.Source } else {
    $taskExecutable = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
    if (-not (Test-Path -LiteralPath $taskExecutable)) { throw 'Python 3.10+ is required.' }
}
Push-Location $PSScriptRoot
try {
    switch ($Action) {
        'serve' { & $taskExecutable server.py }
        'demo' { & $taskExecutable demo.py }
        'test' { & $taskExecutable -m unittest discover -s tests -v }
    }
    $taskExit = $LASTEXITCODE
} finally { Pop-Location }
exit $taskExit
