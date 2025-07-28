import os  # <<< Correção: para ler BOT_TOKEN do ambiente
import sys  # <<< Correção: para encerrar com mensagem clara se faltar token
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ConversationHandler,
    ContextTypes,
)
import sqlite3
from datetime import datetime

# --- Constantes de estado ---
SENHA, TIPO, CATEGORIA, VALOR, DESCRICAO, RELATORIO, AGENDAR_CATEGORIA, AGENDAR_VALOR, AGENDAR_VENCIMENTO, AGENDAR_DESCRICAO = range(10)

# --- Banco de dados ---
DB_PATH = "financeiro.db"

# --- Categorias ---
CATEGORIAS_RECEITA = ["💳 Vendas Créditos", "💵 Salário", "🏱 Outros"]
CATEGORIAS_DESPESA = ["🏠 Aluguel", "🍔 Alimentação", "🚗 Transporte", "📱 Internet", "🏱 Outros"]

VOLTA_TXT = "⬅️ Voltar"
CANCELA_TXT = "❌ Cancelar"

# --- Teclados ---
def teclado_principal():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Adicionar Receita", callback_data="adicionar_receita")],
        [InlineKeyboardButton("➖ Adicionar Despesa", callback_data="adicionar_despesa")],
        [InlineKeyboardButton("🗕️ Agendar Despesa", callback_data="agendar_despesa")],
        [InlineKeyboardButton("📊 Ver Relatório", callback_data="relatorio")],
        [InlineKeyboardButton("🗓️ Ver Agendadas", callback_data="ver_agendadas")],
    ])

def teclado_voltar_cancelar():
    return ReplyKeyboardMarkup(
        [[VOLTA_TXT, CANCELA_TXT]],
        resize_keyboard=True,
        one_time_keyboard=True
    )

# --- Banco de dados ---
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
        conn.execute(
            '''INSERT INTO transacoes (tipo, categoria, valor, descricao, data)
               VALUES (?, ?, ?, ?, ?)''',
            (tipo, categoria, valor, descricao, datetime.now().strftime("%d/%m/%Y"))
        )
        conn.commit()

def adicionar_despesa_agendada(categoria, valor, vencimento, descricao):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            '''INSERT INTO despesas_agendadas (categoria, valor, vencimento, descricao)
               VALUES (?, ?, ?, ?)''',
            (categoria, valor, vencimento, descricao)
        )
        conn.commit()

# --- Handlers de navegação ---
async def handle_voltar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Volta ao menu principal
    await update.message.reply_text("Voltando ao menu principal…", reply_markup=teclado_principal())
    return TIPO

async def handle_cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Cancela o fluxo atual e volta ao menu
    await update.message.reply_text("Operação cancelada.", reply_markup=teclado_principal())
    return TIPO

# --- Categoria Callback ---
async def categoria_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    categoria = query.data
    context.user_data["categoria"] = categoria
    context.user_data["tipo"] = "receita" if categoria in CATEGORIAS_RECEITA else "despesa"
    await query.message.reply_text("Digite o valor:", reply_markup=teclado_voltar_cancelar())
    return VALOR

# --- Receber Valor ---
async def receber_valor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.strip().replace(",", ".")
    if texto in (VOLTA_TXT, CANCELA_TXT):  # <<< Correção: protege contra teclas especiais
        # Delega para handlers já mapeados no ConversationHandler
        return
    try:
        valor = float(texto)
        context.user_data['valor'] = valor
        await update.message.reply_text("Descreva brevemente essa transação:", reply_markup=teclado_voltar_cancelar())
        return DESCRICAO
    except ValueError:
        await update.message.reply_text("Digite um valor numérico válido.", reply_markup=teclado_voltar_cancelar())
        return VALOR

# --- Receber Descrição ---
async def receber_descricao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    descricao = update.message.text.strip()
    if descricao in (VOLTA_TXT, CANCELA_TXT):  # <<< Correção: protege contra teclas especiais
        return
    categoria = context.user_data.get("categoria")
    valor = context.user_data.get("valor")
    tipo = context.user_data.get("tipo")
    if categoria is None or valor is None or tipo is None:  # <<< Correção: valida fluxo
        await update.message.reply_text("Algo deu errado. Recomeçando fluxo.", reply_markup=teclado_principal())
        return TIPO
    adicionar_transacao(tipo, categoria, valor, descricao)
    await update.message.reply_text("✅ Transação registrada com sucesso!", reply_markup=teclado_principal())
    return TIPO

# --- Agendar Despesa ---
async def agendar_categoria(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["categoria"] = query.data
    await query.message.reply_text("Digite o valor da despesa:", reply_markup=teclado_voltar_cancelar())
    return AGENDAR_VALOR

async def agendar_valor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.strip().replace(",", ".")
    if texto in (VOLTA_TXT, CANCELA_TXT):
        return
    try:
        valor = float(texto)
        context.user_data["valor"] = valor
        await update.message.reply_text("Digite a data de vencimento (DD/MM/AAAA):", reply_markup=teclado_voltar_cancelar())
        return AGENDAR_VENCIMENTO
    except ValueError:
        await update.message.reply_text("Digite um valor numérico válido.", reply_markup=teclado_voltar_cancelar())
        return AGENDAR_VALOR

async def agendar_vencimento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    vencimento = update.message.text.strip()
    if vencimento in (VOLTA_TXT, CANCELA_TXT):
        return
    try:
        datetime.strptime(vencimento, "%d/%m/%Y")
        context.user_data["vencimento"] = vencimento
        await update.message.reply_text("Descreva essa despesa agendada:", reply_markup=teclado_voltar_cancelar())
        return AGENDAR_DESCRICAO
    except ValueError:
        await update.message.reply_text("Data inválida. Use o formato DD/MM/AAAA.", reply_markup=teclado_voltar_cancelar())
        return AGENDAR_VENCIMENTO

async def agendar_descricao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    descricao = update.message.text.strip()
    if descricao in (VOLTA_TXT, CANCELA_TXT):
        return
    categoria = context.user_data.get("categoria")
    valor = context.user_data.get("valor")
    vencimento = context.user_data.get("vencimento")
    if not all([categoria, valor, vencimento]):  # <<< Correção: valida fluxo
        await update.message.reply_text("Algo deu errado. Recomeçando fluxo.", reply_markup=teclado_principal())
        return TIPO
    adicionar_despesa_agendada(categoria, valor, vencimento, descricao)
    await update.message.reply_text("✅ Despesa agendada com sucesso!", reply_markup=teclado_principal())
    return TIPO

# --- Ver Relatório ---
async def solicitar_mes_relatorio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.message.reply_text(
        "Digite o mês e ano para o relatório (MM/AAAA):",
        reply_markup=teclado_voltar_cancelar()
    )
    return RELATORIO

async def gerar_relatorio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    entrada = update.message.text.strip()
    if entrada in (VOLTA_TXT, CANCELA_TXT):
        return
    try:
        mes, ano = entrada.split("/")
        mes = mes.zfill(2)
        if len(ano) != 4 or not ano.isdigit():
            raise ValueError
        # Datas são salvas como DD/MM/AAAA, então buscamos por %/MM/AAAA
        like = f"%/{mes}/{ano}"  # <<< Correção: padrão LIKE correto
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT tipo, valor FROM transacoes WHERE data LIKE ?", (like,))
            transacoes = cursor.fetchall()
        receitas = sum(v for t, v in transacoes if t == "receita")
        despesas = sum(v for t, v in transacoes if t == "despesa")
        saldo = receitas - despesas
        texto = (
            f"🗓️ *Relatório de {mes}/{ano}*\n\n"
            f"📈 Receitas: R$ {receitas:.2f}\n"
            f"📉 Despesas: R$ {despesas:.2f}\n"
            f"💰 Saldo: R$ {saldo:.2f}"
        )
        await update.message.reply_text(texto, parse_mode="Markdown", reply_markup=teclado_principal())
        return TIPO
    except Exception:
        await update.message.reply_text("Formato inválido. Use MM/AAAA.", reply_markup=teclado_voltar_cancelar())
        return RELATORIO

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

# --- Fluxo Inicial ---
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

# --- Main ---
def main():
    criar_tabelas()

    # --- Leitura e validação do token ---
    token = os.getenv("BOT_TOKEN", "").strip()  # <<< Correção: lê do ambiente
    if not token or ":" not in token:
        print(
            "ERRO: BOT_TOKEN ausente ou inválido.\n"
            "Defina a variável de ambiente BOT_TOKEN com o token do BotFather "
            "(ex.: 123456789:ABC-DEF1234ghIkl-zyx57W2v1u123ew11)."
        )
        sys.exit(1)  # <<< Correção: encerra antes de tentar iniciar

    app = Application.builder().token(token).build()  # <<< Correção: Application.builder()

    # Handlers comuns para Voltar/Cancelar (em todos os estados via ConversationHandler)
    voltar_handler = MessageHandler(filters.TEXT & filters.Regex(f"^{VOLTA_TXT}$"), handle_voltar)
    cancelar_handler = MessageHandler(filters.TEXT & filters.Regex(f"^{CANCELA_TXT}$"), handle_cancelar)

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            SENHA: [
                cancelar_handler, voltar_handler,  # <<< Correção: handlers de navegação
                MessageHandler(filters.TEXT & ~filters.COMMAND, verificar_senha),
            ],
            TIPO: [
                CallbackQueryHandler(escolher_tipo),
            ],
            CATEGORIA: [
                CallbackQueryHandler(categoria_callback),
            ],
            VALOR: [
                cancelar_handler, voltar_handler,  # <<< Correção
                MessageHandler(filters.TEXT & ~filters.COMMAND, receber_valor),
            ],
            DESCRICAO: [
                cancelar_handler, voltar_handler,  # <<< Correção
                MessageHandler(filters.TEXT & ~filters.COMMAND, receber_descricao),
            ],
            RELATORIO: [
                cancelar_handler, voltar_handler,  # <<< Correção
                MessageHandler(filters.TEXT & ~filters.COMMAND, gerar_relatorio),
            ],
            AGENDAR_CATEGORIA: [
                CallbackQueryHandler(agendar_categoria),
            ],
            AGENDAR_VALOR: [
                cancelar_handler, voltar_handler,  # <<< Correção
                MessageHandler(filters.TEXT & ~filters.COMMAND, agendar_valor),
            ],
            AGENDAR_VENCIMENTO: [
                cancelar_handler, voltar_handler,  # <<< Correção
                MessageHandler(filters.TEXT & ~filters.COMMAND, agendar_vencimento),
            ],
            AGENDAR_DESCRICAO: [
                cancelar_handler, voltar_handler,  # <<< Correção
                MessageHandler(filters.TEXT & ~filters.COMMAND, agendar_descricao),
            ],
        },
        fallbacks=[CommandHandler("cancel", handle_cancelar)],
        per_message=True,  # <<< Correção: elimina o PTBUserWarning para CallbackQueryHandler
    )

    app.add_handler(conv_handler)
    print("Bot rodando...")
    try:
        app.run_polling(allowed_updates=Update.ALL_TYPES)  # <<< Correção: garante receber mensagens e callbacks
    except KeyboardInterrupt:
        print("Bot finalizado.")

if __name__ == '__main__':
    main()
