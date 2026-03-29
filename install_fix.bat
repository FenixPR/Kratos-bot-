@echo off
echo Atualizando dependências para o Kratosbot com IA (Versão Sem Conflitos)...
python -m pip install --upgrade pip
pip uninstall openai -y
pip install requests python-dotenv python-telegram-bot websocket-client
echo.
echo Concluído! Tente rodar o bot novamente com 'python main.py'
pause
