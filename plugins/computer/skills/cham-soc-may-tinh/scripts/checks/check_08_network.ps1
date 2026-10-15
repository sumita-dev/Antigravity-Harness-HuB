# Micro-check 08: DNS Latency
$ping = Test-Connection -ComputerName 1.1.1.1 -Count 1 -ErrorAction SilentlyContinue
$rtt = if ($ping) { $ping.ResponseTime } else { 999 }
[PSCustomObject]@{
    Domain     = "Network_DNS"
    DnsServer  = "1.1.1.1"
    LatencyMs  = $rtt
    Status     = if ($rtt -le 60) { "EXCELLENT" } else { "HIGH_LATENCY" }
}
