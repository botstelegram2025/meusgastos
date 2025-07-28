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
    [KeyboardButton("💰 Adicionar Receita"), KeyboardButton("🛒 Adicionar Despesa")],
    [KeyboardButton("📊 Relatório"), KeyboardButton("💵 Saldo")],
    [KeyboardButton("📅 Adicionar Despesa Agendada"), KeyboardButton("📋 Ver Despesas Agendadas")],
    [KeyboardButton("🗑️ Excluir Transação")],
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

    await update.message.reply_text("✅ Acesso autorizado! Bem-vindo ao Bot Financeiro.", reply_markup=teclado_principal)
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

# --- Demais funções do bot ---

async def escolher_tipo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text
    if texto == "💰 Adicionar Receita":
        context.user_data['tipo'] = 'receita'
        categorias = CATEGORIAS_RECEITA
    elif texto == "🛒 Adicionar Despesa":
        context.user_data['tipo'] = 'despesa'
        categorias = CATEGORIAS_DESPESA
    else:
        return TIPO

    botoes = [[InlineKeyboardButton(cat, callback_data=cat)] for cat in categorias]
    await update.message.reply_text("Escolha a categoria:", reply_markup=InlineKeyboardMarkup(botoes))
    return CATEGORIA

async def categoria_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['categoria'] = query.data
    await query.edit_message_text("Digite o valor:")
    return VALOR

async def receber_valor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        valor = float(update.message.text.replace(',', '.'))
        context.user_data['valor'] = valor
        await update.message.reply_text("Digite uma descrição:")
        return DESCRICAO
    except ValueError:
        await update.message.reply_text("Valor inválido. Digite novamente:")
        return VALOR

async def receber_descricao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    descricao = update.message.text
    context.user_data['descricao'] = descricao

    adicionar_transacao(
        context.user_data['tipo'],
        context.user_data['categoria'],
        context.user_data['valor'],
        descricao
    )
    await update.message.reply_text("✅ Transação adicionada com sucesso!", reply_markup=teclado_principal)
    return TIPO

async def receber_relatorio_mes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    agora = datetime.now()
    inicio_mes = agora.replace(day=1).strftime('%Y-%m-%d')
    fim_mes = agora.strftime('%Y-%m-%d')
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT tipo, categoria, valor, descricao, data FROM transacoes WHERE data BETWEEN ? AND ?", (inicio_mes, fim_mes))
        transacoes = cursor.fetchall()

    if not transacoes:
        await update.message.reply_text("📭 Nenhuma transação encontrada neste mês.")
        return TIPO

    texto = "\n".join([f"{t[4]} - {t[0].capitalize()} - {t[1]}: R$ {t[2]:.2f} ({t[3]})" for t in transacoes])
    await update.message.reply_text(f"📊 Transações do mês:\n\n{texto}")
    return TIPO

async def agendar_categoria_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['categoria'] = query.data
    await query.edit_message_text("Digite o valor da despesa agendada:")
    return AGENDAR_VALOR

async def agendar_valor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        valor = float(update.message.text.replace(',', '.'))
        context.user_data['valor'] = valor
        await update.message.reply_text("Digite o vencimento (formato YYYY-MM-DD):")
        return AGENDAR_VENCIMENTO
    except ValueError:
        await update.message.reply_text("Valor inválido. Digite novamente:")
        return AGENDAR_VALOR

async def agendar_vencimento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    vencimento = update.message.text.strip()
    try:
        datetime.strptime(vencimento, '%Y-%m-%d')
        context.user_data['vencimento'] = vencimento
        await update.message.reply_text("Digite uma descrição para a despesa agendada:")
        return AGENDAR_DESCRICAO
    except ValueError:
        await update.message.reply_text("Data inválida. Use o formato YYYY-MM-DD:")
        return AGENDAR_VENCIMENTO

async def agendar_descricao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    descricao = update.message.text.strip()
    context.user_data['descricao'] = descricao

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''INSERT INTO despesas_agendadas (categoria, valor, vencimento, descricao)
                        VALUES (?, ?, ?, ?)''', (
            context.user_data['categoria'],
            context.user_data['valor'],
            context.user_data['vencimento'],
            descricao
        ))
        conn.commit()

    await update.message.reply_text("✅ Despesa agendada com sucesso!", reply_markup=teclado_principal)
    return TIPO

async def excluir_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Lógica para excluir transações (a ser implementada conforme necessário)
    await update.callback_query.answer("Função de exclusão ainda não implementada.")
    return TIPO

async def pagar_despesa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Lógica para pagar despesas agendadas (a ser implementada conforme necessário)
    await update.message.reply_text("Função de pagamento ainda não implementada.")

async def notificar_despesas_vencendo(context: ContextTypes.DEFAULT_TYPE):
    # Lógica para notificar sobre despesas agendadas vencendo (a ser implementada conforme necessário)
    pass

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
