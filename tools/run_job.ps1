param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('premarket', 'close', 'watch')]
    [string]$Job
)

$ErrorActionPreference = 'Continue'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
$env:MY_BASE = 'D:\明远阁'

$py = 'D:\明远阁\.venv\Scripts\python.exe'
$log = 'D:\明远阁\reports\_job.log'
$stamp = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')

function Log([string]$msg) {
    "[$stamp] $msg" | Out-File -FilePath $log -Append -Encoding utf8
}

try {
    Log "=== 开始 $Job ==="

    switch ($Job) {
        'premarket' {
            & $py 'D:\明远阁\tools\premarket.py' *>> $log
            Log "premarket.py exit=$LASTEXITCODE"
            & $py 'D:\明远阁\tools\mail_report.py' --subject '明远阁 | 盘前简报' *>> $log
            Log "mail exit=$LASTEXITCODE"
        }
        'close' {
            & $py 'D:\明远阁\tools\daily_report.py' *>> $log
            Log "daily_report.py exit=$LASTEXITCODE"
            & $py 'D:\明远阁\tools\mail_report.py' --subject '明远阁 | 收盘总结' *>> $log
            Log "mail exit=$LASTEXITCODE"
        }
        'watch' {
            & $py 'D:\明远阁\tools\watch_check.py' --mail *>> $log
            Log "watch_check.py exit=$LASTEXITCODE"
        }
    }
    Log "=== 结束 $Job ==="
}
catch {
    Log "ERROR: $($_.Exception.Message)"
    exit 1
}
