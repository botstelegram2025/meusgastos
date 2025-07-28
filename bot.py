import sqlite3
import os
from datetime import datetime
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardRemove
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    ConversationHandler,
    filters
)

# Lê o token do ambiente
TOKEN = os.environ.get("BOT_TOKEN")

# Banco de dados SQLite
conn = sqlite3.connect('financeiro.db', check_same_thread=False)
cursor = conn.cursor()

# Cria a tabela se não existir
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

# Estados da conversa
TIPO, CATEGORIA, VALOR, DESCRICAO = range(4)

# Funções de banco
def adicionar_transacao(tipo, categoria, valor, descricao):
    data = datetime.now().strftime('%Y-%m-%d')
    cursor.execute('INSERT INTO transacoes (tipo, categoria, valor, data, descricao) VALUES (?, ?, ?, ?, ?)',
                   (tipo, categoria, valor, data, descricao))
    conn.commit()

def deletar_transacao(id):
    cursor.execute('DELETE FROM transacoes WHERE id = ?', (id,))
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

# Conversa interativa
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("➕ Adicionar Receita", callback_data='receita'),
            InlineKeyboardButton("➖ Adicionar Despesa", callback_data='despesa')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "📌 Escolha uma opção para começar:",
        reply_markup=reply_markup
    )
    return TIPO

async def escolher_tipo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['tipo'] = query.data
    await query.edit_message_text("📂 Digite a *categoria* da transação:", parse_mode='Markdown')
    return CATEGORIA

async def receber_categoria(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['categoria'] = update.message.text
    await update.message.reply_text("💸 Agora, informe o *valor*:", parse_mode='Markdown')
    return VALOR

async def receber_valor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data['valor'] = float(update.message.text.replace(',', '.'))
        await update.message.reply_text("📝 Por fim, escreva uma *descrição*:", parse_mode='Markdown')
        return DESCRICAO
    except ValueError:
        await update.message.reply_text("❌ Valor inválido. Digite um número, ex: 100.50")
        return VALOR

async def receber_descricao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    descricao = update.message.text
    dados = context.user_data
    adicionar_transacao(dados['tipo'], dados['categoria'], dados['valor'], descricao)
    await update.message.reply_text("✅ Transação registrada com sucesso!", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚫 Operação cancelada.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# Comandos auxiliares
async def deletar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        id = int(context.args[0])
        deletar_transacao(id)
        await update.message.reply_text("🗑️ Transação deletada.")
    except:
        await update.message.reply_text("❌ Erro. Use: /deletar ID")

async def relatorio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        mes = context.args[0]
        if not mes.isdigit() or int(mes) < 1 or int(mes) > 12:
            await update.message.reply_text("❌ Mês inválido. Use formato MM (ex: 07).")
            return

        dados = gerar_relatorio(mes)
        if not dados:
            await update.message.reply_text("📭 Sem transações nesse mês.")
            return
        msg = "📊 *Relatório do mês:*\n"
        total = 0
        for tipo, cat, val, data in dados:
            total += val if tipo == 'receita' else -val
            msg += f"{data} - {tipo.upper()} - {cat} - R$ {val:.2f}\n"
        msg += f"\n🧾 *Saldo do mês:* R$ {total:.2f}"
        await update.message.reply_text(msg, parse_mode='Markdown')
    except:
        await update.message.reply_text("❌ Erro. Use: /relatorio MM (ex: 07)")

async def saldo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    saldo_atual = calcular_saldo()
    await update.message.reply_text(f"💰 *Saldo atual:* R$ {saldo_atual:.2f}", parse_mode='Markdown')

# Main
def main():
    if not TOKEN:
        print("⚠️ BOT_TOKEN não definido nas variáveis de ambiente.")
        return

    app = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            TIPO: [CallbackQueryHandler(escolher_tipo)],
            CATEGORIA: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_categoria)],
            VALOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_valor)],
            DESCRICAO: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_descricao)],
        },
        fallbacks=[CommandHandler("cancelar", cancelar)],
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("saldo", saldo))
    app.add_handler(CommandHandler("relatorio", relatorio))
    app.add_handler(CommandHandler("deletar", deletar))

    print("✅ Bot rodando...")
    app.run_polling()

if __name__ == "__main__":
    main()
