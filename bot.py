import sqlite3
import os
import signal
import sys
from datetime import datetime
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

# Lê o token do ambiente
TOKEN = os.environ.get("BOT_TOKEN")

# Conexão com SQLite
conn = sqlite3.connect('financeiro.db', check_same_thread=False)
cursor = conn.cursor()

# Criação da tabela
cursor.execute('''
    CREATE TABLE IF NOT EXISTS transacoes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    cursor.execute('''
        INSERT INTO transacoes (tipo, categoria, valor, data, descricao)
        VALUES (?, ?, ?, ?, ?)
    ''', (tipo, categoria, valor, data, descricao))
    conn.commit()

def deletar_transacao(id):
    cursor.execute('DELETE FROM transacoes WHERE id = ?', (id,))
    conn.commit()
    return cursor.rowcount > 0

def gerar_relatorio(mes_ano):
    cursor.execute(
        "SELECT tipo, categoria, valor, data FROM transacoes WHERE strftime('%Y-%m', data) = ?",
        (mes_ano,))
    return cursor.fetchall()

def calcular_saldo(mes_ano=None):
    if mes_ano:
        cursor.execute("SELECT SUM(valor) FROM transacoes WHERE tipo = 'receita' AND strftime('%Y-%m', data) = ?", (mes_ano,))
        receitas = cursor.fetchone()[0] or 0
        cursor.execute("SELECT SUM(valor) FROM transacoes WHERE tipo = 'despesa' AND strftime('%Y-%m', data) = ?", (mes_ano,))
        despesas = cursor.fetchone()[0] or 0
    else:
        cursor.execute("SELECT SUM(valor) FROM transacoes WHERE tipo = 'receita'")
        receitas = cursor.fetchone()[0] or 0
        cursor.execute("SELECT SUM(valor) FROM transacoes WHERE tipo = 'despesa'")
        despesas = cursor.fetchone()[0] or 0
    return receitas - despesas

# Comandos do Bot
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *Bem-vindo ao Bot de Gestão Financeira!*\n\n"
        "📋 *Comandos disponíveis:*\n"
        "📥 /add_receita categoria valor descrição\n"
        "📤 /add_despesa categoria valor descrição\n"
        "🗑️ /deletar ID\n"
        "📊 /relatorio AAAA-MM\n"
        "💰 /saldo [AAAA-MM]",
        parse_mode="Markdown"
    )

async def add_receita(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        categoria, valor, *descricao = context.args
        valor = float(valor)
        adicionar_transacao('receita', categoria, valor, ' '.join(descricao))
        await update.message.reply_text("📥 Receita adicionada com sucesso!")
    except ValueError:
        await update.message.reply_text("❌ Valor inválido. Use: /add_receita categoria valor descrição")
    except IndexError:
        await update.message.reply_text("❌ Argumentos insuficientes. Use: /add_receita categoria valor descrição")

async def add_despesa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        categoria, valor, *descricao = context.args
        valor = float(valor)
        adicionar_transacao('despesa', categoria, valor, ' '.join(descricao))
        await update.message.reply_text("📤 Despesa adicionada com sucesso!")
    except ValueError:
        await update.message.reply_text("❌ Valor inválido. Use: /add_despesa categoria valor descrição")
    except IndexError:
        await update.message.reply_text("❌ Argumentos insuficientes. Use: /add_despesa categoria valor descrição")

async def deletar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        id = int(context.args[0])
        if deletar_transacao(id):
            await update.message.reply_text("🗑️ Transação deletada com sucesso.")
        else:
            await update.message.reply_text("❌ ID não encontrado.")
    except (IndexError, ValueError):
        await update.message.reply_text("❌ Use: /deletar ID")

async def relatorio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        mes_ano = context.args[0]  # formato: AAAA-MM
        dados = gerar_relatorio(mes_ano)
        if not dados:
            await update.message.reply_text("📭 Sem transações nesse mês.")
            return
        msg = f"📊 *Relatório de {mes_ano}:*\n"
        for tipo, cat, val, data in dados:
            emoji = "📥" if tipo == "receita" else "📤"
            msg += f"{data} - {emoji} {cat} - R$ {val:.2f}\n"
        await update.message.reply_text(msg, parse_mode="Markdown")
    except (IndexError, ValueError):
        await update.message.reply_text("❌ Use: /relatorio AAAA-MM (ex: 2025-07)")

async def saldo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        mes_ano = context.args[0] if context.args else None
        saldo_atual = calcular_saldo(mes_ano)
        if mes_ano:
            await update.message.reply_text(f"💰 Saldo em {mes_ano}: R$ {saldo_atual:.2f}")
        else:
            await update.message.reply_text(f"💰 Saldo total: R$ {saldo_atual:.2f}")
    except:
        await update.message.reply_text("❌ Use: /saldo ou /saldo AAAA-MM")

# Encerramento seguro
def shutdown(*args):
    print("⛔ Encerrando o bot...")
    conn.close()
    sys.exit(0)

# Main
def main():
    if not TOKEN:
        print("⚠️ BOT_TOKEN não definido nas variáveis de ambiente.")
        return

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

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
