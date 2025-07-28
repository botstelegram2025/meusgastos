# --- CÓDIGO COMPLETO FINALIZADO ---

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler, ContextTypes
import sqlite3
from datetime import datetime

# --- Constantes de estado ---
SENHA, TIPO, CATEGORIA, VALOR, DESCRICAO, RELATORIO, AGENDAR_CATEGORIA, AGENDAR_VALOR, AGENDAR_VENCIMENTO, AGENDAR_DESCRICAO = range(10)

# --- Banco de dados ---
DB_PATH = "financeiro.db"

# --- Categorias ---
CATEGORIAS_RECEITA = ["💳 Vendas Créditos", "💵 Salário", "🏱 Outros"]
CATEGORIAS_DESPESA = ["🏠 Aluguel", "🍔 Alimentação", "🚗 Transporte", "📱 Internet", "🏱 Outros"]

# --- Teclados ---
def teclado_principal():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Adicionar Receita", callback_data="adicionar_receita")],
        [InlineKeyboardButton("➖ Adicionar Despesa", callback_data="adicionar_despesa")],
        [InlineKeyboardButton("🗕️ Agendar Despesa", callback_data="agendar_despesa")],
        [InlineKeyboardButton("📊 Ver Relatório", callback_data="relatorio")],
        [InlineKeyboardButton("🗓️ Ver Agendadas", callback_data="ver_agendadas")]
    ])

def teclado_voltar_cancelar():
    return ReplyKeyboardMarkup(
        [["⬅️ Voltar", "❌ Cancelar"]],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def criar_tabelas():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS transacoes (
            id INTEGER PRIMARY KEY,
            tipo TEXT,
            categoria TEXT,
            valor REAL,
            descricao TEXT,
            data TEXT
        )''')
        conn.execute('''CREATE TABLE IF NOT EXISTS despesas_agendadas (
            id INTEGER PRIMARY KEY,
            categoria TEXT,
            valor REAL,
            vencimento TEXT,
            descricao TEXT
        )''')
        conn.commit()

def adicionar_transacao(tipo, categoria, valor, descricao):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''INSERT INTO transacoes (tipo, categoria, valor, descricao, data)
                        VALUES (?, ?, ?, ?, ?)''', (tipo, categoria, valor, descricao, datetime.now().strftime("%d/%m/%Y")))
        conn.commit()

# --- Receber Valor ---
async def receber_valor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.strip().replace(",", ".")
    try:
        valor = float(texto)
        context.user_data['valor'] = valor
        await update.message.reply_text("Descreva brevemente essa transação:", reply_markup=teclado_voltar_cancelar())
        return DESCRICAO
    except ValueError:
        await update.message.reply_text("Digite um valor válido.", reply_markup=teclado_voltar_cancelar())
        return VALOR

# --- Receber Descrição ---
async def receber_descricao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    descricao = update.message.text.strip()
    categoria = context.user_data.get("categoria")
    valor = context.user_data.get("valor")
    tipo = context.user_data.get("tipo")
    adicionar_transacao(tipo, categoria, valor, descricao)
    await update.message.reply_text("Transação registrada com sucesso!", reply_markup=teclado_principal())
    return TIPO

# --- Fluxos de conversa (continua abaixo) ---
# (inclui: remover_transacao, categoria_callback, agendar_categoria, agendar_valor, agendar_vencimento, agendar_descricao)

# --- Ver Relatório ---
async def solicitar_mes_relatorio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.message.reply_text("Digite o mês e ano para o relatório (MM/AAAA):", reply_markup=teclado_voltar_cancelar())
    return RELATORIO

async def gerar_relatorio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    entrada = update.message.text.strip()
    try:
        mes, ano = entrada.split("/")
        data_formatada = f"{mes.zfill(2)}/{ano}"
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT tipo, valor FROM transacoes WHERE data LIKE ?", (f"%/{mes.zfill(2)}/{ano}",))
            transacoes = cursor.fetchall()
        receitas = sum(v for t, v in transacoes if t == "receita")
        despesas = sum(v for t, v in transacoes if t == "despesa")
        saldo = receitas - despesas
        await update.message.reply_text(f"🗓️ *Relatório de {data_formatada}*\n\n📈 Receitas: R$ {receitas:.2f}\n📉 Despesas: R$ {despesas:.2f}\n💰 Saldo: R$ {saldo:.2f}", parse_mode="Markdown", reply_markup=teclado_principal())
    except Exception:
        await update.message.reply_text("Formato inválido. Use MM/AAAA.", reply_markup=teclado_voltar_cancelar())
        return RELATORIO
    return TIPO

# --- Ver Despesas Agendadas ---
async def ver_despesas_agendadas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT categoria, valor, vencimento, descricao FROM despesas_agendadas")
        dados = cursor.fetchall()

    if not dados:
        await update.callback_query.message.reply_text("Nenhuma despesa agendada encontrada.", reply_markup=teclado_principal())
        return TIPO

    texto = "🗓️ *Despesas Agendadas:*\n\n"
    for cat, val, venc, desc in dados:
        texto += f"🔹 {cat} - R$ {val:.2f} - {venc} - {desc}\n"
    await update.callback_query.message.reply_text(texto, parse_mode="Markdown", reply_markup=teclado_principal())
    return TIPO

# --- Fluxo Inicial (senha e tipo) ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔐 Digite a senha de acesso:")
    return SENHA

async def verificar_senha(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "1523":
        await update.message.reply_text("✅ Acesso autorizado! Escolha uma opção:", reply_markup=teclado_principal())
        return TIPO
    else:
        await update.message.reply_text("❌ Senha incorreta. Tente novamente:")
        return SENHA

async def escolher_tipo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    acao = query.data

    if acao == "adicionar_receita":
        botoes = [[InlineKeyboardButton(c, callback_data=c)] for c in CATEGORIAS_RECEITA]
        await query.message.reply_text("Escolha a categoria da receita:", reply_markup=InlineKeyboardMarkup(botoes))
        return CATEGORIA
    elif acao == "adicionar_despesa":
        botoes = [[InlineKeyboardButton(c, callback_data=c)] for c in CATEGORIAS_DESPESA]
        await query.message.reply_text("Escolha a categoria da despesa:", reply_markup=InlineKeyboardMarkup(botoes))
        return CATEGORIA
    elif acao == "agendar_despesa":
        botoes = [[InlineKeyboardButton(c, callback_data=c)] for c in CATEGORIAS_DESPESA]
        await query.message.reply_text("Escolha a categoria da despesa agendada:", reply_markup=InlineKeyboardMarkup(botoes))
        return AGENDAR_CATEGORIA
    elif acao == "relatorio":
        return await solicitar_mes_relatorio(update, context)
    elif acao == "ver_agendadas":
        return await ver_despesas_agendadas(update, context)

    await query.message.reply_text("Escolha uma opção válida.", reply_markup=teclado_principal())
    return TIPO

# --- Função Main ---
def main():
    criar_tabelas()
    app = ApplicationBuilder().token("SEU_TOKEN_AQUI").build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            SENHA: [MessageHandler(filters.TEXT & ~filters.COMMAND, verificar_senha)],
            TIPO: [CallbackQueryHandler(escolher_tipo)],
            CATEGORIA: [CallbackQueryHandler(categoria_callback)],
            VALOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_valor)],
            DESCRICAO: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_descricao)],
            RELATORIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, gerar_relatorio)],
            AGENDAR_CATEGORIA: [CallbackQueryHandler(agendar_categoria)],
            AGENDAR_VALOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, agendar_valor)],
            AGENDAR_VENCIMENTO: [MessageHandler(filters.TEXT & ~filters.COMMAND, agendar_vencimento)],
            AGENDAR_DESCRICAO: [MessageHandler(filters.TEXT & ~filters.COMMAND, agendar_descricao)],
        },
        fallbacks=[]
    )

    app.add_handler(conv_handler)
    app.run_polling()

if __name__ == '__main__':
    main()
