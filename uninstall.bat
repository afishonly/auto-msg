@echo off
chcp 65001 >nul
setlocal

set "TASK_NAME=WebMsgDailySend"

echo 移除定时任务: %TASK_NAME%
schtasks /Delete /TN "%TASK_NAME%" /F

if %errorlevel%==0 (
    echo 已成功移除定时任务
) else (
    echo 移除失败，任务可能不存在
)

pause
