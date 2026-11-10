# Smoke test for the coding agent stack, run from a Windows client.
# Checks Ollama, the coding models, tool calling, and OpenHands.
# Must parse on Windows PowerShell 5.1.
#
#   .\scripts\test-coding-agent.ps1
#   .\scripts\test-coding-agent.ps1 -Server 192.168.1.102 -Model qwen3-coder:30b-128k
#   .\scripts\test-coding-agent.ps1 -LongContext    # also fill ~100k tokens and find a needle
#
# -Model is the OpenHands model (non-streaming requests). -CopilotModel is the
# model selected in VS Code Copilot agent mode, which streams its requests;
# qwen3-coder intermittently leaks its tool calls as text when streamed.
# qwen3-coder:30b-128k is qwen3-coder:30b with num_ctx 131072 baked in
# (scripts/create-ollama-variants.sh), so clients that send no num_ctx,
# like OpenHands over /v1, still get the full window.

param(
    [string]$Server = "192.168.1.102",
    [string]$Model = "qwen3-coder:30b-128k",
    [int]$MinContext = 131072,
    [string]$CopilotModel = "gpt-oss:20b",
    [int]$StreamTrials = 3,
    [string[]]$RequiredModels = @("qwen3-coder:30b", "qwen3-coder:30b-128k", "gpt-oss:20b", "qwen2.5-coder:7b", "devstral:latest", "nomic-embed-text:latest"),
    [int]$OpenHandsPort = 3003,
    [switch]$LongContext,
    [int]$LongContextTokens = 100000
)

$ErrorActionPreference = "Stop"
$ollama = "http://${Server}:11434"
$openhands = "http://${Server}:$OpenHandsPort"
$failures = 0

function Pass($msg) { Write-Host "  PASS  $msg" -ForegroundColor Green }
function Fail($msg) { Write-Host "  FAIL  $msg" -ForegroundColor Red; $script:failures++ }

Write-Host "Coding agent smoke test against $Server"

# 1. Ollama reachable
try {
    $v = Invoke-RestMethod "$ollama/api/version" -TimeoutSec 10
    Pass "Ollama reachable (version $($v.version))"
} catch {
    Fail "Ollama not reachable at ${ollama}: $($_.Exception.Message)"
    Write-Host "Ollama is down; skipping the remaining checks."
    exit 1
}

# 2. Required models pulled
$tags = (Invoke-RestMethod "$ollama/api/tags" -TimeoutSec 10).models | ForEach-Object { $_.name }
foreach ($m in $RequiredModels) {
    if ($tags -contains $m) { Pass "model present: $m" } else { Fail "model missing: $m (docker exec ollama ollama pull $m)" }
}

# 3. Tool calling through the OpenAI-compatible endpoint (what OpenHands uses)
$body = @{
    model    = $Model
    messages = @(@{ role = "user"; content = "List the files in /tmp using the tool." })
    tools    = @(@{
        type     = "function"
        function = @{
            name        = "execute_bash"
            description = "Run a bash command"
            parameters  = @{
                type       = "object"
                properties = @{ command = @{ type = "string" } }
                required   = @("command")
            }
        }
    })
} | ConvertTo-Json -Depth 10
try {
    $sw = [Diagnostics.Stopwatch]::StartNew()
    $r = Invoke-RestMethod "$ollama/v1/chat/completions" -Method Post -ContentType "application/json" -Body $body -TimeoutSec 300
    $sw.Stop()
    $call = $r.choices[0].message.tool_calls
    if ($call -and $call[0].function.name -eq "execute_bash") {
        Pass ("tool call returned by {0} in {1:N1}s: {2}" -f $Model, $sw.Elapsed.TotalSeconds, $call[0].function.arguments)
    } else {
        Fail "$Model answered without a tool call (finish_reason: $($r.choices[0].finish_reason))"
    }
} catch {
    Fail "tool-call request failed: $($_.Exception.Message)"
}

# 3b. Streamed tool calling, the way Copilot agent mode calls the model.
# A preamble sentence before the call is what triggers leaked <function=...> text.
$streamBody = @{
    model    = $CopilotModel
    stream   = $true
    messages = @(@{ role = "user"; content = "First say in one sentence what you will do, then list the files in /tmp using the tool." })
    tools    = ($body | ConvertFrom-Json).tools
} | ConvertTo-Json -Depth 10
$streamOk = 0
for ($i = 1; $i -le $StreamTrials; $i++) {
    try {
        $raw = (Invoke-WebRequest "$ollama/v1/chat/completions" -Method Post -ContentType "application/json" -Body $streamBody -TimeoutSec 300 -UseBasicParsing).Content
        $hasCall = $false
        $text = ""
        foreach ($line in ($raw -split "`n")) {
            $line = $line.Trim()
            if (-not $line.StartsWith("data:") -or $line -eq "data: [DONE]") { continue }
            $delta = ($line.Substring(5) | ConvertFrom-Json).choices[0].delta
            if ($delta.tool_calls) { $hasCall = $true }
            if ($delta.content) { $text += $delta.content }
        }
        if ($hasCall -and $text -notmatch "<function=|<tool_call>") { $streamOk++ }
    } catch {
        Write-Host "    stream trial $i failed: $($_.Exception.Message)"
    }
}
if ($streamOk -eq $StreamTrials) {
    Pass "streamed tool calls from ${CopilotModel}: $streamOk/$StreamTrials structured"
} else {
    Fail "streamed tool calls from ${CopilotModel}: only $streamOk/$StreamTrials structured (Copilot agent mode will show raw <function=...> text)"
}

# 4. Generation speed
try {
    $gen = @{ model = $Model; prompt = "Write a Python function that reverses a string."; stream = $false; options = @{ num_predict = 128 } } | ConvertTo-Json
    $g = Invoke-RestMethod "$ollama/api/generate" -Method Post -ContentType "application/json" -Body $gen -TimeoutSec 300
    $tps = $g.eval_count / ($g.eval_duration / 1e9)
    if ($tps -ge 20) { Pass ("generation speed {0:N0} tok/s" -f $tps) } else { Fail ("generation speed {0:N0} tok/s (model may be spilling to CPU)" -f $tps) }
} catch {
    Fail "generate request failed: $($_.Exception.Message)"
}

# 5. Model fully in VRAM
$ps = (Invoke-RestMethod "$ollama/api/ps" -TimeoutSec 10).models | Where-Object { $_.name -eq $Model }
if ($ps -and $ps.size_vram -ge $ps.size) {
    Pass ("{0} fully on GPU ({1:N1} GB, ctx {2})" -f $Model, ($ps.size_vram / 1GB), $ps.context_length)
    if ($ps.context_length -lt $MinContext) {
        Fail ("{0} loaded with ctx {1}, expected at least {2} (a client sent a smaller num_ctx)" -f $Model, $ps.context_length, $MinContext)
    }
} elseif ($ps) {
    Fail ("{0} partly on CPU: {1:N1} of {2:N1} GB in VRAM" -f $Model, ($ps.size_vram / 1GB), ($ps.size / 1GB))
} else {
    Fail "$Model is not loaded after the requests above"
}

# 6. OpenHands up and pointed at Ollama
try {
    Invoke-RestMethod "$openhands/health" -TimeoutSec 10 | Out-Null
    Pass "OpenHands reachable at $openhands"
    $s = Invoke-RestMethod "$openhands/api/settings" -TimeoutSec 10
    if ($s.llm_model -eq "openai/$Model" -and $s.llm_base_url -like "*ollama:11434*") {
        Pass "OpenHands uses $($s.llm_model) via $($s.llm_base_url)"
    } else {
        Fail "OpenHands LLM settings: model=$($s.llm_model) base_url=$($s.llm_base_url)"
    }
} catch {
    Fail "OpenHands check failed: $($_.Exception.Message)"
}

# 7. Long context: bury a needle 40% into ~LongContextTokens of code and ask for it.
# Sends no num_ctx, like OpenHands, so it exercises the tag's own window.
if ($LongContext) {
    $blocks = [int]($LongContextTokens / 45)
    $sb = New-Object System.Text.StringBuilder
    for ($i = 0; $i -lt $blocks; $i++) {
        if ($i -eq [int]($blocks * 0.4)) { [void]$sb.AppendLine("DEPLOY_TOKEN = 'amber-7731-kestrel'  # read by release.py") }
        [void]$sb.AppendLine("def handler_$i(request, retries=$($i % 7)):")
        [void]$sb.AppendLine("    value = request.get('field_$i', $i)")
        [void]$sb.AppendLine("    return {'id': $i, 'value': value * $($i % 13), 'ok': True}")
        [void]$sb.AppendLine("")
    }
    $lc = @{
        model    = $Model
        stream   = $false
        messages = @(
            @{ role = "system"; content = "You are a code assistant. Answer with the value only." },
            @{ role = "user"; content = $sb.ToString() + "`nWhat string is DEPLOY_TOKEN set to in the code above?" }
        )
        options  = @{ num_predict = 32; temperature = 0 }
    } | ConvertTo-Json -Depth 5
    try {
        $r = Invoke-RestMethod "$ollama/api/chat" -Method Post -ContentType "application/json; charset=utf-8" -Body ([Text.Encoding]::UTF8.GetBytes($lc)) -TimeoutSec 900
        $secs = $r.prompt_eval_duration / 1e9
        $info = "{0} prompt tokens, prefill {1:N0} tok/s ({2:N0}s)" -f $r.prompt_eval_count, ($r.prompt_eval_count / $secs), $secs
        if ($r.prompt_eval_count -lt $LongContextTokens * 0.8) {
            Fail "long context truncated: only $info"
        } elseif ($r.message.content -match "amber-7731-kestrel") {
            Pass "long context needle found: $info"
        } else {
            Fail "long context needle missed ($info): $($r.message.content)"
        }
    } catch {
        Fail "long context request failed: $($_.Exception.Message)"
    }
}

Write-Host ""
if ($failures -eq 0) {
    Write-Host "All checks passed." -ForegroundColor Green
    exit 0
}
Write-Host "$failures check(s) failed." -ForegroundColor Red
exit 1
