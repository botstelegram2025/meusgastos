import sqlite3
import os
import sys
from datetime import datetime
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

# Leitura do token do ambiente com verificação
TOKEN = os.environ.get("BOT_TOKEN")
if not TOKEN:
    print("❌ ERRO: A variável de ambiente BOT_TOKEN não foi definida.")
    print("➡️  Defina com: export BOT_TOKEN='seu_token_aqui'")
    sys.exit(1)

# Banco de dados SQLite
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

# Funções do banco
def adicionar_transacao(tipo, categoria, valor, descricao):
    data = datetime.now().strftime('%Y-%m-%d')
    cursor.execute(
        'INSERT INTO transacoes (tipo, categoria, valor, data, descricao) VALUES (?, ?, ?, ?, ?)',
        (tipo, categoria, valor, data, descricao)
    )
    conn.commit()

def deletar_transacao(id):
    cursor.execute('DELETE FROM transacoes WHERE id = ?', (id,))
    conn.commit()

def gerar_relatorio(mes):
    cursor.execute("SELECT id, tipo, categoria, valor, data FROM transacoes WHERE strftime('%m', data) = ?", (mes,))
    return cursor.fetchall()

def calcular_saldo():
    cursor.execute("SELECT SUM(valor) FROM transacoes WHERE tipo = 'receita'")
    receitas = cursor.fetchone()[0] or 0
    cursor.execute("SELECT SUM(valor) FROM transacoes WHERE tipo = 'despesa'")
    despesas = cursor.fetchone()[0] or 0
    return receitas - despesas

# Estados do ConversationHandler
TIPO, CATEGORIA, VALOR, DESCRICAO = range(4)

# Start com teclado principal
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        ["➕ Receita", "➖ Despesa"],
        ["📊 Relatório", "💰 Saldo"],
        ["🗑️ Deletar", "🚫 Cancelar"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "🤖 Bem-vindo ao Bot de Gestão Financeira!\n\n"
        "Escolha uma opção usando os botões abaixo:",
        reply_markup=reply_markup
    )
    return TIPO

# Escolhe se é receita ou despesa
async def escolher_tipo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text
    if texto == "➕ Receita":
        context.user_data['tipo'] = 'receita'
    elif texto == "➖ Despesa":
        context.user_data['tipo'] = 'despesa'
    else:
        await update.message.reply_text("❌ Por favor, escolha '➕ Receita' ou '➖ Despesa'.")
        return TIPO

    await update.message.reply_text("📂 Digite a *categoria* da transação:", parse_mode='Markdown')
    return CATEGORIA

# Recebe categoria
async def receber_categoria(update: Update, context: ContextTypes.DEFAULT_TYPE):
    categoria = update.message.text.strip()
    if not categoria:
        await update.message.reply_text("❌ Categoria inválida. Tente novamente:")
        return CATEGORIA
    context.user_data['categoria'] = categoria
    await update.message.reply_text("💵 Agora digite o *valor* (exemplo: 123.45):", parse_mode='Markdown')
    return VALOR

# Recebe valor
async def receber_valor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    valor_texto = update.message.text.strip().replace(',', '.')
    try:
        valor = float(valor_texto)
        if valor <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Valor inválido. Digite um número positivo:")
        return VALOR

    context.user_data['valor'] = valor
    await update.message.reply_text("📝 Por fim, digite uma descrição (ou /pular para nenhum):")
    return DESCRICAO

# Recebe descrição ou pula
async def receber_descricao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    descricao = update.message.text.strip()
    tipo = context.user_data['tipo']
    categoria = context.user_data['categoria']
    valor = context.user_data['valor']

    adicionar_transacao(tipo, categoria, valor, descricao)
    await update.message.reply_text(
        f"✅ {tipo.capitalize()} adicionada:\n"
        f"Categoria: {categoria}\n"
        f"Valor: R$ {valor:.2f}\n"
        f"Descrição: {descricao}",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

async def pular_descricao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tipo = context.user_data['tipo']
    categoria = context.user_data['categoria']
    valor = context.user_data['valor']
    descricao = ''

    adicionar_transacao(tipo, categoria, valor, descricao)
    await update.message.reply_text(
        f"✅ {tipo.capitalize()} adicionada:\n"
        f"Categoria: {categoria}\n"
        f"Valor: R$ {valor:.2f}\n"
        f"(Sem descrição)",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

# Cancelar conversa
async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❌ Operação cancelada.", reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

# Mostrar saldo
async def saldo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    saldo_atual = calcular_saldo()
    await update.message.reply_text(f"💰 Saldo atual: R$ {saldo_atual:.2f}")

# Gerar relatório
async def relatorio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("❌ Use: /relatorio MM (exemplo: /relatorio 07)")
        return
    mes = args[0]
    if len(mes) != 2 or not mes.isdigit() or not (1 <= int(mes) <= 12):
        await update.message.reply_text("❌ Mês inválido. Use formato MM, ex: 07")
        return

    dados = gerar_relatorio(mes)
    if not dados:
        await update.message.reply_text("📭 Sem transações nesse mês.")
        return
    msg = "📊 Relatório:\n"
    for id_, tipo, cat, val, data in dados:
        msg += f"{data} - {tipo.upper()} - {cat} - R$ {val:.2f} (ID: {id_})\n"
    await update.message.reply_text(msg)

# Deletar transação
async def deletar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("❌ Use: /deletar ID")
        return
    try:
        id_ = int(args[0])
    except ValueError:
        await update.message.reply_text("❌ ID inválido. Use um número inteiro.")
        return

    deletar_transacao(id_)
    await update.message.reply_text(f"🗑️ Transação {id_} deletada.")

# Main
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            TIPO: [
                MessageHandler(filters.Regex("^(➕ Receita|➖ Despesa)$"), escolher_tipo)
            ],
            CATEGORIA: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_categoria)],
            VALOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_valor)],
            DESCRICAO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receber_descricao),
                CommandHandler("pular", pular_descricao),
            ],
        },
        fallbacks=[
            CommandHandler("cancelar", cancelar),
            MessageHandler(filters.Regex("🚫 Cancelar"), cancelar),
        ],
    )

    app.add_handler(conv_handler)

    # Comandos que também podem ser chamados via botão
    app.add_handler(CommandHandler("saldo", saldo))
    app.add_handler(CommandHandler("relatorio", relatorio))
    app.add_handler(CommandHandler("deletar", deletar))

    # Botões do teclado para essas funções
    app.add_handler(MessageHandler(filters.Regex("^💰 Saldo$"), saldo))
    app.add_handler(MessageHandler(filters.Regex("^📊 Relatório$"), relatorio))
    app.add_handler(MessageHandler(filters.Regex("^🗑️ Deletar$"), deletar))

    print("✅ Bot rodando...")
    app.run_polling()

if __name__ == "__main__":
    main()
