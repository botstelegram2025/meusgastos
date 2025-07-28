import sqlite3
import os
from datetime import datetime, time, timedelta
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
    JobQueue,
)

TIPO, CATEGORIA, VALOR, DESCRICAO, RELATORIO = range(5)
AGENDAR_CATEGORIA, AGENDAR_VALOR, AGENDAR_VENCIMENTO, AGENDAR_DESCRICAO = range(5, 9)
EXCLUIR = 9  # Novo estado

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
            chat_id INTEGER PRIMARY KEY)''')  # tabela para salvar chat_id dos usuários
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
    # Salvar chat_id na tabela usuarios (ignorar duplicatas)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("INSERT OR IGNORE INTO usuarios (chat_id) VALUES (?)", (chat_id,))
        conn.commit()
    await update.message.reply_text("Bem-vindo ao Bot Financeiro!", reply_markup=teclado_principal)
    return TIPO

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
    texto = update.message.text.lower()
    if texto in ["❌ cancelar", "cancelar"]:
        await update.message.reply_text("Operação cancelada.", reply_markup=teclado_principal)
        return TIPO
    if texto in ["⬅️ voltar", "voltar"]:
        await update.message.reply_text("Voltando ao menu principal.", reply_markup=teclado_principal)
        return TIPO

    mes = update.message.text.zfill(2)
    if not mes.isdigit() or not (1 <= int(mes) <= 12):
        await update.message.reply_text("Mês inválido. Digite no formato MM (ex: 07 para julho):")
        return RELATORIO

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT tipo, categoria, valor, data
            FROM transacoes
            WHERE strftime('%m', data) = ?
            ORDER BY data ASC
        """, (mes,))
        dados = cursor.fetchall()

    if not dados:
        await update.message.reply_text("Sem dados para este mês.", reply_markup=teclado_principal)
        return TIPO

    msg = f"\U0001F4CA Relatório do mês {mes}:\n"
    total = {"receita": 0, "despesa": 0}
    for tipo, cat, val, data in dados:
        msg += f"{data} - {tipo.upper()}: {cat} - R$ {val:.2f}\n"
        total[tipo] += val
    msg += f"\nSaldo: R$ {total['receita'] - total['despesa']:.2f}"
    await update.message.reply_text(msg, reply_markup=teclado_principal)
    return TIPO

# --- Despesas Agendadas ---
async def agendar_categoria_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['categoria'] = query.data
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
        valor = float(update.message.text.replace(',', '.'))
        if valor <= 0:
            raise ValueError
        context.user_data['valor'] = valor
        await update.message.reply_text("Digite a data de vencimento (YYYY-MM-DD):", reply_markup=teclado_voltar_cancelar())
        return AGENDAR_VENCIMENTO
    except ValueError:
        await update.message.reply_text("Valor inválido. Digite um número positivo:")
        return AGENDAR_VALOR

async def agendar_vencimento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.lower()
    if texto in ["❌ cancelar", "cancelar"]:
        await update.message.reply_text("Operação cancelada.", reply_markup=teclado_principal)
        return TIPO
    if texto in ["⬅️ voltar", "voltar"]:
        await update.message.reply_text("Digite o valor da despesa agendada:", reply_markup=teclado_voltar_cancelar())
        return AGENDAR_VALOR
    try:
        venc = datetime.strptime(update.message.text, "%Y-%m-%d").date()
        if venc < datetime.today().date():
            raise ValueError
        context.user_data['vencimento'] = venc.isoformat()
        await update.message.reply_text("Descrição da despesa (ou 'nenhuma'):", reply_markup=teclado_voltar_cancelar())
        return AGENDAR_DESCRICAO
    except ValueError:
        await update.message.reply_text("Data inválida ou no passado. Use o formato YYYY-MM-DD e data futura:")
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
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO despesas_agendadas (categoria, valor, vencimento, descricao) VALUES (?, ?, ?, ?)",
            (context.user_data['categoria'], context.user_data['valor'], context.user_data['vencimento'], descricao)
        )
        conn.commit()
    await update.message.reply_text("Despesa agendada cadastrada com sucesso!", reply_markup=teclado_principal)
    return TIPO

async def listar_despesas_agendadas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, categoria, valor, vencimento, descricao, status FROM despesas_agendadas ORDER BY vencimento ASC")
        despesas = cursor.fetchall()
    if not despesas:
        await update.message.reply_text("Não há despesas agendadas.", reply_markup=teclado_principal)
        return TIPO

    msg = "Despesas agendadas:\n"
    for id_, cat, val, venc, desc, status in despesas:
        msg += f"ID {id_}: {cat} - R$ {val:.2f} - Vence em {venc} - Status: {status}\nDescrição: {desc}\n\n"
    await update.message.reply_text(msg, reply_markup=teclado_principal)
    return TIPO

async def listar_transacoes_para_excluir(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, tipo, categoria, valor, data, descricao FROM transacoes ORDER BY data DESC LIMIT 20")
        transacoes = cursor.fetchall()
    if not transacoes:
        await update.message.reply_text("Não há transações para excluir.", reply_markup=teclado_principal)
        return TIPO

    buttons = []
    for t in transacoes:
        id_, tipo, cat, val, data_, desc = t
        texto_btn = f"{tipo.capitalize()}: {cat} R$ {val:.2f} em {data_}"
        buttons.append([InlineKeyboardButton(texto_btn, callback_data=f"excluir_{id_}")])
    await update.message.reply_text("Escolha a transação para excluir:", reply_markup=InlineKeyboardMarkup(buttons))
    return EXCLUIR

async def excluir_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data.startswith("excluir_"):
        id_excluir = int(data.split("_")[1])
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            # Antes de excluir, verificar se é despesa e subtrair do saldo?
            cursor.execute("SELECT tipo, valor FROM transacoes WHERE id = ?", (id_excluir,))
            resultado = cursor.fetchone()
            if resultado is None:
                await query.message.reply_text("Transação não encontrada.", reply_markup=teclado_principal)
                return TIPO
            tipo, valor = resultado
            # Excluir a transação
            conn.execute("DELETE FROM transacoes WHERE id = ?", (id_excluir,))
            conn.commit()
        await query.message.reply_text("Transação excluída com sucesso.", reply_markup=teclado_principal)
        return TIPO

async def notificar_despesas_vencendo(context: ContextTypes.DEFAULT_TYPE):
    hoje = datetime.today().date().isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, categoria, valor, descricao FROM despesas_agendadas WHERE vencimento = ? AND status = 'pendente'", (hoje,))
        despesas_hoje = cursor.fetchall()
        cursor.execute("SELECT chat_id FROM usuarios")
        usuarios = cursor.fetchall()

    if not despesas_hoje:
        return

    for (chat_id,) in usuarios:
        msg = "⚠️ Contas vencendo hoje:\n"
        for despesa in despesas_hoje:
            id_, categoria, valor, descricao = despesa
            desc_txt = descricao if descricao else "-"
            msg += f"- {categoria}: R$ {valor:.2f} - {desc_txt}\n"
        await context.bot.send_message(chat_id=chat_id, text=msg)

async def pagar_despesa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.lower()
    partes = texto.split()
    if len(partes) != 2 or not partes[1].isdigit():
        await update.message.reply_text("Use: /pagar <id_da_despesa>", reply_markup=teclado_principal)
        return
    id_despesa = int(partes[1])
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT status, valor FROM despesas_agendadas WHERE id = ?", (id_despesa,))
        res = cursor.fetchone()
        if not res:
            await update.message.reply_text("Despesa não encontrada.", reply_markup=teclado_principal)
            return
        status, valor = res
        if status == 'paga':
            await update.message.reply_text("Despesa já marcada como paga.", reply_markup=teclado_principal)
            return
        # Marcar como paga
        conn.execute("UPDATE despesas_agendadas SET status = 'paga' WHERE id = ?", (id_despesa,))
        # Registrar como despesa na tabela transacoes para atualizar saldo
        data_hoje = datetime.now().strftime('%Y-%m-%d')
        cursor.execute("SELECT categoria, descricao FROM despesas_agendadas WHERE id = ?", (id_despesa,))
        categoria, descricao = cursor.fetchone()
        conn.execute("INSERT INTO transacoes (tipo, categoria, valor, data, descricao) VALUES (?, ?, ?, ?, ?)",
                     ('despesa', categoria, valor, data_hoje, descricao))
        conn.commit()
    await update.message.reply_text(f"Despesa ID {id_despesa} marcada como paga e saldo atualizado.", reply_markup=teclado_principal)

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            TIPO: [MessageHandler(filters.TEXT & ~filters.COMMAND, escolher_tipo)],
            CATEGORIA: [CallbackQueryHandler(categoria_callback)],
            VALOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_valor)],
            DESCRICAO: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_descricao)],
            RELATORIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_relatorio_mes)],
            AGENDAR_CATEGORIA: [CallbackQueryHandler(agendar_categoria_callback)],
            AGENDAR_VALOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, agendar_valor)],
            AGENDAR_VENCIMENTO: [MessageHandler(filters.TEXT & ~filters.COMMAND, agendar_vencimento)],
            AGENDAR_DESCRICAO: [MessageHandler(filters.TEXT & ~filters.COMMAND, agendar_descricao)],
            EXCLUIR: [CallbackQueryHandler(excluir_callback)],
        },
        fallbacks=[CommandHandler('start', start)]
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler('pagar', pagar_despesa))

    # Agendar job para rodar diariamente às 9h
    job_queue = app.job_queue
    # Calcula o delay para a próxima execução às 9h
    now = datetime.now()
    proximo_9h = datetime.combine(now.date(), time(hour=9))
    if now > proximo_9h:
        proximo_9h += timedelta(days=1)
    delay_segundos = (proximo_9h - now).total_seconds()

    job_queue.run_repeating(notificar_despesas_vencendo, interval=86400, first=delay_segundos)

    print("Bot iniciado...")
    app.run_polling()

if __name__ == '__main__':
    main() 
