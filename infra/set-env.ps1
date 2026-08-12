# Injects the Terraform credentials into the current shell session.
#
#   CIVO_TOKEN            Civo API key
#   AWS_ACCESS_KEY_ID     Civo Object Store access key (S3-compatible backend)
#   AWS_SECRET_ACCESS_KEY Civo Object Store secret key
#
# Usage (dot-source so the variables persist):
#   . .\infra\set-env.ps1
#   terraform plan
#
# Or pass values inline:
#   . .\infra\set-env.ps1 -CivoToken $env:CIVO_TOKEN -AccessKey $env:AWS_ACCESS_KEY_ID -SecretKey $env:AWS_SECRET_ACCESS_KEY

param(
    [string]$CivoToken,
    [string]$AccessKey,
    [string]$SecretKey
)

function Read-Secret([string]$Prompt) {
    Write-Host -NoNewline $Prompt
    $secret = Read-Host -AsSecureString
    [System.Net.NetworkCredential]::new("", $secret).Password
}

function Read-DotEnv {
    $envFile = Join-Path $PSScriptRoot "..\.env"
    $result = @{}
    if (-not (Test-Path $envFile)) { return $result }
    Get-Content $envFile | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith("#")) {
            $match = [regex]::Match($line, "^([^=]+)=(.*)$")
            if ($match.Success) {
                $result[$match.Groups[1].Value.Trim()] = $match.Groups[2].Value.Trim().Trim('"')
            }
        }
    }
    return $result
}

$dotEnv = Read-DotEnv

if (-not $CivoToken)   { $CivoToken   = $env:CIVO_TOKEN }
if (-not $AccessKey)   { $AccessKey   = $env:AWS_ACCESS_KEY_ID }
if (-not $SecretKey)   { $SecretKey   = $env:AWS_SECRET_ACCESS_KEY }

if (-not $CivoToken)   { $CivoToken   = $dotEnv["CIVO_TOKEN"] }
if (-not $AccessKey)   { $AccessKey   = $dotEnv["AWS_ACCESS_KEY_ID"] }
if (-not $SecretKey)   { $SecretKey   = $dotEnv["AWS_SECRET_ACCESS_KEY"] }

if (-not $CivoToken)   { $CivoToken   = Read-Secret "CIVO_TOKEN: " }
if (-not $AccessKey)   { $AccessKey   = Read-Secret "AWS_ACCESS_KEY_ID: " }
if (-not $SecretKey)   { $SecretKey   = Read-Secret "AWS_SECRET_ACCESS_KEY: " }

$env:CIVO_TOKEN            = $CivoToken
$env:AWS_ACCESS_KEY_ID     = $AccessKey
$env:AWS_SECRET_ACCESS_KEY = $SecretKey

Write-Host "Injected CIVO_TOKEN, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY into the current shell." -ForegroundColor Green
