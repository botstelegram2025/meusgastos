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

# Estados do ConversationHandler
SENHA, TIPO, CATEGORIA, VALOR, DESCRICAO, RELATORIO = range(6)
AGENDAR_CATEGORIA, AGENDAR_VALOR, AGENDAR_VENCIMENTO, AGENDAR_DESCRICAO = range(6, 10)
REMOVER_SELECIONAR = 10

TOKEN = os.environ.get("BOT_TOKEN")
DB_PATH = 'financeiro.db'

CATEGORIAS_RECEITA = ["Salário mensal", "Vale Alimentação", "Vendas Canais", "Adesão APP", "Vendas Créditos", "Saldo Inicial"]
CATEGORIAS_DESPESA = ["Alimentação", "Transporte", "Lazer", "Saúde", "Moradia", "Educação", "Cartões", "Outros"]

teclado_principal = ReplyKeyboardMarkup([
    [KeyboardButton("💰 Adicionar Receita"), KeyboardButton("💲 Adicionar Despesa")],
    [KeyboardButton("🗑️ Remover Receita/Despesa")],
    [KeyboardButton("📊 Relatório"), KeyboardButton("💵 Saldo")],
    [KeyboardButton("📅 Adicionar Despesa Agendada"), KeyboardButton("📋 Ver Despesas Agendadas")],
    [KeyboardButton("❌ Cancelar")],
], resize_keyboard=True)

def teclado_voltar_cancelar():
    return ReplyKeyboardMarkup([
        [KeyboardButton("⬅️ Voltar"), KeyboardButton("❌ Cancelar")]
    ], resize_keyboard=True)

usuarios_autorizados = set()

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
    data = datetime.now().strftime('%d/%m/%Y')
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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    criar_tabelas()
    user_id = update.message.from_user.id
    if user_id not in usuarios_autorizados:
        await update.message.reply_text("Por favor, digite a senha para acessar o bot:")
        return SENHA
    else:
        await update.message.reply_text("Bem-vindo ao Bot Financeiro!", reply_markup=teclado_principal)
        return TIPO

async def verificar_senha(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    senha = update.message.text.strip()
    if senha == "1523":
        usuarios_autorizados.add(user_id)
        await update.message.reply_text("Senha correta! Você pode usar o bot agora.", reply_markup=teclado_principal)
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

    if texto in ["💲 adicionar despesa", "adicionar despesa"]:
        buttons = [[InlineKeyboardButton(cat, callback_data=cat)] for cat in CATEGORIAS_DESPESA]
        await update.message.reply_text("Selecione a categoria:", reply_markup=InlineKeyboardMarkup(buttons))
        return CATEGORIA

    if texto in ["🗑️ remover receita/despesa"]:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, tipo, categoria, valor, data FROM transacoes ORDER BY id DESC LIMIT 10")
            transacoes = cursor.fetchall()

        if not transacoes:
            await update.message.reply_text("Nenhuma transação para remover.", reply_markup=teclado_principal)
            return TIPO

        buttons = [
            [InlineKeyboardButton(f"{t[1].capitalize()} - {t[2]} - R$ {t[3]:.2f} ({t[4]})", callback_data=f"remover_{t[0]}")]
            for t in transacoes
        ]
        await update.message.reply_text("Selecione a transação para remover:", reply_markup=InlineKeyboardMarkup(buttons))
        return REMOVER_SELECIONAR

    if texto in ["📊 relatório", "relatório"]:
        await update.message.reply_text("Digite o mês e ano no formato MM/AAAA:", reply_markup=teclado_voltar_cancelar())
        return RELATORIO

    if texto in ["💵 saldo", "saldo"]:
        saldo = calcular_saldo()
        await update.message.reply_text(f"Saldo atual: R$ {saldo:.2f}", reply_markup=teclado_principal)
        return TIPO

    await update.message.reply_text("Escolha uma opção válida.", reply_markup=teclado_principal)
    return TIPO

async def selecionar_categoria(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    categoria = query.data
    tipo = 'receita' if categoria in CATEGORIAS_RECEITA else 'despesa'
    context.user_data['tipo'] = tipo
    context.user_data['categoria'] = categoria
    await query.message.reply_text(f"Digite o valor da {tipo}:", reply_markup=teclado_voltar_cancelar())
    return VALOR

async def receber_valor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.strip().replace(',', '.')
    try:
        valor = float(texto)
        context.user_data['valor'] = valor
        await update.message.reply_text("Digite uma descrição (ou apenas envie para pular):", reply_markup=teclado_voltar_cancelar())
        return DESCRICAO
    except ValueError:
        await update.message.reply_text("Valor inválido. Digite apenas números. Ex: 1500.00", reply_markup=teclado_voltar_cancelar())
        return VALOR

async def receber_descricao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    descricao = update.message.text.strip()
    tipo = context.user_data.get('tipo')
    categoria = context.user_data.get('categoria')
    valor = context.user_data.get('valor')
    adicionar_transacao(tipo, categoria, valor, descricao)
    await update.message.reply_text(f"{tipo.capitalize()} adicionada com sucesso!", reply_markup=teclado_principal)
    return TIPO

async def remover_selecao_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("remover_"):
        id_remover = int(data.split("_")[1])
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("DELETE FROM transacoes WHERE id = ?", (id_remover,))
            conn.commit()
        await query.message.reply_text(f"Transação {id_remover} removida com sucesso!", reply_markup=teclado_principal)
        return TIPO

def main():
    application = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            SENHA: [MessageHandler(filters.TEXT & ~filters.COMMAND, verificar_senha)],
            TIPO: [MessageHandler(filters.TEXT & ~filters.COMMAND, escolher_tipo)],
            CATEGORIA: [CallbackQueryHandler(selecionar_categoria)],
            VALOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_valor)],
            DESCRICAO: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_descricao)],
            RELATORIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, escolher_tipo)],
            REMOVER_SELECIONAR: [CallbackQueryHandler(remover_selecao_callback, pattern="^remover_\\d+$")],
        },
        fallbacks=[MessageHandler(filters.Regex("^(❌ Cancelar|⬅️ Voltar)$"), escolher_tipo)]
    )

    application.add_handler(conv_handler)
    application.run_polling()

if __name__ == "__main__":
    main()
