# Micro-check 10: Security & Bootloader
$testsigning = bcdedit /enum "{current}" 2>$null | Select-String "testsigning"
$consumers = (Get-CimInstance -Namespace root\subscription -ClassName __EventConsumer -ErrorAction SilentlyContinue).Count
[PSCustomObject]@{
    Domain          = "Security_Boot_WMI"
    TestSigningOn   = ($testsigning -ne $null)
    WmiConsumers    = $consumers
    Status          = if ($testsigning) { "SECURITY_RISK" } else { "PROTECTED" }
}
