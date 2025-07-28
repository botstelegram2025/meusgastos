import sqlite3
import os
from datetime import datetime, timedelta
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
from apscheduler.schedulers.background import BackgroundScheduler

TIPO, CATEGORIA, VALOR, DESCRICAO, RELATORIO = range(5)
AGENDAR_CATEGORIA, AGENDAR_VALOR, AGENDAR_VENCIMENTO, AGENDAR_DESCRICAO = range(5, 9)

TOKEN = os.environ.get("BOT_TOKEN")
DB_PATH = 'financeiro.db'

CATEGORIAS_RECEITA = ["Salário mensal", "Vale Alimentação", "Vendas Canais", "Adesão APP"]
CATEGORIAS_DESPESA = ["Alimentação", "Transporte", "Lazer", "Saúde", "Moradia", "Educação", "Outros"]

teclado_principal = ReplyKeyboardMarkup([
    [KeyboardButton("Adicionar Receita"), KeyboardButton("Adicionar Despesa")],
    [KeyboardButton("Relatório"), KeyboardButton("Saldo")],
    [KeyboardButton("Adicionar Despesa Agendada"), KeyboardButton("Ver Despesas Agendadas")],
    [KeyboardButton("Cancelar")],
], resize_keyboard=True)

# --- Banco de Dados ---
def criar_tabelas():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS transacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo TEXT, categoria TEXT, valor REAL, data TEXT, descricao TEXT)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS despesas_agendadas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            categoria TEXT, valor REAL, vencimento TEXT, descricao TEXT, status TEXT DEFAULT 'pendente')''')
        conn.commit()

def adicionar_transacao(tipo, categoria, valor, descricao):
    data = datetime.now().strftime('%Y-%m-%d')
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''INSERT INTO transacoes (tipo, categoria, valor, data, descricao)
                        VALUES (?, ?, ?, ?, ?)''', (tipo, categoria, valor, data, descricao))

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    criar_tabelas()
    await update.message.reply_text(
        "Bem-vindo ao Bot Financeiro!", reply_markup=teclado_principal)
    return TIPO

async def escolher_tipo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.lower()
    if texto == "cancelar":
        await update.message.reply_text("Operação cancelada.", reply_markup=teclado_principal)
        return ConversationHandler.END

    if texto == "adicionar receita":
        buttons = [[InlineKeyboardButton(cat, callback_data=cat)] for cat in CATEGORIAS_RECEITA]
        await update.message.reply_text("Selecione a categoria:", reply_markup=InlineKeyboardMarkup(buttons))
        return CATEGORIA

    if texto == "adicionar despesa":
        buttons = [[InlineKeyboardButton(cat, callback_data=cat)] for cat in CATEGORIAS_DESPESA]
        await update.message.reply_text("Selecione a categoria:", reply_markup=InlineKeyboardMarkup(buttons))
        return CATEGORIA

    if texto == "relatório":
        await update.message.reply_text("Digite o mês (MM):")
        return RELATORIO

    if texto == "saldo":
        saldo = calcular_saldo()
        await update.message.reply_text(f"Saldo atual: R$ {saldo:.2f}")
        return TIPO

    if texto == "adicionar despesa agendada":
        buttons = [[InlineKeyboardButton(cat, callback_data=cat)] for cat in CATEGORIAS_DESPESA]
        await update.message.reply_text("Categoria da despesa agendada:", reply_markup=InlineKeyboardMarkup(buttons))
        return AGENDAR_CATEGORIA

    if texto == "ver despesas agendadas":
        return await listar_despesas_agendadas(update, context)

    await update.message.reply_text("Escolha uma opção válida.")
    return TIPO

async def categoria_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    categoria = query.data
    tipo = 'receita' if categoria in CATEGORIAS_RECEITA else 'despesa'
    context.user_data['tipo'] = tipo
    context.user_data['categoria'] = categoria
    await query.message.reply_text(f"Digite o valor da {tipo}:")
    return VALOR

async def receber_valor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        valor = float(update.message.text.replace(',', '.'))
        if valor <= 0:
            raise ValueError
        context.user_data['valor'] = valor
        await update.message.reply_text("Digite uma descrição (ou 'nenhuma'):")
        return DESCRICAO
    except ValueError:
        await update.message.reply_text("Valor inválido. Digite um número positivo:")
        return VALOR

async def receber_descricao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    descricao = update.message.text if update.message.text.lower() != 'nenhuma' else ''
    tipo = context.user_data['tipo']
    adicionar_transacao(tipo, context.user_data['categoria'], context.user_data['valor'], descricao)
    await update.message.reply_text("Transação registrada com sucesso!", reply_markup=teclado_principal)
    return TIPO

async def receber_relatorio_mes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mes = update.message.text.zfill(2)
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT tipo, categoria, valor FROM transacoes WHERE strftime('%m', data) = ?", (mes,))
        dados = cursor.fetchall()

    if not dados:
        await update.message.reply_text("Sem dados para este mês.", reply_markup=teclado_principal)
        return TIPO

    msg = f"Relatório {mes}:
"
    total = {"receita": 0, "despesa": 0}
    for tipo, cat, val in dados:
        msg += f"{tipo.upper()}: {cat} - R$ {val:.2f}\n"
        total[tipo] += val
    msg += f"\nSaldo: R$ {total['receita'] - total['despesa']:.2f}"
    await update.message.reply_text(msg, reply_markup=teclado_principal)
    return TIPO

# --- Agendamento de Despesa ---
async def agendar_categoria_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['categoria'] = query.data
    await query.message.reply_text("Digite o valor da despesa agendada:")
    return AGENDAR_VALOR

async def agendar_valor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        valor = float(update.message.text.replace(',', '.'))
        if valor <= 0:
            raise ValueError
        context.user_data['valor'] = valor
        await update.message.reply_text("Digite a data de vencimento (YYYY-MM-DD):")
        return AGENDAR_VENCIMENTO
    except ValueError:
        await update.message.reply_text("Valor inválido. Digite um número positivo:")
        return AGENDAR_VALOR

async def agendar_vencimento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        vencimento = datetime.strptime(update.message.text, '%Y-%m-%d')
        context.user_data['vencimento'] = vencimento.strftime('%Y-%m-%d')
        await update.message.reply_text("Digite uma descrição (ou 'nenhuma'):")
        return AGENDAR_DESCRICAO
    except ValueError:
        await update.message.reply_text("Data inválida. Use o formato YYYY-MM-DD:")
        return AGENDAR_VENCIMENTO

async def agendar_descricao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    descricao = update.message.text if update.message.text.lower() != 'nenhuma' else ''
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''INSERT INTO despesas_agendadas (categoria, valor, vencimento, descricao)
                        VALUES (?, ?, ?, ?)''', (
            context.user_data['categoria'], context.user_data['valor'],
            context.user_data['vencimento'], descricao))
    await update.message.reply_text("Despesa agendada com sucesso!", reply_markup=teclado_principal)
    return TIPO

async def listar_despesas_agendadas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, categoria, valor, vencimento, status FROM despesas_agendadas WHERE status='pendente'")
        rows = cursor.fetchall()

    if not rows:
        await update.message.reply_text("Nenhuma despesa agendada.", reply_markup=teclado_principal)
        return TIPO

    buttons = [[InlineKeyboardButton(f"{cat} - {venc} - R$ {val:.2f}", callback_data=f"pagar_{id}")]
               for id, cat, val, venc, status in rows]
    markup = InlineKeyboardMarkup(buttons)
    await update.message.reply_text("Despesas Agendadas:", reply_markup=markup)
    return TIPO

async def marcar_como_pago(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    id = int(query.data.split('_')[1])

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT categoria, valor, descricao FROM despesas_agendadas WHERE id=?", (id,))
        row = cursor.fetchone()
        if row:
            adicionar_transacao("despesa", row[0], row[1], row[2])
            cursor.execute("UPDATE despesas_agendadas SET status='pago' WHERE id=?", (id,))
            conn.commit()

    await query.message.reply_text("Despesa marcada como paga!", reply_markup=teclado_principal)
    return TIPO

# --- Alerta Diário ---
def verificar_vencimentos():
    with sqlite3.connect(DB_PATH) as conn:
        hoje = datetime.now().strftime('%Y-%m-%d')
        cursor = conn.cursor()
        cursor.execute("SELECT id, descricao FROM despesas_agendadas WHERE vencimento=? AND status='pendente'", (hoje,))
        rows = cursor.fetchall()
        for row in rows:
            print(f"⚠️ Alerta: Despesa pendente hoje: {row[1]}")

scheduler = BackgroundScheduler()
scheduler.add_job(verificar_vencimentos, 'interval', hours=24)
scheduler.start()

def calcular_saldo():
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT SUM(valor) FROM transacoes WHERE tipo='receita'")
        receitas = c.fetchone()[0] or 0
        c.execute("SELECT SUM(valor) FROM transacoes WHERE tipo='despesa'")
        despesas = c.fetchone()[0] or 0
        return receitas - despesas

def main():
    if not TOKEN:
        print("BOT_TOKEN não definido.")
        return

    app = ApplicationBuilder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler('start', start), MessageHandler(filters.TEXT & ~filters.COMMAND, escolher_tipo)],
        states={
            TIPO: [MessageHandler(filters.TEXT & ~filters.COMMAND, escolher_tipo)],
            CATEGORIA: [CallbackQueryHandler(categoria_callback)],
            VALOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_valor)],
            DESCRICAO: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_descricao)],
            RELATORIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_relatorio_mes)],

            AGENDAR_CATEGORIA: [CallbackQueryHandler(agendar_categoria_callback)],
            AGENDAR_VALOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, agendar_valor)],
            AGENDAR_VENCIMENTO: [MessageHandler(filters.TEXT & ~filters.COMMAND, agendar_vencimento)],
            AGENDAR_DESCRICAO: [MessageHandler(filters.TEXT & ~filters.COMMAND, agendar_descricao)]
        },
        fallbacks=[],
        allow_reentry=True
    )

    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(marcar_como_pago, pattern=r'^pagar_\\d+$'))

    print("Bot rodando...")
    app.run_polling()

if __name__ == '__main__':
    main()
