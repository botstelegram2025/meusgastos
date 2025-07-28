import sqlite3
import os
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
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

# Estados do ConversationHandler
TIPO, CATEGORIA, VALOR, DESCRICAO = range(4)

# Categorias predefinidas para receita
CATEGORIAS_RECEITA = [
    ["Salário mensal", "Vale Alimentação"],
    ["Vendas Canais", "Adesão APP"],
    ["Outra"]
]

# Teclado principal com botões para receita e despesa
TECLADO_PRINCIPAL = ReplyKeyboardMarkup(
    [["➕ Receita", "➖ Despesa"], ["📊 Relatório", "💰 Saldo"]],
    resize_keyboard=True
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Bem-vindo ao Bot de Gestão Financeira!\n\n"
        "Use os botões abaixo para começar:",
        reply_markup=TECLADO_PRINCIPAL
    )
    return TIPO

async def escolher_tipo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text
    if texto == "➕ Receita":
        context.user_data['tipo'] = 'receita'

        # Mostrar teclado de categorias para receita
        reply_markup = ReplyKeyboardMarkup(CATEGORIAS_RECEITA, resize_keyboard=True, one_time_keyboard=True)
        await update.message.reply_text(
            "📂 Escolha uma categoria para a receita ou selecione 'Outra' para digitar manualmente:",
            reply_markup=reply_markup
        )
        return CATEGORIA

    elif texto == "➖ Despesa":
        context.user_data['tipo'] = 'despesa'
        await update.message.reply_text(
            "📂 Digite a *categoria* da despesa:",
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardRemove()
        )
        return CATEGORIA

    elif texto == "📊 Relatório":
        await update.message.reply_text(
            "Use o comando:\n/relatorio MM\n(exemplo: /relatorio 07 para julho)",
            reply_markup=TECLADO_PRINCIPAL
        )
        return TIPO

    elif texto == "💰 Saldo":
        saldo_atual = calcular_saldo()
        await update.message.reply_text(f"💰 Saldo atual: R$ {saldo_atual:.2f}", reply_markup=TECLADO_PRINCIPAL)
        return TIPO

    else:
        await update.message.reply_text("❌ Por favor, escolha uma opção válida usando os botões.")
        return TIPO

async def receber_categoria(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.strip()
    tipo = context.user_data.get('tipo')

    if tipo == 'receita':
        if texto == 'Outra':
            # Usuário quer digitar categoria manualmente
            await update.message.reply_text(
                "Digite a categoria da receita manualmente:",
                reply_markup=ReplyKeyboardRemove()
            )
            return CATEGORIA  # Continua esperando a categoria digitada
        else:
            # Categoria selecionada pelo botão
            context.user_data['categoria'] = texto
            await update.message.reply_text("💵 Agora digite o *valor* (exemplo: 123.45):", parse_mode='Markdown')
            return VALOR

    else:
        # Despesa: categoria digitada manualmente
        if not texto:
            await update.message.reply_text("❌ Categoria inválida. Tente novamente:")
            return CATEGORIA
        context.user_data['categoria'] = texto
        await update.message.reply_text("💵 Agora digite o *valor* (exemplo: 123.45):", parse_mode='Markdown')
        return VALOR

async def receber_valor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.strip()
    try:
        valor = float(texto.replace(',', '.'))
        if valor <= 0:
            raise ValueError()
        context.user_data['valor'] = valor
        await update.message.reply_text("📝 Agora digite uma descrição (ou 'nenhuma') para a transação:")
        return DESCRICAO
    except:
        await update.message.reply_text("❌ Valor inválido. Digite um número positivo, ex: 123.45")
        return VALOR

async def receber_descricao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    descricao = update.message.text.strip()
    if descricao.lower() == 'nenhuma':
        descricao = ''
    context.user_data['descricao'] = descricao

    # Salvar no banco
    adicionar_transacao(
        context.user_data['tipo'],
        context.user_data['categoria'],
        context.user_data['valor'],
        context.user_data['descricao']
    )

    await update.message.reply_text(
        f"✅ {context.user_data['tipo'].capitalize()} adicionada com sucesso!\n"
        f"Categoria: {context.user_data['categoria']}\n"
        f"Valor: R$ {context.user_data['valor']:.2f}\n"
        f"Descrição: {descricao if descricao else '(nenhuma)'}",
        reply_markup=TECLADO_PRINCIPAL
    )

    return TIPO

async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Operação cancelada.",
        reply_markup=TECLADO_PRINCIPAL
    )
    return ConversationHandler.END

# Comandos independentes para relatório, deletar e saldo

async def comando_relatorio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        mes = context.args[0]
        if len(mes) != 2 or not mes.isdigit() or not (1 <= int(mes) <= 12):
            raise ValueError()
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

async def comando_deletar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        id = int(context.args[0])
        deletar_transacao(id)
        await update.message.reply_text("🗑️ Transação deletada.")
    except:
        await update.message.reply_text("❌ Erro. Use: /deletar ID")

async def comando_saldo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    saldo_atual = calcular_saldo()
    await update.message.reply_text(f"💰 Saldo atual: R$ {saldo_atual:.2f}")

def main():
    if not TOKEN:
        print("⚠️ BOT_TOKEN não definido nas variáveis de ambiente.")
        return

    app = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start), MessageHandler(filters.TEXT & ~filters.COMMAND, escolher_tipo)],
        states={
            TIPO: [MessageHandler(filters.TEXT & ~filters.COMMAND, escolher_tipo)],
            CATEGORIA: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_categoria)],
            VALOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_valor)],
            DESCRICAO: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_descricao)],
        },
        fallbacks=[CommandHandler('cancelar', cancelar)],
        allow_reentry=True
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("relatorio", comando_relatorio))
    app.add_handler(CommandHandler("deletar", comando_deletar))
    app.add_handler(CommandHandler("saldo", comando_saldo))

    print("✅ Bot rodando...")
    app.run_polling()

if __name__ == "__main__":
    main()
