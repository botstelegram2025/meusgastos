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

TIPO, CATEGORIA, VALOR, DESCRICAO, RELATORIO = range(5)
AGENDAR_CATEGORIA, AGENDAR_VALOR, AGENDAR_VENCIMENTO, AGENDAR_DESCRICAO = range(5, 9)

TOKEN = os.environ.get("BOT_TOKEN")
DB_PATH = 'financeiro.db'

CATEGORIAS_RECEITA = ["Salário mensal", "Vale Alimentação", "Vendas Canais", "Adesão APP"]
CATEGORIAS_DESPESA = ["Alimentação", "Transporte", "Lazer", "Saúde", "Moradia", "Educação", "Outros"]

# Teclado principal
teclado_principal = ReplyKeyboardMarkup([
    [KeyboardButton("Adicionar Receita"), KeyboardButton("Adicionar Despesa")],
    [KeyboardButton("Relatório"), KeyboardButton("Saldo")],
    [KeyboardButton("Adicionar Despesa Agendada"), KeyboardButton("Ver Despesas Agendadas")],
    [KeyboardButton("Cancelar")],
], resize_keyboard=True)

# Teclado com botão Voltar e Cancelar para as etapas intermediárias
def teclado_voltar_cancelar():
    return ReplyKeyboardMarkup([
        [KeyboardButton("Voltar"), KeyboardButton("Cancelar")]
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

def calcular_saldo():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT SUM(valor) FROM transacoes WHERE tipo = 'receita'")
        receitas = cursor.fetchone()[0] or 0
        cursor.execute("SELECT SUM(valor) FROM transacoes WHERE tipo = 'despesa'")
        despesas = cursor.fetchone()[0] or 0
    return receitas - despesas

# --- Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    criar_tabelas()
    await update.message.reply_text(
        "Bem-vindo ao Bot Financeiro!", reply_markup=teclado_principal)
    return TIPO

async def escolher_tipo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.lower()
    
    if texto == "cancelar":
        await update.message.reply_text("Operação cancelada.", reply_markup=teclado_principal)
        return TIPO
    
    if texto == "voltar":
        # No menu principal, voltar não faz sentido, apenas mantém no TIPO
        await update.message.reply_text("Você já está no menu principal.", reply_markup=teclado_principal)
        return TIPO

    if texto == "adicionar receita":
        buttons = [[InlineKeyboardButton(cat, callback_data=cat)] for cat in CATEGORIAS_RECEITA]
        await update.message.reply_text("Selecione a categoria:", reply_markup=InlineKeyboardMarkup(buttons))
        return CATEGORIA

    if texto == "adicionar despesa":
        buttons = [[InlineKeyboardButton(cat, callback_data=cat)] for cat in CATEGORIAS_DESPESA]
        await update.message.reply_text("Selecione a categoria:", reply_markup=InlineKeyboardMarkup(buttons))
        return CATEGORIA

    if texto == "relatório":
        await update.message.reply_text("Digite o mês (MM):", reply_markup=teclado_voltar_cancelar())
        return RELATORIO

    if texto == "saldo":
        saldo = calcular_saldo()
        await update.message.reply_text(f"Saldo atual: R$ {saldo:.2f}", reply_markup=teclado_principal)
        return TIPO

    if texto == "adicionar despesa agendada":
        buttons = [[InlineKeyboardButton(cat, callback_data=cat)] for cat in CATEGORIAS_DESPESA]
        await update.message.reply_text("Categoria da despesa agendada:", reply_markup=InlineKeyboardMarkup(buttons))
        return AGENDAR_CATEGORIA

    if texto == "ver despesas agendadas":
        return await listar_despesas_agendadas(update, context)

    await update.message.reply_text("Escolha uma opção válida.", reply_markup=teclado_principal)
    return TIPO

async def categoria_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    categoria = query.data
    tipo = 'receita' if categoria in CATEGORIAS_RECEITA else 'despesa'
    context.user_data['tipo'] = tipo
    context.user_data['categoria'] = categoria
    await query.message.reply_text(f"Digite o valor da {tipo}:", reply_markup=teclado_voltar_cancelar())
    return VALOR

async def receber_valor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.lower()
    if texto == "cancelar":
        await update.message.reply_text("Operação cancelada.", reply_markup=teclado_principal)
        return TIPO
    if texto == "voltar":
        # Voltar para escolher tipo
        await update.message.reply_text("Voltando ao menu principal.", reply_markup=teclado_principal)
        return TIPO
    
    try:
        valor = float(update.message.text.replace(',', '.'))
        if valor <= 0:
            raise ValueError
        context.user_data['valor'] = valor
        await update.message.reply_text("Digite uma descrição (ou 'nenhuma'):", reply_markup=teclado_voltar_cancelar())
        return DESCRICAO
    except ValueError:
        await update.message.reply_text("Valor inválido. Digite um número positivo:")
        return VALOR

async def receber_descricao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.lower()
    if texto == "cancelar":
        await update.message.reply_text("Operação cancelada.", reply_markup=teclado_principal)
        return TIPO
    if texto == "voltar":
        # Voltar para digitar valor novamente
        await update.message.reply_text(f"Digite o valor da {context.user_data['tipo']}:", reply_markup=teclado_voltar_cancelar())
        return VALOR
    
    descricao = update.message.text if texto != 'nenhuma' else ''
    tipo = context.user_data['tipo']
    adicionar_transacao(tipo, context.user_data['categoria'], context.user_data['valor'], descricao)
    await update.message.reply_text("Transação registrada com sucesso!", reply_markup=teclado_principal)
    return TIPO

async def receber_relatorio_mes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.lower()
    if texto == "cancelar":
        await update.message.reply_text("Operação cancelada.", reply_markup=teclado_principal)
        return TIPO
    if texto == "voltar":
        await update.message.reply_text("Voltando ao menu principal.", reply_markup=teclado_principal)
        return TIPO

    mes = update.message.text.zfill(2)
    if not mes.isdigit() or not (1 <= int(mes) <= 12):
        await update.message.reply_text("Mês inválido. Digite no formato MM (ex: 07 para julho):")
        return RELATORIO

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT tipo, categoria, valor, data
            FROM transacoes
            WHERE strftime('%m', data) = ?
            ORDER BY data ASC
        """, (mes,))
        dados = cursor.fetchall()

    if not dados:
        await update.message.reply_text("Sem dados para este mês.", reply_markup=teclado_principal)
        return TIPO

    msg = f"\U0001F4CA Relatório do mês {mes}:\n"
    total = {"receita": 0, "despesa": 0}
    for tipo, cat, val, data in dados:
        msg += f"{data} - {tipo.upper()}: {cat} - R$ {val:.2f}\n"
        total[tipo] += val
    msg += f"\nSaldo: R$ {total['receita'] - total['despesa']:.2f}"
    await update.message.reply_text(msg, reply_markup=teclado_principal)
    return TIPO

# --- Despesa Agendada ---
async def agendar_categoria_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['categoria'] = query.data
    await query.message.reply_text("Digite o valor da despesa agendada:", reply_markup=teclado_voltar_cancelar())
    return AGENDAR_VALOR

async def agendar_valor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.lower()
    if texto == "cancelar":
        await update.message.reply_text("Operação cancelada.", reply_markup=teclado_principal)
        return TIPO
    if texto == "voltar":
        # Voltar para escolher categoria novamente
        buttons = [[InlineKeyboardButton(cat, callback_data=cat)] for cat in CATEGORIAS_DESPESA]
        await update.message.reply_text("Categoria da despesa agendada:", reply_markup=InlineKeyboardMarkup(buttons))
        return AGENDAR_CATEGORIA
    
    try:
        valor = float(update.message.text.replace(',', '.'))
        if valor <= 0:
            raise ValueError
        context.user_data['valor'] = valor
        await update.message.reply_text("Digite a data de vencimento (YYYY-MM-DD):", reply_markup=teclado_voltar_cancelar())
        return AGENDAR_VENCIMENTO
    except ValueError:
        await update.message.reply_text("Valor inválido. Digite um número positivo:")
        return AGENDAR_VALOR

async def agendar_vencimento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.lower()
    if texto == "cancelar":
        await update.message.reply_text("Operação cancelada.", reply_markup=teclado_principal)
        return TIPO
    if texto == "voltar":
        await update.message.reply_text("Digite o valor da despesa agendada:", reply_markup=teclado_voltar_cancelar())
        return AGENDAR_VALOR
    try:
        venc = datetime.strptime(update.message.text, "%Y-%m-%d").date()
        if venc < datetime.today().date():
            raise ValueError
        context.user_data['vencimento'] = venc.isoformat()
        await update.message.reply_text("Descrição da despesa (ou 'nenhuma'):", reply_markup=teclado_voltar_cancelar())
        return AGENDAR_DESCRICAO
    except ValueError:
        await update.message.reply_text("Data inválida. Use o formato YYYY-MM-DD e uma data futura.")
        return AGENDAR_VENCIMENTO

async def agendar_descricao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.lower()
    if texto == "cancelar":
        await update.message.reply_text("Operação cancelada.", reply_markup=teclado_principal)
        return TIPO
    if texto == "voltar":
        await update.message.reply_text("Digite a data de vencimento (YYYY-MM-DD):", reply_markup=teclado_voltar_cancelar())
        return AGENDAR_VENCIMENTO

    descricao = update.message.text if texto != 'nenhuma' else ''
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''INSERT INTO despesas_agendadas (categoria, valor, vencimento, descricao)
                        VALUES (?, ?, ?, ?)''', (
            context.user_data['categoria'],
            context.user_data['valor'],
            context.user_data['vencimento'],
            descricao
        ))
    await update.message.reply_text("Despesa agendada com sucesso!", reply_markup=teclado_principal)
    return TIPO

async def listar_despesas_agendadas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, categoria, valor, vencimento, descricao, status FROM despesas_agendadas ORDER BY vencimento ASC")
        rows = cursor.fetchall()

    if not rows:
        await update.message.reply_text("Nenhuma despesa agendada.", reply_markup=teclado_principal)
        return TIPO

    for row in rows:
        id, cat, val, venc, desc, status = row
        msg = (f"🗓️ Vencimento: {venc}\n📌 Categoria: {cat}\n"
               f"💰 Valor: R$ {val:.2f}\n📄 Desc: {desc or '(sem descrição)'}\n📍Status: {status}")
        if status == "pendente":
            buttons = [[InlineKeyboardButton("Marcar como Pago", callback_data=f"pagar_{id}")]]
            await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(buttons))
        else:
            await update.message.reply_text(msg)
    return TIPO

async def pagar_despesa_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    despesa_id = int(query.data.split('_')[1])
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT categoria, valor, descricao FROM despesas_agendadas WHERE id = ?", (despesa_id,))
        row = cursor.fetchone()
        if not row:
            await query.message.reply_text("Despesa não encontrada.")
            return TIPO
        cat, val, desc = row
        adicionar_transacao('despesa', cat, val, desc)
        cursor.execute("UPDATE despesas_agendadas SET status = 'pago' WHERE id = ?", (despesa_id,))
        conn.commit()

    await query.message.reply_text("✅ Despesa marcada como paga e registrada!")
    return TIPO

# --- Main ---
def main():
    criar_tabelas()
    application = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            TIPO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, escolher_tipo)
            ],
            CATEGORIA: [
                CallbackQueryHandler(categoria_callback)
            ],
            VALOR: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receber_valor)
            ],
            DESCRICAO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receber_descricao)
            ],
            RELATORIO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receber_relatorio_mes)
            ],
            AGENDAR_CATEGORIA: [
                CallbackQueryHandler(agendar_categoria_callback)
            ],
            AGENDAR_VALOR: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, agendar_valor)
            ],
            AGENDAR_VENCIMENTO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, agendar_vencimento)
            ],
            AGENDAR_DESCRICAO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, agendar_descricao)
            ],
        },
        fallbacks=[MessageHandler(filters.Regex("^(Cancelar|Voltar)$"), escolher_tipo)]
    )

    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(pagar_despesa_callback, pattern=r"^pagar_\d+$"))

    application.run_polling()

if __name__ == '__main__':
    main()
