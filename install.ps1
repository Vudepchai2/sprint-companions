# Sprint companions installer for Windows (PowerShell).
#
#   irm https://raw.githubusercontent.com/Vudepchai2/sprint-companions/main/install.ps1 | iex
#
# It checks what you need, installs the plugin into Claude Code, installs the companions engine,
# and (after asking) adds three permission rules so the companions don't ask every time.
# It is safe to run again: every step skips itself when it's already done.
# To answer yes to every question, first run:  $env:SPRINT_COMPANIONS_YES = '1'
#
# It runs inside your own PowerShell window (irm | iex), so it never calls exit: a failed step
# stops the installer with a message and leaves the window open.

& {
# Continue, not Stop: in Windows PowerShell 5.1, Stop turns any stderr line from a native command
# (claude, uv, the engine's install progress) into an error. Every step checks its own result.
$ErrorActionPreference = 'Continue'
$Repo = 'Vudepchai2/sprint-companions'
$Plugin = 'sprint-companions@sprint-companions'
$Yes = ($env:SPRINT_COMPANIONS_YES -eq '1')

function Write-Step([string]$Text) { Write-Host ''; Write-Host $Text -ForegroundColor White }
function Write-Ok([string]$Text) { Write-Host '  ' -NoNewline; Write-Host 'OK' -ForegroundColor Green -NoNewline; Write-Host " $Text" }
function Write-Info([string]$Text) { Write-Host "  $Text" }
function Stop-Install([string[]]$Lines) { throw [System.OperationCanceledException]::new(($Lines -join "`n")) }
function Read-YesNo([string]$Question) {
    if ($Yes) { Write-Host "  $Question [Y/n] y"; return $true }
    $answer = Read-Host "  $Question [Y/n]"
    return ($answer -eq '' -or $answer -match '^(y|yes)$')
}
function Update-SessionPath {
    $machine = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $user = [Environment]::GetEnvironmentVariable('Path', 'User')
    $env:Path = "$HOME\.local\bin;$machine;$user"
}
function Test-Command([string]$Name) { return [bool](Get-Command $Name -ErrorAction SilentlyContinue) }

try {
    Write-Host 'Sprint companions installer' -ForegroundColor White
    Write-Info 'TT, KS, MM and MR: four AI companions for your demo-day story, inside Claude Code.'

    Write-Step '1/5  Claude Code'
    Update-SessionPath
    if (-not (Test-Command 'claude')) {
        Stop-Install @("Claude Code isn't installed (no 'claude' command found).",
            'Install it from https://claude.com/claude-code, open it once, then run this installer again.')
    }
    $claudeVersion = & claude --version
    Write-Ok ("found " + (@($claudeVersion) | Select-Object -First 1))

    Write-Step '2/5  Git for Windows (Claude Code and the companions need its bash)'
    if (-not (Test-Command 'git')) {
        Write-Info 'Git for Windows is missing. It installs with winget, from the official Git package.'
        if (-not (Read-YesNo 'Install Git for Windows now?')) {
            Stop-Install @('Git for Windows is needed.', 'Install it from https://git-scm.com/download/win, then run this installer again.')
        }
        & winget install --id Git.Git -e --source winget --accept-package-agreements --accept-source-agreements
        Update-SessionPath
        if (-not (Test-Command 'git')) { Stop-Install @('Git installed, but this window can''t find it yet.', 'Open a new PowerShell window and run this installer again.') }
    }
    $gitExe = (Get-Command git).Source
    $gitRoot = Split-Path (Split-Path $gitExe -Parent) -Parent
    $bash = Join-Path $gitRoot 'bin\bash.exe'
    if (-not (Test-Path $bash)) { $bash = 'C:\Program Files\Git\bin\bash.exe' }
    if (-not (Test-Path $bash)) {
        Stop-Install @("Git is installed, but Git Bash (bash.exe) wasn't found next to it.",
            'Install Git for Windows from https://git-scm.com/download/win, then run this installer again.')
    }
    Write-Ok ("found " + (& git --version))

    Write-Step '3/5  uv (installs the companions engine and its Python)'
    if (Test-Command 'uv') {
        Write-Ok ("found " + (& uv --version))
    } else {
        Write-Info 'uv is a small installer for Python tools from astral.sh. It needs no admin rights.'
        if (-not (Read-YesNo 'Install uv now?')) {
            Stop-Install @('uv is needed.', 'Install it yourself with: powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"', 'Then run this installer again.')
        }
        & powershell -NoProfile -ExecutionPolicy ByPass -Command 'irm https://astral.sh/uv/install.ps1 | iex'
        Update-SessionPath
        if (-not (Test-Command 'uv')) { Stop-Install @('uv installed, but this window can''t find it yet.', 'Open a new PowerShell window and run this installer again.') }
        Write-Ok ("installed " + (& uv --version))
    }

    Write-Step '4/5  The plugin'
    $marketplaces = (& claude plugin marketplace list 2>$null) -join "`n"
    if ($marketplaces -match 'sprint-companions') {
        & claude plugin marketplace update sprint-companions *> $null
        Write-Ok 'marketplace already added (refreshed)'
    } else {
        & claude plugin marketplace add $Repo
        if ($LASTEXITCODE -ne 0) { Stop-Install @("Couldn't add the marketplace.", 'Check your internet connection and try again.') }
        Write-Ok 'marketplace added'
    }
    $installed = (& claude plugin list --json 2>$null) -join "`n" | ConvertFrom-Json
    $entry = @($installed) | Where-Object { $_.id -eq $Plugin } | Select-Object -First 1
    if ($entry) {
        & claude plugin update $Plugin *> $null
        & claude plugin enable $Plugin *> $null
        Write-Ok 'plugin already installed (updated)'
    } else {
        & claude plugin install $Plugin --scope user
        if ($LASTEXITCODE -ne 0) { Stop-Install @("Couldn't install the plugin.", "Try again, or in Claude Code type: /plugin install $Plugin") }
        Write-Ok 'plugin installed'
    }
    $installed = (& claude plugin list --json 2>$null) -join "`n" | ConvertFrom-Json
    $entry = @($installed) | Where-Object { $_.id -eq $Plugin } | Select-Object -First 1
    if (-not $entry -or -not $entry.installPath) {
        Stop-Install @('The plugin is installed, but I couldn''t find its folder.', 'Start Claude Code: the engine installs itself at the first companion call.')
    }

    Write-Info 'Installing the companions engine (once; this can take a minute)...'
    $launcher = (Join-Path $entry.installPath 'bin\companions') -replace '\\', '/'
    # Capture all output first: Select-Object -First on a live pipeline would stop the install early.
    $engineOut = & $bash $launcher version 2>$null
    $engineCode = $LASTEXITCODE
    $engineVersion = @($engineOut) | Select-Object -First 1
    if ($engineCode -ne 0 -or -not $engineVersion) {
        Stop-Install @("The engine didn't install.", 'Check your internet connection, then run this installer again.')
    }
    Write-Ok "engine ready: $engineVersion"

    Write-Step '5/5  Fewer permission prompts'
    $configDir = if ($env:CLAUDE_CONFIG_DIR) { $env:CLAUDE_CONFIG_DIR } else { Join-Path $HOME '.claude' }
    $settings = Join-Path $configDir 'settings.json'
    $memRule = if ($env:COMPANIONS_HOME) { "Edit($($env:COMPANIONS_HOME -replace '\\', '/')/**)" } else { 'Edit(~/SprintCompanions/**)' }
    Write-Info 'Without these, Claude Code asks before each companion command. The rules let it:'
    Write-Info '  Skill(sprint-companions:*)   call a companion when you ask for one'
    Write-Info '  Bash(companions *)           run the companions engine'
    Write-Info "  $memRule   save to your memory folder, and nowhere else"
    Write-Info "They go into $settings. The companions still ask in the chat before deleting anything."
    if (Read-YesNo 'Add these three rules?') {
        New-Item -ItemType Directory -Force -Path $configDir | Out-Null
        $merge = @'
import json, os, sys
path, rules = sys.argv[1], sys.argv[2:]
data = {}
if os.path.exists(path):
    try:
        with open(path, encoding="utf-8-sig") as f:
            text = f.read()
        data = json.loads(text) if text.strip() else {}
    except ValueError:
        print("unreadable"); sys.exit(0)
if not isinstance(data, dict):
    print("unreadable"); sys.exit(0)
perms = data.setdefault("permissions", {})
if not isinstance(perms, dict):
    print("unreadable"); sys.exit(0)
allow = perms.setdefault("allow", [])
if not isinstance(allow, list):
    print("unreadable"); sys.exit(0)
added = [r for r in rules if r not in allow]
allow.extend(added)
if added:
    tmp = path + ".sprint-companions.tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)
print(len(added))
'@
        $script = Join-Path ([System.IO.Path]::GetTempPath()) 'sprint-companions-rules.py'
        [System.IO.File]::WriteAllText($script, $merge, [System.Text.UTF8Encoding]::new($false))
        $mergeOut = & uv run --no-project --quiet --python 3.12 python $script $settings 'Skill(sprint-companions:*)' 'Bash(companions *)' $memRule
        $mergeCode = $LASTEXITCODE
        $result = @($mergeOut) | Select-Object -Last 1
        Remove-Item $script -ErrorAction SilentlyContinue
        if ($mergeCode -ne 0 -or $result -eq 'unreadable' -or -not $result) {
            Write-Info 'Your settings file couldn''t be read as JSON, so I left it alone.'
            Write-Info 'Add the rules yourself in Claude Code: type /permissions, choose Allow, and add them.'
        } elseif ($result -eq '0') {
            Write-Ok 'rules already there'
        } else {
            Write-Ok "added $result rule(s)"
        }
    } else {
        Write-Info 'Skipped. You can add them later in Claude Code: /permissions, then Allow.'
    }

    Write-Host ''
    Write-Host 'Sprint companions is ready.' -ForegroundColor Green
    Write-Info 'Open Claude Code in your startup''s folder and type:  /tt'
}
catch [System.OperationCanceledException] {
    Write-Host ''
    Write-Host '  Stopped: ' -ForegroundColor Red -NoNewline
    Write-Host $_.Exception.Message
}
}
