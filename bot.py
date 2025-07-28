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
CATEGORIAS_DESPESA = ["Alimentação", "Transporte", "Lazer", "Saúde", "Moradia", "Educação", "Cartões" "Outros"]

teclado_principal = ReplyKeyboardMarkup([
    [KeyboardButton("💰 Adicionar Receita"), KeyboardButton("💲 Adicionar Despesa")],
    [KeyboardButton("🗑️ Remover Receita/Despesa")],
    [KeyboardButton("📊 Relatório"), KeyboardButton("💵 Saldo")],
    [KeyboardButton("🗓️ Adicionar Despesa Agendada"), KeyboardButton("📋 Ver Despesas Agendadas")],
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
        cursor.execute('''CREATE TABLE IF NOT EXISTS usuarios (
            user_id INTEGER PRIMARY KEY)''')
        conn.commit()


def usuario_autorizado(user_id):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM usuarios WHERE user_id = ?", (user_id,))
        return cursor.fetchone() is not None


def autorizar_usuario(user_id):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("INSERT OR IGNORE INTO usuarios (user_id) VALUES (?)", (user_id,))
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
    if not usuario_autorizado(user_id):
        await update.message.reply_text("Por favor, digite a senha para acessar o bot:")
        return SENHA
    else:
        await update.message.reply_text("Bem-vindo ao Bot Financeiro!", reply_markup=teclado_principal)
        return TIPO


async def verificar_senha(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    senha = update.message.text.strip()
    if senha == "1523":
        autorizar_usuario(user_id)
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

    if texto in ["🗓️ adicionar despesa agendada"]:
        buttons = [[InlineKeyboardButton(cat, callback_data=cat)] for cat in CATEGORIAS_DESPESA]
        await update.message.reply_text("Escolha a categoria da despesa agendada:", reply_markup=InlineKeyboardMarkup(buttons))
        return AGENDAR_CATEGORIA

    if texto in ["📋 ver despesas agendadas"]:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT categoria, valor, vencimento, descricao FROM despesas_agendadas WHERE status = 'pendente'")
            despesas = cursor.fetchall()

        if not despesas:
            await update.message.reply_text("Nenhuma despesa agendada encontrada.", reply_markup=teclado_principal)
            return TIPO

        resposta = "Despesas Agendadas:\n"
        for cat, val, venc, desc in despesas:
            resposta += f"Categoria: {cat}, Valor: R$ {val:.2f}, Vencimento: {venc}, Descrição: {desc}\n"

        await update.message.reply_text(resposta, reply_markup=teclado_principal)
        return TIPO

    if '/' in texto and len(texto) == 7:
        try:
            mes, ano = texto.split('/')
            datetime.strptime(f"01/{mes}/{ano}", "%d/%m/%Y")
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT tipo, categoria, valor, data FROM transacoes
                    WHERE strftime('%m/%Y', substr(data, 7, 4) || '-' || substr(data, 4, 2) || '-' || substr(data, 1, 2)) = ?
                """, (texto,))
                dados = cursor.fetchall()

            if not dados:
                await update.message.reply_text("Nenhuma transação encontrada para esse período.", reply_markup=teclado_principal)
                return TIPO

            relatorio = "\n".join([f"{d[0].capitalize()} - {d[1]} - R$ {d[2]:.2f} ({d[3]})" for d in dados])
            await update.message.reply_text(f"Relatório de {texto}:\n{relatorio}", reply_markup=teclado_principal)
            return TIPO
        except Exception:
            await update.message.reply_text("Formato inválido. Use MM/AAAA.", reply_markup=teclado_voltar_cancelar())
            return RELATORIO

    await update.message.reply_text("Escolha uma opção válida.", reply_markup=teclado_principal)
    return TIPO


# As demais funções permanecem como estão
