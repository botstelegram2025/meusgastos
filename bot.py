import sqlite3
import os
from datetime import datetime
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
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

# Funções do banco
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

# Comandos do Bot
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Bem-vindo ao Bot de Gestão Financeira!\n\n"
        "Comandos disponíveis:\n"
        "/add_receita categoria valor descricao\n"
        "/add_despesa categoria valor descricao\n"
        "/deletar id\n"
        "/relatorio MM\n"
        "/saldo"
    )

async def add_receita(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        categoria, valor, *descricao = context.args
        adicionar_transacao('receita', categoria, float(valor), ' '.join(descricao))
        await update.message.reply_text("✅ Receita adicionada com sucesso!")
    except:
        await update.message.reply_text("❌ Erro no comando. Use: /add_receita categoria valor descricao")

async def add_despesa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        categoria, valor, *descricao = context.args
        adicionar_transacao('despesa', categoria, float(valor), ' '.join(descricao))
        await update.message.reply_text("✅ Despesa adicionada com sucesso!")
    except:
        await update.message.reply_text("❌ Erro no comando. Use: /add_despesa categoria valor descricao")

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
        dados = gerar_relatorio(mes)
        if not dados:
            await update.message.reply_text("📭 Sem transações nesse mês.")
            return
        msg = "📊 Relatório:\n"
        for tipo, cat, val, data in dados:
            msg += f"{data} - {tipo.upper()} - {cat} - R$ {val:.2f}\n"
        await update.message.reply_text(msg)
    except:
        await update.message.reply_text("❌ Erro. Use: /relatorio MM (ex: 07)")

async def saldo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    saldo_atual = calcular_saldo()
    await update.message.reply_text(f"💰 Saldo atual: R$ {saldo_atual:.2f}")

# Inicia o bot
def main():
    if not TOKEN:
        print("⚠️ BOT_TOKEN não definido nas variáveis de ambiente.")
        return

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add_receita", add_receita))
    app.add_handler(CommandHandler("add_despesa", add_despesa))
    app.add_handler(CommandHandler("deletar", deletar))
    app.add_handler(CommandHandler("relatorio", relatorio))
    app.add_handler(CommandHandler("saldo", saldo))

    print("✅ Bot rodando...")
    app.run_polling()

if __name__ == "__main__":
    main()
