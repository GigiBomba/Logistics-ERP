@echo off
rem Operion site origin ? serves dist/client on 127.0.0.1:8080 (tunnel ingress target). Auto-restarts on exit.
:loop
"C:\Program Files\nodejs\node.exe" "C:\Users\Bonjo\source\repos\operion-website\scripts\serve-site.mjs"
timeout /t 5 /nobreak >nul
goto loop
