param(
    [string]$Token = "",
    [ValidateSet("api", "full")]
    [string]$Mode = "full",
    [switch]$AllowInsecureTlsFallback,
    [switch]$AllowInsecurePublicUrlProbe,
    [switch]$VerboseOutput
)

$ErrorActionPreference = "Stop"

if (-not $Token -and $env:TUNNELLIO_API_TOKEN) {
    $Token = $env:TUNNELLIO_API_TOKEN
}

if (-not $Token) {
    throw "Pass -Token or set TUNNELLIO_API_TOKEN"
}

$argsList = @(
    "local_e2e_tests.py",
    "--token", $Token,
    "--mode", $Mode
)

if ($AllowInsecureTlsFallback) {
    $argsList += "--allow-insecure-tls-fallback"
}

if ($AllowInsecurePublicUrlProbe) {
    $argsList += "--allow-insecure-public-url-probe"
}

if ($VerboseOutput) {
    $argsList += "--verbose"
}

python @argsList
