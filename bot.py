import sqlite3
import os
from datetime import datetime, time, timedelta
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
    CallbackQueryHandler,
    ConversationHandler,
)

# --- Estados ---
SENHA = -1
TIPO, CATEGORIA, VALOR, DESCRICAO, RELATORIO = range(5)
AGENDAR_CATEGORIA, AGENDAR_VALOR, AGENDAR_VENCIMENTO, AGENDAR_DESCRICAO = range(5, 9)
EXCLUIR = 9

# --- Variáveis ---
TOKEN = os.environ.get("BOT_TOKEN")
BOT_PASSWORD = os.environ.get("BOT_PASSWORD", "1523")
DB_PATH = 'financeiro.db'

CATEGORIAS_RECEITA = ["Salário mensal", "Vale Alimentação", "Vendas Canais", "Adesão APP", "Vendas Créditos"]
CATEGORIAS_DESPESA = ["Alimentação", "Transporte", "Lazer", "Saúde", "Moradia", "Educação", "Outros"]

teclado_principal = ReplyKeyboardMarkup([
    [KeyboardButton("💰 Adicionar Receita"), KeyboardButton("🛍️ Adicionar Despesa")],
    [KeyboardButton("📊 Relatório"), KeyboardButton("💵 Saldo")],
    [KeyboardButton("🗕️ Adicionar Despesa Agendada"), KeyboardButton("📋 Ver Despesas Agendadas")],
    [KeyboardButton("🗑️ Excluir Transação")],
    [KeyboardButton("❌ Cancelar")],
], resize_keyboard=True)

def teclado_voltar_cancelar():
    return ReplyKeyboardMarkup([
        [KeyboardButton("⬅️ Voltar"), KeyboardButton("❌ Cancelar")]
    ], resize_keyboard=True)

# --- Banco de dados ---
def criar_tabelas():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS transacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo TEXT, categoria TEXT, valor REAL, data TEXT, descricao TEXT)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS despesas_agendadas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            categoria TEXT, valor REAL, vencimento TEXT, descricao TEXT, status TEXT DEFAULT 'pendente')''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS usuarios (
            chat_id INTEGER PRIMARY KEY)''')
        conn.commit()

# --- Verificação de senha ---
async def verificar_senha(update: Update, context: ContextTypes.DEFAULT_TYPE):
    senha_digitada = update.message.text.strip()

    if senha_digitada != BOT_PASSWORD:
        await update.message.reply_text("❌ Senha incorreta. Tente novamente:")
        return SENHA

    chat_id = update.message.chat_id
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("INSERT OR IGNORE INTO usuarios (chat_id) VALUES (?)", (chat_id,))
        conn.commit()

    await update.message.reply_text("✅ Acesso autorizado! Bem-vindo ao Bot Financeiro.", reply_markup=teclado_principal)
    return TIPO

# --- Início ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    criar_tabelas()
    chat_id = update.message.chat_id

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM usuarios WHERE chat_id = ?", (chat_id,))
        usuario_existe = cursor.fetchone()

    if not usuario_existe:
        await update.message.reply_text("🔐 Olá! Para começar, digite a senha de acesso:")
        return SENHA

    await update.message.reply_text("👋 Bem-vindo de volta ao Bot Financeiro!", reply_markup=teclado_principal)
    return TIPO

# Aqui viriam as demais funções do bot (escolher_tipo, categoria_callback, etc.)
# Elas permanecem exatamente como no seu código anterior e não precisam ser modificadas.
# Você só precisa garantir que SENHA esteja incluído no ConversationHandler.

# --- Main ---
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            SENHA: [MessageHandler(filters.TEXT & ~filters.COMMAND, verificar_senha)],
            TIPO: [MessageHandler(filters.TEXT & ~filters.COMMAND, escolher_tipo)],
            CATEGORIA: [CallbackQueryHandler(categoria_callback)],
            VALOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_valor)],
            DESCRICAO: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_descricao)],
            RELATORIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_relatorio_mes)],
            AGENDAR_CATEGORIA: [CallbackQueryHandler(agendar_categoria_callback)],
            AGENDAR_VALOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, agendar_valor)],
            AGENDAR_VENCIMENTO: [MessageHandler(filters.TEXT & ~filters.COMMAND, agendar_vencimento)],
            AGENDAR_DESCRICAO: [MessageHandler(filters.TEXT & ~filters.COMMAND, agendar_descricao)],
            EXCLUIR: [CallbackQueryHandler(excluir_callback)],
        },
        fallbacks=[CommandHandler('start', start)]
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler('pagar', pagar_despesa))

    # Agendamento diário às 9h para notificações
    job_queue = app.job_queue
    now = datetime.now()
    proximo_9h = datetime.combine(now.date(), time(hour=9))
    if now > proximo_9h:
        proximo_9h += timedelta(days=1)
    delay_segundos = (proximo_9h - now).total_seconds()
    job_queue.run_repeating(notificar_despesas_vencendo, interval=86400, first=delay_segundos)

    print("Bot iniciado...")
    app.run_polling()

if __name__ == '__main__':
    main()
