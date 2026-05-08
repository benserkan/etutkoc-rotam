@echo off
REM LGS Takip — yerel geliştirme sunucusunu baslatir
REM Port: 8081 · Tarayici: http://127.0.0.1:8081
REM Kapatmak icin: bu pencerede Ctrl+C (iki kez) veya pencereyi kapat.

cd /d "%~dp0"

REM Venv'in python.exe'sini dogrudan cagiriyoruz (activate'e gerek yok)
set PYTHON=.venv\Scripts\python.exe

if not exist "%PYTHON%" (
    echo [HATA] Sanal ortam bulunamadi: %PYTHON%
    echo Lutfen once projeye kurulum yapin.
    pause
    exit /b 1
)

echo.
echo ============================================
echo   LGS Takip - Yerel Sunucu
echo ============================================
echo   URL:      http://127.0.0.1:8081
echo   Ogretmen: ogretmen@lgs.local / ogretmen123
echo   Durdur:   Ctrl+C veya bu pencereyi kapat
echo ============================================
echo.

REM Tarayici otomatik acilsin (5 saniye sonra, sunucu baslamis olur)
start "" /b cmd /c "timeout /t 3 /nobreak >nul && start http://127.0.0.1:8081/"

"%PYTHON%" -m uvicorn app.main:app --reload --port 8081 --host 127.0.0.1

echo.
echo Sunucu durdu. Kapatmak icin bir tusa basin.
pause >nul
