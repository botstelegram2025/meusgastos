import sqlite3
import os
from datetime import datetime
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
    [KeyboardButton("💰 Adicionar Receita"), KeyboardButton("🛒 Adicionar Despesa")],
    [KeyboardButton("📊 Relatório"), KeyboardButton("💵 Saldo")],
    [KeyboardButton("📅 Adicionar Despesa Agendada"), KeyboardButton("📋 Ver Despesas Agendadas")],
    [KeyboardButton("🖑️ Excluir Transação")],
    [KeyboardButton("❌ Cancelar")],
], resize_keyboard=True)

def teclado_voltar_cancelar():
    return ReplyKeyboardMarkup([
        [KeyboardButton("⬅️ Voltar"), KeyboardButton("❌ Cancelar")]
    ], resize_keyboard=True)

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

def adicionar_transacao(tipo, categoria, valor, descricao):
    data = datetime.now().strftime('%Y-%m-%d')
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''INSERT INTO transacoes (tipo, categoria, valor, data, descricao)
                        VALUES (?, ?, ?, ?, ?)''', (tipo, categoria, valor, data, descricao))

def calcular_saldo():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT SUM(valor) FROM transacoes WHERE tipo = 'receita'")
        receitas = cursor.fetchone()[0] or 0
        cursor.execute("SELECT SUM(valor) FROM transacoes WHERE tipo = 'despesa'")
        despesas = cursor.fetchone()[0] or 0
    return receitas - despesas

async def verificar_senha(update: Update, context: ContextTypes.DEFAULT_TYPE):
    senha_digitada = update.message.text.strip()

    if senha_digitada != BOT_PASSWORD:
        await update.message.reply_text("❌ Senha incorreta. Tente novamente:")
        return SENHA

    chat_id = update.message.chat_id
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("INSERT OR IGNORE INTO usuarios (chat_id) VALUES (?)", (chat_id,))
        conn.commit()

    await update.message.reply_text("✅ Acesso autorizado! Escolha uma opção:", reply_markup=teclado_principal)
    return TIPO

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

async def escolher_tipo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text

    if texto == "💰 Adicionar Receita":
        await update.message.reply_text("Você escolheu adicionar uma receita. (Função em construção...)")
        return ConversationHandler.END

    elif texto == "🛒 Adicionar Despesa":
        await update.message.reply_text("Você escolheu adicionar uma despesa. (Função em construção...)")
        return ConversationHandler.END

    elif texto == "📊 Relatório":
        await update.message.reply_text("Você escolheu ver o relatório. (Função em construção...)")
        return ConversationHandler.END

    elif texto == "💵 Saldo":
        saldo = calcular_saldo()
        await update.message.reply_text(f"Seu saldo atual é: R$ {saldo:.2f}")
        return TIPO

    elif texto == "📅 Adicionar Despesa Agendada":
        await update.message.reply_text("Adicionar despesa agendada. (Função em construção...)")
        return ConversationHandler.END

    elif texto == "📋 Ver Despesas Agendadas":
        await update.message.reply_text("Ver despesas agendadas. (Função em construção...)")
        return ConversationHandler.END

    elif texto == "🖑️ Excluir Transação":
        await update.message.reply_text("Excluir transação. (Função em construção...)")
        return ConversationHandler.END

    elif texto == "❌ Cancelar":
        await update.message.reply_text("Operação cancelada.", reply_markup=teclado_principal)
        return TIPO

    else:
        await update.message.reply_text("Opção inválida. Por favor, escolha uma opção válida.", reply_markup=teclado_principal)
        return TIPO

# --- Funções simuladas ---
async def categoria_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer("Função categoria_callback em construção.")
    return ConversationHandler.END

async def receber_valor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Função receber_valor em construção.")
    return ConversationHandler.END

async def receber_descricao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Função receber_descricao em construção.")
    return ConversationHandler.END

async def receber_relatorio_mes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Função receber_relatorio_mes em construção.")
    return ConversationHandler.END

async def agendar_categoria_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer("Função agendar_categoria_callback em construção.")
    return ConversationHandler.END

async def agendar_valor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Função agendar_valor em construção.")
    return ConversationHandler.END

async def agendar_vencimento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Função agendar_vencimento em construção.")
    return ConversationHandler.END

async def agendar_descricao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Função agendar_descricao em construção.")
    return ConversationHandler.END

async def excluir_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer("Função excluir_callback em construção.")
    return ConversationHandler.END

# --- Main ---
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
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
        fallbacks=[MessageHandler(filters.Regex("❌ Cancelar"), start)],
    )

    app.add_handler(conv_handler)
    app.run_polling()

if __name__ == '__main__':
    main()
