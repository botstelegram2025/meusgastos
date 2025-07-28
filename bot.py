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
EXCLUIR = 9  # Novo estado
SENHA = 10  # Estado novo para senha

TOKEN = os.environ.get("BOT_TOKEN")
DB_PATH = 'financeiro.db'

CATEGORIAS_RECEITA = ["Salário mensal", "Vale Alimentação", "Vendas Canais", "Adesão APP", "Vendas Créditos"]
CATEGORIAS_DESPESA = ["Alimentação", "Transporte", "Lazer", "Saúde", "Moradia", "Educação", "Outros"]

teclado_principal = ReplyKeyboardMarkup([
    [KeyboardButton("💰 Adicionar Receita"), KeyboardButton("🛒 Adicionar Despesa")],
    [KeyboardButton("📊 Relatório"), KeyboardButton("💵 Saldo")],
    [KeyboardButton("📅 Adicionar Despesa Agendada"), KeyboardButton("📋 Ver Despesas Agendadas")],
    [KeyboardButton("🗑️ Excluir Transação")],
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
        cursor.execute('''CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER UNIQUE)''')
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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    criar_tabelas()

    chat_id = update.message.chat_id
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM usuarios WHERE chat_id = ?", (chat_id,))
        if cursor.fetchone() is None:
            # Usuário novo, solicitar senha
            await update.message.reply_text("Digite a senha para acessar o bot:")
            return SENHA
        else:
            await update.message.reply_text("Bem-vindo de volta ao Bot Financeiro!", reply_markup=teclado_principal)
            return TIPO

async def senha(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.strip()
    chat_id = update.message.chat_id
    if texto == "1523":
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("INSERT OR IGNORE INTO usuarios (chat_id) VALUES (?)", (chat_id,))
            conn.commit()
        await update.message.reply_text("Senha correta! Bem-vindo ao Bot Financeiro!", reply_markup=teclado_principal)
        return TIPO
    else:
        await update.message.reply_text("Senha incorreta. Digite novamente ou /start para tentar novamente.")
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

    if texto in ["🛒 adicionar despesa", "adicionar despesa"]:
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

    if texto in ["📅 adicionar despesa agendada", "adicionar despesa agendada"]:
        buttons = [[InlineKeyboardButton(cat, callback_data=cat)] for cat in CATEGORIAS_DESPESA]
        await update.message.reply_text("Categoria da despesa agendada:", reply_markup=InlineKeyboardMarkup(buttons))
        return AGENDAR_CATEGORIA

    if texto in ["📋 ver despesas agendadas", "ver despesas agendadas"]:
        return await listar_despesas_agendadas(update, context)

    if texto in ["🗑️ excluir transação", "excluir transação"]:
        return await listar_transacoes_para_excluir(update, context)

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
    if texto in ["❌ cancelar", "cancelar"]:
        await update.message.reply_text("Operação cancelada.", reply_markup=teclado_principal)
        return TIPO
    if texto in ["⬅️ voltar", "voltar"]:
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
    if texto in ["❌ cancelar", "cancelar"]:
        await update.message.reply_text("Operação cancelada.", reply_markup=teclado_principal)
        return TIPO
    if texto in ["⬅️ voltar", "voltar"]:
        await update.message.reply_text(f"Digite o valor da {context.user_data['tipo']}:", reply_markup=teclado_voltar_cancelar())
        return VALOR

    descricao = update.message.text if texto != 'nenhuma' else ''
    tipo = context.user_data['tipo']
    adicionar_transacao(tipo, context.user_data['categoria'], context.user_data['valor'], descricao)
    await update.message.reply_text("Transação registrada com sucesso! ✅", reply_markup=teclado_principal)
    return TIPO

async def receber_relatorio_mes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.strip()
    if texto in ["❌ cancelar", "cancelar"]:
        await update.message.reply_text("Operação cancelada.", reply_markup=teclado_principal)
        return TIPO
    if texto in ["⬅️ voltar", "voltar"]:
        await update.message.reply_text("Voltando ao menu principal.", reply_markup=teclado_principal)
        return TIPO

    if not texto.isdigit() or not (1 <= int(texto) <= 12):
        await update.message.reply_text("Digite um mês válido (01 a 12):")
        return RELATORIO

    mes = int(texto)
    ano = datetime.now().year
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT tipo, categoria, valor, data, descricao
            FROM transacoes
            WHERE strftime('%m', data) = ? AND strftime('%Y', data) = ?
            ORDER BY data
        """, (f"{mes:02d}", str(ano)))
        rows = cursor.fetchall()

    if not rows:
        await update.message.reply_text("Nenhuma transação encontrada para este mês.", reply_markup=teclado_principal)
        return TIPO

    mensagem = f"Relatório para {mes:02d}/{ano}:\n\n"
    for t in rows:
        mensagem += f"{t[3]} - {t[0].capitalize()} - {t[1]} - R$ {t[2]:.2f} - {t[4]}\n"
    await update.message.reply_text(mensagem, reply_markup=teclado_principal)
    return TIPO

# --- DESPESAS AGENDADAS ---

async def agendar_categoria_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    categoria = query.data
    context.user_data['agendar_categoria'] = categoria
    await query.message.reply_text("Digite o valor da despesa agendada:", reply_markup=teclado_voltar_cancelar())
    return AGENDAR_VALOR

async def agendar_valor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.lower()
    if texto in ["❌ cancelar", "cancelar"]:
        await update.message.reply_text("Operação cancelada.", reply_markup=teclado_principal)
        return TIPO
    if texto in ["⬅️ voltar", "voltar"]:
        buttons = [[InlineKeyboardButton(cat, callback_data=cat)] for cat in CATEGORIAS_DESPESA]
        await update.message.reply_text("Categoria da despesa agendada:", reply_markup=InlineKeyboardMarkup(buttons))
        return AGENDAR_CATEGORIA

    try:
        valor = float(texto.replace(',', '.'))
        if valor <= 0:
            raise ValueError
        context.user_data['agendar_valor'] = valor
        await update.message.reply_text("Digite a data de vencimento (YYYY-MM-DD):", reply_markup=teclado_voltar_cancelar())
        return AGENDAR_VENCIMENTO
    except ValueError:
        await update.message.reply_text("Valor inválido. Digite um número positivo:")
        return AGENDAR_VALOR

async def agendar_vencimento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.strip()
    if texto in ["❌ cancelar", "cancelar"]:
        await update.message.reply_text("Operação cancelada.", reply_markup=teclado_principal)
        return TIPO
    if texto in ["⬅️ voltar", "voltar"]:
        await update.message.reply_text("Digite o valor da despesa agendada:", reply_markup=teclado_voltar_cancelar())
        return AGENDAR_VALOR
    try:
        datetime.strptime(texto, '%Y-%m-%d')
        context.user_data['agendar_vencimento'] = texto
        await update.message.reply_text("Digite uma descrição (ou 'nenhuma'):", reply_markup=teclado_voltar_cancelar())
        return AGENDAR_DESCRICAO
    except ValueError:
        await update.message.reply_text("Data inválida. Use o formato YYYY-MM-DD:")
        return AGENDAR_VENCIMENTO

async def agendar_descricao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.lower()
    if texto in ["❌ cancelar", "cancelar"]:
        await update.message.reply_text("Operação cancelada.", reply_markup=teclado_principal)
        return TIPO
    if texto in ["⬅️ voltar", "voltar"]:
        await update.message.reply_text("Digite a data de vencimento (YYYY-MM-DD):", reply_markup=teclado_voltar_cancelar())
        return AGENDAR_VENCIMENTO

    descricao = update.message.text if texto != 'nenhuma' else ''
    categoria = context.user_data['agendar_categoria']
    valor = context.user_data['agendar_valor']
    vencimento = context.user_data['agendar_vencimento']

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''INSERT INTO despesas_agendadas (categoria, valor, vencimento, descricao, status)
                        VALUES (?, ?, ?, ?, 'pendente')''',
                     (categoria, valor, vencimento, descricao))
        conn.commit()

    await update.message.reply_text("Despesa agendada com sucesso! ✅", reply_markup=teclado_principal)
    return TIPO

async def listar_despesas_agendadas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, categoria, valor, vencimento, descricao, status FROM despesas_agendadas ORDER BY vencimento")
        rows = cursor.fetchall()

    if not rows:
        await update.message.reply_text("Nenhuma despesa agendada encontrada.", reply_markup=teclado_principal)
        return TIPO

    mensagens = []
    for despesa in rows:
        id_, categoria, valor, vencimento, descricao, status = despesa
        status_emoji = "✅ Pago" if status == 'pago' else "⏳ Pendente"
        texto = f"ID: {id_}\nCategoria: {categoria}\nValor: R$ {valor:.2f}\nVencimento: {vencimento}\nDescrição: {descricao}\nStatus: {status_emoji}"
        mensagens.append(texto)

    # Enviar lista em mensagens separadas para não ficar pesado
    for msg in mensagens:
        await update.message.reply_text(msg)

    # Inline buttons para marcar como pago despesas pendentes
    buttons = []
    for despesa in rows:
        if despesa[5] == 'pendente':
            buttons.append([InlineKeyboardButton(f"Marcar ID {despesa[0]} como pago", callback_data=f"pagar_{despesa[0]}")])

    if buttons:
        await update.message.reply_text("Marcar despesas como pagas:", reply_markup=InlineKeyboardMarkup(buttons))
    else:
        await update.message.reply_text("Todas as despesas agendadas estão pagas.", reply_markup=teclado_principal)

    return TIPO

async def pagar_despesa_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    despesa_id = int(query.data.split('_')[1])

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        # Buscar dados da despesa
        cursor.execute("SELECT categoria, valor, vencimento, descricao FROM despesas_agendadas WHERE id=?", (despesa_id,))
        row = cursor.fetchone()
        if not row:
            await query.message.reply_text("Despesa não encontrada.", reply_markup=teclado_principal)
            return TIPO

        categoria, valor, vencimento, descricao = row

        # Marcar como pago
        cursor.execute("UPDATE despesas_agendadas SET status='pago' WHERE id=?", (despesa_id,))

        # Registrar despesa real para deduzir do saldo
        data_pagamento = datetime.now().strftime('%Y-%m-%d')
        cursor.execute('''INSERT INTO transacoes (tipo, categoria, valor, data, descricao)
                          VALUES (?, ?, ?, ?, ?)''', ('despesa', categoria, valor, data_pagamento, descricao))
        conn.commit()

    await query.message.reply_text(f"Despesa ID {despesa_id} marcada como paga e registrada no saldo.", reply_markup=teclado_principal)
    return TIPO

# --- Exclusão de transações ---

async def listar_transacoes_para_excluir(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, tipo, categoria, valor, data, descricao FROM transacoes ORDER BY data DESC LIMIT 20")
        rows = cursor.fetchall()

    if not rows:
        await update.message.reply_text("Nenhuma transação encontrada para exclusão.", reply_markup=teclado_principal)
        return TIPO

    buttons = []
    mensagem = "Selecione a transação para excluir:\n"
    for t in rows:
        tid, tipo, categoria, valor, data_, descricao = t
        desc = descricao if descricao else '-'
        mensagem += f"ID {tid}: {data_} {tipo} {categoria} R$ {valor:.2f} ({desc})\n"
        buttons.append([InlineKeyboardButton(f"Excluir ID {tid}", callback_data=f"excluir_{tid}")])

    await update.message.reply_text(mensagem)
    await update.message.reply_text("Selecione uma transação para excluir:", reply_markup=InlineKeyboardMarkup(buttons))
    return EXCLUIR

async def excluir_transacao_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    transacao_id = int(query.data.split('_')[1])

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM transacoes WHERE id=?", (transacao_id,))
        conn.commit()

    await query.message.reply_text(f"Transação ID {transacao_id} excluída.", reply_markup=teclado_principal)
    return TIPO

async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Operação cancelada.", reply_markup=teclado_principal)
    return TIPO

def main():
    application = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            SENHA: [MessageHandler(filters.TEXT & ~filters.COMMAND, senha)],
            TIPO: [MessageHandler(filters.Regex('^(💰 Adicionar Receita|🛒 Adicionar Despesa|📊 Relatório|💵 Saldo|📅 Adicionar Despesa Agendada|📋 Ver Despesas Agendadas|🗑️ Excluir Transação|❌ Cancelar)$'), escolher_tipo)],
            CATEGORIA: [CallbackQueryHandler(categoria_callback)],
            VALOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_valor)],
            DESCRICAO: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_descricao)],
            RELATORIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_relatorio_mes)],
            AGENDAR_CATEGORIA: [CallbackQueryHandler(agendar_categoria_callback)],
            AGENDAR_VALOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, agendar_valor)],
            AGENDAR_VENCIMENTO: [MessageHandler(filters.TEXT & ~filters.COMMAND, agendar_vencimento)],
            AGENDAR_DESCRICAO: [MessageHandler(filters.TEXT & ~filters.COMMAND, agendar_descricao)],
            EXCLUIR: [CallbackQueryHandler(excluir_transacao_callback)],
        },
        fallbacks=[CommandHandler('cancel', cancelar)],
    )

    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(pagar_despesa_callback, pattern=r"^pagar_\d+$"))

    application.run_polling()

if __name__ == '__main__':
    main()
