@echo off
chcp 65001 >nul
echo ========================================
echo 📤 上传项目到 GitHub
echo ========================================
echo.

REM 检查是否已安装 Git
where git >nul 2>&1
if errorlevel 1 (
    echo ❌ 错误：未检测到 Git
    echo 请先安装 Git: https://git-scm.com/download/win
    pause
    exit /b 1
)

REM 检查是否已初始化 Git
if not exist .git (
    echo 📦 初始化 Git 仓库...
    git init
    echo ✅ Git 仓库初始化完成
    echo.
)

REM 检查是否有 .env 文件（防止上传敏感信息）
if exist .env (
    echo ⚠️  检测到 .env 文件
    findstr /C:".env" .gitignore >nul 2>&1
    if errorlevel 1 (
        echo ❌ 错误：.env 未在 .gitignore 中！
        echo 为了安全，请先将 .env 添加到 .gitignore
        pause
        exit /b 1
    ) else (
        echo ✅ .env 已在 .gitignore 中，安全
    )
    echo.
)

REM 显示将要添加的文件
echo 📋 将要提交的文件：
git status -s
echo.

REM 确认
set /p confirm="是否继续？(Y/N): "
if /i not "%confirm%"=="Y" (
    echo 已取消
    pause
    exit /b 0
)

REM 添加文件
echo 📦 添加文件到暂存区...
git add .
echo.

REM 提交
set /p commit_msg="💬 请输入提交信息 (默认: Initial commit): "
if "%commit_msg%"=="" set commit_msg=Initial commit

git commit -m "%commit_msg%"
if errorlevel 1 (
    echo ⚠️  没有需要提交的更改
) else (
    echo ✅ 提交成功
)
echo.

REM 检查是否已配置远程仓库
git remote get-url origin >nul 2>&1
if errorlevel 1 (
    echo 🔗 配置远程仓库...
    echo.
    echo 请先在 GitHub 创建仓库：https://github.com/new
    echo 仓库名称建议：MyNameChat
    echo.
    set /p repo_url="📝 输入 GitHub 仓库 URL (例如: https://github.com/用户名/MyNameChat.git): "
    
    if "%repo_url%"=="" (
        echo ❌ 错误：未输入仓库 URL
        pause
        exit /b 1
    )
    
    git remote add origin %repo_url%
    echo ✅ 远程仓库配置完成
    echo.
)

REM 推送
echo 🚀 推送到 GitHub...
git branch -M main
git push -u origin main

if errorlevel 1 (
    echo.
    echo ❌ 推送失败！
    echo.
    echo 可能的原因：
    echo 1. 需要登录 GitHub（首次推送）
    echo 2. 远程仓库有冲突
    echo 3. 网络连接问题
    echo.
    echo 解决方法：
    echo - 确保已登录 GitHub
    echo - 使用 GitHub Desktop（图形界面）
    echo - 或配置 SSH 密钥
    echo.
    pause
    exit /b 1
) else (
    echo.
    echo ========================================
    echo ✅ 上传完成！
    echo ========================================
    echo.
    git remote get-url origin
    echo.
    echo 🌐 在浏览器中查看你的项目
    pause
)

