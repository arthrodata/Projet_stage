Set-Location -Path "$PSScriptRoot\Frontend"
python -m http.server 8081 --bind 127.0.0.1
