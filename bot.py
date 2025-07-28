import os
import sys
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
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
(
    SENHA,
    TIPO,
    CATEGORIA,
    VALOR,
    DESCRICAO,
    RELATORIO,
    EXCLUIR_CONFIRMA,
) = range(7)

DB_PATH = "financeiro.db"

CATEGORIAS_RECEITA = ["💳 Vendas Créditos", "💵 Salário", "🏮 Outros"]
CATEGORIAS_DESPESA = ["🏠 Aluguel", "🍔 Alimentação", "🚗 Transporte", "📱 Internet", "🏮 Outros"]

VOLTA_TXT = "⬅️ Voltar"
CANCELA_TXT = "❌ Cancelar"

# --- Teclados ---
def teclado_principal():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("/add_receita"), KeyboardButton("/add_despesa")],
            [KeyboardButton("/relatorio"), KeyboardButton("/excluir")],
            [KeyboardButton("/cancel")],
        ],
        resize_keyboard=True,
    )


def teclado_voltar_cancelar():
    return ReplyKeyboardMarkup([[VOLTA_TXT, CANCELA_TXT]], resize_keyboard=True, one_time_keyboard=True)


# --- Banco de dados ---
def criar_tabelas():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
        CREATE TABLE IF NOT EXISTS transacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo TEXT NOT NULL,
            categoria TEXT NOT NULL,
            valor REAL NOT NULL,
            descricao TEXT NOT NULL,
            data TEXT NOT NULL
        )
        """
        )


# --- Fluxo Inicial ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔐 Digite a senha:")
    return SENHA


async def verificar_senha(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "1523":
        await update.message.reply_text(
            "✅ Bem-vindo!\nEscolha uma opção:\n"
            "/add_receita - Adicionar Receita\n"
            "/add_despesa - Adicionar Despesa\n"
            "/relatorio - Gerar Relatório\n"
            "/excluir - Excluir Transação\n"
            "/cancel - Cancelar",
            reply_markup=teclado_principal(),
        )
        return TIPO
    else:
        await update.message.reply_text("❌ Senha incorreta. Tente novamente:")
        return SENHA


# --- Cadastro de Transações ---
async def adicionar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cmd = update.message.text
    if cmd == "/add_receita":
        context.user_data["tipo"] = "receita"
        categorias = CATEGORIAS_RECEITA
    elif cmd == "/add_despesa":
        context.user_data["tipo"] = "despesa"
        categorias = CATEGORIAS_DESPESA
    else:
        await update.message.reply_text(
            "Comando inválido. Use o menu principal.", reply_markup=teclado_principal()
        )
        return TIPO

    botoes = [[InlineKeyboardButton(c, callback_data=c)] for c in categorias]
    await update.message.reply_text(
        "Escolha a categoria:", reply_markup=InlineKeyboardMarkup(botoes)
    )
    return CATEGORIA


async def selecionar_categoria(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["categoria"] = query.data
    await query.message.reply_text(
        "Digite o valor (exemplo: 150.50):", reply_markup=teclado_voltar_cancelar()
    )
    return VALOR


async def receber_valor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == VOLTA_TXT:
        # voltar para categoria
        categorias = (
            CATEGORIAS_RECEITA
            if context.user_data.get("tipo") == "receita"
            else CATEGORIAS_DESPESA
        )
        botoes = [[InlineKeyboardButton(c, callback_data=c)] for c in categorias]
        await update.message.reply_text(
            "Escolha a categoria:", reply_markup=InlineKeyboardMarkup(botoes)
        )
        return CATEGORIA
    elif text == CANCELA_TXT:
        return await cancelar(update, context)

    try:
        valor = float(text.replace(",", "."))
        if valor <= 0:
            raise ValueError()
        context.user_data["valor"] = valor
        await update.message.reply_text(
            "Descreva a transação:", reply_markup=teclado_voltar_cancelar()
        )
        return DESCRICAO
    except ValueError:
        await update.message.reply_text("Valor inválido. Insira um número positivo:")
        return VALOR


async def receber_descricao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == VOLTA_TXT:
        await update.message.reply_text(
            "Digite o valor (exemplo: 150.50):", reply_markup=teclado_voltar_cancelar()
        )
        return VALOR
    elif text == CANCELA_TXT:
        return await cancelar(update, context)

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO transacoes (tipo, categoria, valor, descricao, data) VALUES (?, ?, ?, ?, ?)",
            (
                context.user_data["tipo"],
                context.user_data["categoria"],
                context.user_data["valor"],
                text,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )
    await update.message.reply_text(
        "✅ Transação registrada.", reply_markup=teclado_principal()
    )
    return TIPO


# --- Relatório ---
async def relatorio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Digite o mês e ano para o relatório no formato MM/AAAA (exemplo: 07/2025):"
    )
    return RELATORIO


async def gerar_relatorio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == CANCELA_TXT:
        return await cancelar(update, context)

    try:
        mes, ano = text.split("/")
        if len(mes) != 2 or len(ano) != 4 or not (mes.isdigit() and ano.isdigit()):
            raise ValueError()

        periodo = f"{ano}-{mes.zfill(2)}"
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT tipo, valor FROM transacoes
                WHERE strftime('%Y-%m', data) = ?
                """,
                (periodo,),
            )
            transacoes = cursor.fetchall()

        receitas = sum(v for t, v in transacoes if t == "receita")
        despesas = sum(v for t, v in transacoes if t == "despesa")
        saldo = receitas - despesas

        await update.message.reply_text(
            f"📊 Relatório {mes}/{ano}\n"
            f"Receitas: R$ {receitas:.2f}\n"
            f"Despesas: R$ {despesas:.2f}\n"
            f"Saldo: R$ {saldo:.2f}",
            reply_markup=teclado_principal(),
        )
        return TIPO
    except Exception:
        await update.message.reply_text(
            "Formato inválido. Use MM/AAAA (exemplo: 07/2025):"
        )
        return RELATORIO


# --- Excluir Transações ---
async def excluir(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, tipo, categoria, valor FROM transacoes ORDER BY id DESC LIMIT 5"
        )
        registros = cursor.fetchall()

    if not registros:
        await update.message.reply_text(
            "Nenhum registro encontrado.", reply_markup=teclado_principal()
        )
        return TIPO

    botoes = [
        [InlineKeyboardButton(f"#{r[0]} - {r[1]} - {r[2]} - R${r[3]:.2f}", callback_data=str(r[0]))]
        for r in registros
    ]
    await update.message.reply_text(
        "Selecione o registro a excluir:", reply_markup=InlineKeyboardMarkup(botoes)
    )
    return EXCLUIR_CONFIRMA


async def confirmar_exclusao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    trans_id = query.data
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM transacoes WHERE id = ?", (trans_id,))
    await query.message.reply_text(
        f"❌ Transação #{trans_id} excluída.", reply_markup=teclado_principal()
    )
    return TIPO


# --- Cancelamento / Default ---
async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Operação cancelada.", reply_markup=teclado_principal()
    )
    return TIPO


async def comando_desconhecido(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Comando não reconhecido. Use o menu principal ou /cancel para voltar."
    )
    return TIPO


# --- Main ---
def main():
    criar_tabelas()
    token = os.getenv("BOT_TOKEN")
    if not token:
        print("Token não definido. Defina a variável de ambiente BOT_TOKEN.")
        sys.exit(1)

    app = Application.builder().token(token).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            SENHA: [MessageHandler(filters.TEXT & ~filters.COMMAND, verificar_senha)],
            TIPO: [
                MessageHandler(filters.Regex("^/add_receita$|^/add_despesa$"), adicionar),
                MessageHandler(filters.Regex("^/relatorio$"), relatorio),
                MessageHandler(filters.Regex("^/excluir$"), excluir),
                MessageHandler(filters.Regex("^/cancel$"), cancelar),
                MessageHandler(filters.ALL, comando_desconhecido),  # qualquer outro comando/texto
            ],
            CATEGORIA: [CallbackQueryHandler(selecionar_categoria)],
            VALOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_valor)],
            DESCRICAO: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_descricao)],
            RELATORIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, gerar_relatorio)],
            EXCLUIR_CONFIRMA: [CallbackQueryHandler(confirmar_exclusao)],
        },
        fallbacks=[CommandHandler("cancel", cancelar)],
        allow_reentry=True,
    )

    app.add_handler(conv_handler)
    print("✅ Bot rodando...")
    app.run_polling()


if __name__ == "__main__":
    main()
