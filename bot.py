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

TIPO, CATEGORIA, VALOR, DESCRICAO, RELATORIO = range(5)  # Adicionei RELATORIO

TOKEN = os.environ.get("BOT_TOKEN")

conn = sqlite3.connect('financeiro.db', check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''
    CREATE TABLE IF NOT EXISTS transacoes (
        id INTEGER PRIMARY KEY,
        tipo TEXT,
        categoria TEXT,
        valor REAL,
        data TEXT,
        descricao TEXT
    )
''')
conn.commit()

def adicionar_transacao(tipo, categoria, valor, descricao):
    data = datetime.now().strftime('%Y-%m-%d')
    cursor.execute(
        'INSERT INTO transacoes (tipo, categoria, valor, data, descricao) VALUES (?, ?, ?, ?, ?)',
        (tipo, categoria, valor, data, descricao)
    )
    conn.commit()

def gerar_relatorio(mes):
    cursor.execute("SELECT tipo, categoria, valor, data FROM transacoes WHERE strftime('%m', data) = ?", (mes,))
    return cursor.fetchall()

def calcular_saldo():
    cursor.execute("SELECT SUM(valor) FROM transacoes WHERE tipo = 'receita'")
    receitas = cursor.fetchone()[0] or 0
    cursor.execute("SELECT SUM(valor) FROM transacoes WHERE tipo = 'despesa'")
    despesas = cursor.fetchone()[0] or 0
    return receitas - despesas

CATEGORIAS_RECEITA = [
    "Salário mensal",
    "Vale Alimentação",
    "Vendas Canais",
    "Adesão APP",
]

teclado_principal = ReplyKeyboardMarkup(
    [
        [KeyboardButton("Adicionar Receita"), KeyboardButton("Adicionar Despesa")],
        [KeyboardButton("Relatório"), KeyboardButton("Saldo")],
        [KeyboardButton("Cancelar")],
    ],
    resize_keyboard=True,
    one_time_keyboard=False
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Bem-vindo ao Bot de Gestão Financeira!\n"
        "Use o teclado abaixo para navegar.",
        reply_markup=teclado_principal,
    )
    return TIPO

async def escolher_tipo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.lower()
    if texto == "adicionar receita":
        buttons = [
            [InlineKeyboardButton(cat, callback_data=cat)] for cat in CATEGORIAS_RECEITA
        ]
        markup = InlineKeyboardMarkup(buttons)
        await update.message.reply_text(
            "Selecione a categoria da receita:",
            reply_markup=markup
        )
        return CATEGORIA

    elif texto == "adicionar despesa":
        await update.message.reply_text(
            "Envie a categoria da despesa (texto):"
        )
        return CATEGORIA

    elif texto == "relatório":
        await update.message.reply_text(
            "Envie o mês do relatório no formato MM (exemplo: 07 para julho):"
        )
        return RELATORIO  # Estado específico para relatório

    elif texto == "saldo":
        saldo_atual = calcular_saldo()
        await update.message.reply_text(f"💰 Saldo atual: R$ {saldo_atual:.2f}")
        return TIPO

    elif texto == "cancelar":
        await update.message.reply_text("Operação cancelada.", reply_markup=teclado_principal)
        return ConversationHandler.END

    else:
        await update.message.reply_text(
            "Comando inválido. Use o teclado para selecionar uma opção."
        )
        return TIPO

async def categoria_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    categoria = query.data
    context.user_data['tipo'] = 'receita'
    context.user_data['categoria'] = categoria

    await query.message.reply_text("Digite o valor da receita (exemplo: 1500.00):")
    return VALOR

async def receber_categoria(update: Update, context: ContextTypes.DEFAULT_TYPE):
    categoria = update.message.text
    context.user_data['categoria'] = categoria
    context.user_data['tipo'] = 'despesa'

    await update.message.reply_text("Digite o valor da despesa (exemplo: 50.00):")
    return VALOR

async def receber_valor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        valor = float(update.message.text.replace(',', '.'))
        context.user_data['valor'] = valor
    except ValueError:
        await update.message.reply_text("Valor inválido. Digite um número, por favor:")
        return VALOR

    await update.message.reply_text("Digite uma descrição (ou 'nenhuma'):")
    return DESCRICAO

async def receber_descricao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    descricao = update.message.text
    if descricao.lower() == 'nenhuma':
        descricao = ''

    tipo = context.user_data.get('tipo')
    categoria = context.user_data.get('categoria')
    valor = context.user_data.get('valor')

    adicionar_transacao(tipo, categoria, valor, descricao)

    await update.message.reply_text(
        f"✅ {tipo.capitalize()} adicionada:\n"
        f"Categoria: {categoria}\n"
        f"Valor: R$ {valor:.2f}\n"
        f"Descrição: {descricao if descricao else '(sem descrição)'}",
        reply_markup=teclado_principal
    )
    return TIPO

async def receber_relatorio_mes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mes = update.message.text
    if len(mes) != 2 or not mes.isdigit() or not (1 <= int(mes) <= 12):
        await update.message.reply_text("Mês inválido. Envie no formato MM (ex: 07):")
        return RELATORIO

    dados = gerar_relatorio(mes.zfill(2))
    if not dados:
        await update.message.reply_text("📭 Sem transações nesse mês.", reply_markup=teclado_principal)
        return TIPO

    msg = "📊 Relatório:\n"
    for tipo, cat, val, data in dados:
        msg += f"{data} - {tipo.upper()} - {cat} - R$ {val:.2f}\n"

    await update.message.reply_text(msg, reply_markup=teclado_principal)
    return TIPO

async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Operação cancelada.", reply_markup=teclado_principal)
    return ConversationHandler.END

def main():
    if not TOKEN:
        print("⚠️ BOT_TOKEN não definido nas variáveis de ambiente.")
        return

    app = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start), MessageHandler(filters.TEXT & ~filters.COMMAND, escolher_tipo)],
        states={
            TIPO: [MessageHandler(filters.TEXT & ~filters.COMMAND, escolher_tipo)],
            CATEGORIA: [
                CallbackQueryHandler(categoria_callback),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receber_categoria)
            ],
            VALOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_valor)],
            DESCRICAO: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_descricao)],
            RELATORIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_relatorio_mes)],
        },
        fallbacks=[CommandHandler('cancelar', cancelar)],
        allow_reentry=True,
    )

    app.add_handler(conv_handler)

    print("✅ Bot rodando...")
    app.run_polling()

if __name__ == '__main__':
    main()
