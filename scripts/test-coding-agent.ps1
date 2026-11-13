# Smoke test for the coding stack, run from a Windows client.
# Checks the vLLM servers behind VS Code Copilot Chat, Continue.dev and
# OpenHands: model and context window, tool calling (plain and streamed),
# fill-in-the-middle autocomplete, embeddings, speed, and OpenHands' settings.
# Must parse on Windows PowerShell 5.1.
#
#   .\scripts\test-coding-agent.ps1
#   .\scripts\test-coding-agent.ps1 -Server 192.168.1.102
#   .\scripts\test-coding-agent.ps1 -LongContext    # also fill ~120k tokens and find a needle
#
# Copilot agent mode streams its requests, OpenHands does not; both paths are
# checked because a tool parser can return structured calls on one and leak
# raw <tool_call> text on the other.

param(
    [string]$Server = "192.168.1.102",
    [int]$Port = 8002,
    [string]$Model = "qwen3.8-27b",
    [int]$MinContext = 262144,
    [int]$EmbedPort = 8003,
    [string]$EmbedModel = "nomic-embed-text",
    [int]$StreamTrials = 3,
    [int]$OpenHandsPort = 3003,
    [switch]$LongContext,
    [int]$LongContextTokens = 120000
)

$ErrorActionPreference = "Stop"
$api = "http://${Server}:$Port/v1"
$embedApi = "http://${Server}:$EmbedPort/v1"
$openhands = "http://${Server}:$OpenHandsPort"
$failures = 0

function Pass($msg) { Write-Host "  PASS  $msg" -ForegroundColor Green }
function Fail($msg) { Write-Host "  FAIL  $msg" -ForegroundColor Red; $script:failures++ }

# POST JSON as UTF-8 (PowerShell 5.1 would send the string as Latin-1).
function Post($url, $obj, $timeout = 300) {
    $json = $obj | ConvertTo-Json -Depth 12
    Invoke-RestMethod $url -Method Post -ContentType "application/json; charset=utf-8" `
        -Body ([Text.Encoding]::UTF8.GetBytes($json)) -TimeoutSec $timeout
}

# Thinking off: the checks below want the answer, not the reasoning trace.
$noThink = @{ enable_thinking = $false }

Write-Host "Coding stack smoke test against $Server"

# 1. Model server up, right model, full window
try {
    $models = Invoke-RestMethod "$api/models" -TimeoutSec 10
    $m = $models.data | Where-Object { $_.id -eq $Model }
    if (-not $m) {
        Fail "$Model not served at $api (serving: $(($models.data | ForEach-Object { $_.id }) -join ', '))"
    } elseif ($m.max_model_len -lt $MinContext) {
        Fail "$Model max_model_len $($m.max_model_len), expected at least $MinContext"
    } else {
        Pass "$Model served at $api (max_model_len $($m.max_model_len))"
    }
} catch {
    Fail "vLLM not reachable at ${api}: $($_.Exception.Message)"
    Write-Host "The model server is down; skipping the remaining checks."
    exit 1
}

# 2. Tool calling through chat completions, non-streamed (OpenHands' path).
# Thinking stays on here, as in a real agent turn.
$tools = @(@{
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
try {
    $sw = [Diagnostics.Stopwatch]::StartNew()
    $r = Post "$api/chat/completions" @{
        model    = $Model
        messages = @(@{ role = "user"; content = "List the files in /tmp using the tool." })
        tools    = $tools
    }
    $sw.Stop()
    $call = $r.choices[0].message.tool_calls
    if ($call -and $call[0].function.name -eq "execute_bash") {
        Pass ("tool call returned in {0:N1}s: {1}" -f $sw.Elapsed.TotalSeconds, $call[0].function.arguments)
    } else {
        Fail "answered without a tool call (finish_reason: $($r.choices[0].finish_reason)): $($r.choices[0].message.content)"
    }
} catch {
    Fail "tool-call request failed: $($_.Exception.Message)"
}

# 3. Streamed tool calling, the way Copilot agent mode calls the model.
# A preamble sentence before the call is what tends to leak raw call text.
$streamBody = @{
    model    = $Model
    stream   = $true
    messages = @(@{ role = "user"; content = "First say in one sentence what you will do, then list the files in /tmp using the tool." })
    tools    = $tools
} | ConvertTo-Json -Depth 12
$streamOk = 0
for ($i = 1; $i -le $StreamTrials; $i++) {
    try {
        $raw = (Invoke-WebRequest "$api/chat/completions" -Method Post -ContentType "application/json; charset=utf-8" `
            -Body ([Text.Encoding]::UTF8.GetBytes($streamBody)) -TimeoutSec 300 -UseBasicParsing).Content
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
        else { Write-Host "    stream trial ${i}: tool_calls=$hasCall content=$($text.Substring(0, [Math]::Min(120, $text.Length)))" }
    } catch {
        Write-Host "    stream trial $i failed: $($_.Exception.Message)"
    }
}
if ($streamOk -eq $StreamTrials) {
    Pass "streamed tool calls: $streamOk/$StreamTrials structured"
} else {
    Fail "streamed tool calls: only $streamOk/$StreamTrials structured (Copilot agent mode would show raw call text)"
}

# 4. Fill-in-the-middle through /v1/completions (Continue tab autocomplete)
try {
    $fim = "<|fim_prefix|>def add(a, b):`n    <|fim_suffix|>`n`n`nprint(add(2, 3))`n<|fim_middle|>"
    $sw = [Diagnostics.Stopwatch]::StartNew()
    $r = Post "$api/completions" @{ model = $Model; prompt = $fim; max_tokens = 32; temperature = 0
                                    stop = @("<|endoftext|>", "<|fim_pad|>", "<|file_sep|>", "<|im_end|>") }
    $sw.Stop()
    $txt = $r.choices[0].text
    if ($txt -match "return\s+a\s*\+\s*b") {
        Pass ("FIM autocomplete in {0:N2}s: {1}" -f $sw.Elapsed.TotalSeconds, $txt.Trim())
    } else {
        Fail "FIM autocomplete returned: $txt"
    }
} catch {
    Fail "FIM request failed: $($_.Exception.Message)"
}

# 5. Embeddings (Continue codebase search, Open WebUI RAG)
try {
    $e = Post "$embedApi/embeddings" @{ model = $EmbedModel; input = @("search_query: reverse a string") } 60
    $dim = $e.data[0].embedding.Count
    if ($dim -eq 768) { Pass "embeddings from $EmbedModel ($dim dims)" } else { Fail "embeddings from $EmbedModel have $dim dims, expected 768" }
} catch {
    Fail "embeddings at $embedApi failed: $($_.Exception.Message)"
}

# 6. Generation speed (wall clock, so it includes time to first token)
try {
    $sw = [Diagnostics.Stopwatch]::StartNew()
    $g = Post "$api/chat/completions" @{
        model = $Model; max_tokens = 256; chat_template_kwargs = $noThink
        messages = @(@{ role = "user"; content = "Write a Python function that reverses a string, with a docstring and three doctests." })
    }
    $sw.Stop()
    $tps = $g.usage.completion_tokens / $sw.Elapsed.TotalSeconds
    if ($tps -ge 15) { Pass ("generation {0:N0} tok/s ({1} tokens)" -f $tps, $g.usage.completion_tokens) }
    else { Fail ("generation {0:N0} tok/s ({1} tokens)" -f $tps, $g.usage.completion_tokens) }
} catch {
    Fail "generation request failed: $($_.Exception.Message)"
}

# 7. OpenHands up and pointed at vLLM
try {
    Invoke-RestMethod "$openhands/health" -TimeoutSec 10 | Out-Null
    Pass "OpenHands reachable at $openhands"
    $s = Invoke-RestMethod "$openhands/api/settings" -TimeoutSec 10
    if ($s.llm_model -eq "openai/$Model" -and $s.llm_base_url -like "*vllm-4gpu:8000*") {
        Pass "OpenHands uses $($s.llm_model) via $($s.llm_base_url)"
    } else {
        Fail "OpenHands LLM settings: model=$($s.llm_model) base_url=$($s.llm_base_url) (run scripts/deploy-phase11.sh on the host)"
    }
} catch {
    Fail "OpenHands check failed: $($_.Exception.Message)"
}

# 8. Long context: bury a needle 40% into ~LongContextTokens of code and ask for it.
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
    try {
        $sw = [Diagnostics.Stopwatch]::StartNew()
        $r = Post "$api/chat/completions" @{
            model = $Model; max_tokens = 32; temperature = 0; chat_template_kwargs = $noThink
            messages = @(
                @{ role = "system"; content = "You are a code assistant. Answer with the value only." },
                @{ role = "user"; content = $sb.ToString() + "`nWhat string is DEPLOY_TOKEN set to in the code above?" }
            )
        } 900
        $sw.Stop()
        $n = $r.usage.prompt_tokens
        $info = "{0} prompt tokens in {1:N0}s ({2:N0} tok/s incl. decode)" -f $n, $sw.Elapsed.TotalSeconds, ($n / $sw.Elapsed.TotalSeconds)
        if ($n -lt $LongContextTokens * 0.8) {
            Fail "long context smaller than asked: $info"
        } elseif ($r.choices[0].message.content -match "amber-7731-kestrel") {
            Pass "long context needle found: $info"
        } else {
            Fail "long context needle missed ($info): $($r.choices[0].message.content)"
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
