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
SENHA = 9

TOKEN = os.environ.get("BOT_TOKEN")
DB_PATH = 'financeiro.db'
SENHA_CORRETA = "1523"

CATEGORIAS_RECEITA = ["Salário mensal", "Vale Alimentação", "Vendas Canais", "Adesão APP", "Vendas Créditos"]
CATEGORIAS_DESPESA = ["Alimentação", "Transporte", "Lazer", "Saúde", "Moradia", "Educação", "Outros"]

teclado_principal = ReplyKeyboardMarkup([
    [KeyboardButton("💰 Adicionar Receita"), KeyboardButton("🚲 Adicionar Despesa")],
    [KeyboardButton("📊 Relatório"), KeyboardButton("💵 Saldo")],
    [KeyboardButton("🗕️ Adicionar Despesa Agendada"), KeyboardButton("📋 Ver Despesas Agendadas")],
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
        conn.commit()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bem-vindo ao Bot Financeiro! Digite a senha para acessar:")
    return SENHA

async def validar_senha(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == SENHA_CORRETA:
        criar_tabelas()
        await update.message.reply_text("Acesso concedido. Bem-vindo!", reply_markup=teclado_principal)
        return TIPO
    else:
        await update.message.reply_text("Senha incorreta. Tente novamente:")
        return SENHA

async def escolher_tipo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.lower()

    if texto in ["❌ cancelar", "cancelar"]:
        await update.message.reply_text("Operação cancelada.", reply_markup=teclado_principal)
        return TIPO

    if texto in ["⬅️ voltar", "voltar"]:
        await update.message.reply_text("Você já está no menu principal.", reply_markup=teclado_principal)
        return TIPO

    if texto in ["💰 adicionar receita", "adicionar receita"]:
        buttons = [[InlineKeyboardButton(cat, callback_data=cat)] for cat in CATEGORIAS_RECEITA]
        await update.message.reply_text("Selecione a categoria:", reply_markup=InlineKeyboardMarkup(buttons))
        return CATEGORIA

    if texto in ["🚲 adicionar despesa", "adicionar despesa"]:
        buttons = [[InlineKeyboardButton(cat, callback_data=cat)] for cat in CATEGORIAS_DESPESA]
        await update.message.reply_text("Selecione a categoria:", reply_markup=InlineKeyboardMarkup(buttons))
        return CATEGORIA

    if texto in ["📊 relatório", "relatório"]:
        await update.message.reply_text("Digite o mês (MM):", reply_markup=teclado_voltar_cancelar())
        return RELATORIO

    if texto in ["💵 saldo", "saldo"]:
        saldo = calcular_saldo()
        await update.message.reply_text(f"Saldo atual: R$ {saldo:.2f}", reply_markup=teclado_principal)
        return TIPO

    if texto in ["🗕️ adicionar despesa agendada"]:
        buttons = [[InlineKeyboardButton(cat, callback_data=cat)] for cat in CATEGORIAS_DESPESA]
        await update.message.reply_text("Categoria da despesa agendada:", reply_markup=InlineKeyboardMarkup(buttons))
        return AGENDAR_CATEGORIA

    if texto in ["📋 ver despesas agendadas"]:
        return await listar_despesas_agendadas(update, context)

    await update.message.reply_text("Escolha uma opção válida.", reply_markup=teclado_principal)
    return TIPO

async def listar_despesas_agendadas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, categoria, valor, vencimento, descricao, status FROM despesas_agendadas WHERE status='pendente'")
        despesas = cursor.fetchall()

    if not despesas:
        await update.message.reply_text("Não há despesas agendadas pendentes.", reply_markup=teclado_principal)
        return TIPO

    for desp in despesas:
        msg = (f"ID: {desp[0]}\nCategoria: {desp[1]}\nValor: R$ {desp[2]:.2f}\n"
               f"Vencimento: {desp[3]}\nDescrição: {desp[4]}\nStatus: {desp[5]}")
        botao = InlineKeyboardMarkup.from_button(
            InlineKeyboardButton("✅ Marcar como Paga", callback_data=f"pagar_{desp[0]}")
        )
        await update.message.reply_text(msg, reply_markup=botao)

    return TIPO

async def pagar_despesa_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    despesa_id = int(query.data.split('_')[1])
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT categoria, valor, descricao FROM despesas_agendadas WHERE id=?", (despesa_id,))
        row = cursor.fetchone()
        if row:
            categoria, valor, descricao = row
            cursor.execute("UPDATE despesas_agendadas SET status='pago' WHERE id=?", (despesa_id,))
            cursor.execute("""
                INSERT INTO transacoes (tipo, categoria, valor, data, descricao)
                VALUES (?, ?, ?, ?, ?)
            """, ("despesa", categoria, valor, datetime.now().strftime('%Y-%m-%d'), f"Agendada: {descricao}"))
            conn.commit()
    await query.message.reply_text(f"Despesa agendada {despesa_id} marcada como paga e registrada. ✅", reply_markup=teclado_principal)

# --- Função de cálculo de saldo ---
def calcular_saldo():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT SUM(valor) FROM transacoes WHERE tipo = 'receita'")
        receitas = cursor.fetchone()[0] or 0
        cursor.execute("SELECT SUM(valor) FROM transacoes WHERE tipo = 'despesa'")
        despesas = cursor.fetchone()[0] or 0
    return receitas - despesas

# --- Main ---
def main():
    application = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            SENHA: [MessageHandler(filters.TEXT & ~filters.COMMAND, validar_senha)],
            TIPO: [MessageHandler(filters.TEXT & ~filters.COMMAND, escolher_tipo)],
            RELATORIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, escolher_tipo)],
        },
        fallbacks=[]
    )

    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(pagar_despesa_callback, pattern=r"^pagar_\\d+$"))
    application.run_polling()

if __name__ == '__main__':
    main()
